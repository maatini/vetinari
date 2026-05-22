# Audit Remediation Plan — `multi-llm-vetinari`

> Ergebnis der Code-Audit vom 22.05.2026
> 6 Probleme identifiziert: 2 kritisch (🔴), 4 wichtig (🟡)

---

## Übersicht der Issues

| # | Kategorie | Schwere | Datei(en) | Aufwand |
|---|-----------|---------|-----------|---------|
| 1 | Concurrency: TTLCache & RateLimiter | 🔴 P0 | `llm_router.py` | 2h |
| 2 | Cache-Key ignoriert model/temperature | 🔴 P0 | `llm_router.py` | 0.5h |
| 3 | Toter Code (ModelConfig.api_key_var, _find_api_key_var) | 🟡 P1 | `llm_router.py` | 0.5h |
| 4 | Projekt-Müll (package.json, setup.py, node_modules) | 🟡 P1 | root | 0.5h |
| 5 | Falsche/veraltete Modell-IDs | 🟡 P2 | `llm_router.py` | 0.5h |
| 6 | Tests decken Concurrency nicht ab | 🟡 P2 | `tests/test_router.py` | 1h |

**Geschätzter Gesamtaufwand:** ~5 Stunden

---

## Phase A: Kritische Fixes (P0) — ~2.5h

### A1: Concurrency-Sicherheit für TTLCache

**Problem:** Kein Locking. Bei parallelen `asyncio.gather()`-Calls (via `consult_multiple`) oder simultanen FastMCP-Tool-Aufrufen können `_data`-Mutationen kollidieren.

**Ursache:**
- `get()` liest, prüft TTL, löscht, und verschiebt LRU — alles nicht-atomar
- `set()` schreibt, verschiebt, und evictet — Race mit `get()`
- `OrderedDict` ist nicht thread-/async-safe für Mutation während Iteration

**Fix:**
```python
class TTLCache:
    def __init__(self, ...):
        ...
        self._lock = asyncio.Lock()

    async def get(self, prompt, model=""):
        async with self._lock:
            # gesamte get-Logik unter Lock

    async def set(self, prompt, model="", value=""):
        async with self._lock:
            # gesamte set-Logik unter Lock

    async def clear(self):
        async with self._lock:
            self._data.clear()
```

**Betroffene Aufrufer anpassen:** `LLMRouter.consult()` ruft `self.cache.get()` und `self.cache.set()` auf — alle diese Aufrufe werden zu `await self.cache.get()` / `await self.cache.set()`.

**Dateien:**
- `src/expert_advisor/routers/llm_router.py` — `TTLCache`-Klasse + alle Aufrufstellen
- `tests/test_router.py` — `TestTTLCache`-Tests auf `await` umstellen

---

### A2: Concurrency-Sicherheit für RateLimiter

**Problem:** TOCTOU-Race zwischen `check()` und `record()`. Kein Locking, `setdefault`+`append` nicht atomar.

**Fix:**
```python
class RateLimiter:
    def __init__(self, ...):
        ...
        self._lock = asyncio.Lock()

    async def acquire(self, model: str) -> bool:
        """Atomar: check + record. Gibt True wenn Request erlaubt."""
        async with self._lock:
            self._cleanup(model)
            if len(self._timestamps.get(model, [])) < self._max:
                self._timestamps.setdefault(model, []).append(time.monotonic())
                return True
            return False
```

Die alte API (`check()` + `record()`) wird durch eine einzige atomare `acquire()`-Methode ersetzt — damit ist das TOCTOU-Problem beseitigt.

**Betroffene Aufrufer:**
```python
# Vorher:
if not self.rate_limiter.check(model_name):
    continue
...
self.rate_limiter.record(model_name)

# Nachher:
if not await self.rate_limiter.acquire(model_name):
    continue
```

**Dateien:**
- `src/expert_advisor/routers/llm_router.py` — `RateLimiter`-Klasse + Aufrufstelle in `consult()`
- `tests/test_router.py` — `TestRateLimiter`-Tests umschreiben

---

### A3: Cache-Key inkludiert model, temperature, max_tokens

**Problem:** `TTLCache._key()` hasht nur den Prompt. Unterschiedliche Modelle/Temperaturen kriegen dieselbe gecachte Antwort.

**Fix:**
```python
def _key(self, prompt: str, model: str = "", temperature: float = 0.0, max_tokens: int = 0) -> str:
    raw = f"{prompt}|{model}|{temperature}|{max_tokens}"
    return hashlib.sha256(raw.encode()).hexdigest()
```

**Betroffene Aufrufer:** `get()` und `set()` müssen die zusätzlichen Parameter durchreichen. In `LLMRouter.consult()`:
```python
cache_key = f"<system>{system_prompt}</system>\n<user>{user_message}</user>"
cached = await self.cache.get(cache_key, selected_model, temp, max_tok)
...
await self.cache.set(cache_key, selected_model, result["content"], temp, max_tok)
```

**Dateien:**
- `src/expert_advisor/routers/llm_router.py` — `TTLCache._key`, `.get`, `.set`, und Aufrufe in `LLMRouter.consult()`
- `tests/test_router.py` — Cache-Test um verschiedene model/temperature-Szenarien erweitern

---

## Phase B: Code-Bereinigung (P1) — ~1h

### B1: Toten Code entfernen

**Zu entfernende Elemente in `llm_router.py`:**

1. `ModelConfig` Dataclass komplett → ersetzen durch `list[str]` für Modell-Namen
2. `DEFAULT_MODELS` → wird zu `DEFAULT_MODEL_LIST: list[str]` (nur die `.model`-Strings)
3. `_find_api_key_var()` Methode komplett löschen (wird nie aufgerufen, LiteLLM managed Keys selbst)
4. `LLMRouter.__init__` → `models`-Parameter ändern von `list[ModelConfig]` zu `list[str]`
5. `LLMRouter.consult()` → `models_to_try`-Logik vereinfachen (direkt Strings statt `.model`-Attribute)

**Vorher:**
```python
@dataclass
class ModelConfig:
    model: str
    api_key_var: str      # ← ungenutzt
    priority: int = 0     # ← nur für Sortierung
    rpm_limit: int = 100  # ← ungenutzt

DEFAULT_MODELS = [
    ModelConfig(model="gpt-4o-mini", api_key_var="OPENAI_API_KEY", priority=0),
    ...
]
```

**Nachher:**
```python
DEFAULT_MODELS: list[str] = [
    "gpt-4o-mini",
    "anthropic/claude-3-5-sonnet-20241022",
    "gemini/gemini-1.5-flash",
    "deepseek/deepseek-chat",
    "groq/llama3-70b-8192",
    "gpt-3.5-turbo",
]
```

**Dateien:**
- `src/expert_advisor/routers/llm_router.py` — ~50 Zeilen entfernen, ~10 Zeilen vereinfachen

---

### B2: Projekt-Müll entfernen

```bash
# 1. Node.js-Müll
rm -rf node_modules/
rm package.json package-lock.json

# 2. Legacy setup.py (nicht das Paket-Setup — das macht pyproject.toml + hatchling)
rm setup.py

# 3. .pi/ ins .gitignore
echo ".pi/" >> .gitignore
```

**Begründung:**
- `package.json` enthält `@gotgenes/pi-permission-system` — existiert nicht auf npm, 100% Halluzination
- `setup.py` ist 170 Zeilen Code, der `.pi/skills/`-Verzeichnisse erstellt — gehört nicht ins Repo, ist User-seitige Tool-Konfiguration
- `.pi/` ist Pi-spezifisch, nicht Teil der Projektlogik

**Dateien:**
- `package.json` → löschen
- `package-lock.json` → löschen
- `node_modules/` → löschen
- `setup.py` → löschen
- `.gitignore` → `.pi/` hinzufügen

---

## Phase C: Modell-IDs korrigieren & Tests (P2) — ~1.5h

### C1: Modell-IDs aktualisieren

| Aktuell (falsch/veraltet) | Korrektur | Begründung |
|---|---|---|
| `gemini/gemini-2.0-flash` | `gemini/gemini-1.5-flash` | 2.0 Flash existiert nicht als stable release |
| `anthropic/claude-3-5-sonnet-20240620` | `anthropic/claude-3-5-sonnet-20241022` | Veraltetes snapshot-Datum |

**Alternativ:** Auf LiteLLM-Standard-Aliase setzen (z.B. `claude-3-5-sonnet-latest`), aber explizite IDs sind stabiler.

**Config-Naming-Inkonsistenz** (separater Fund):
- `config.py` hat `google_api_key` → ENV-Variable `GOOGLE_API_KEY`
- `DEFAULT_MODELS` und `_find_api_key_var` referenzieren `GEMINI_API_KEY`

→ Da `ModelConfig` samt `api_key_var` ohnehin gelöscht wird (B1), ist das nur noch relevant für `.env.example`. Die ENV-Variable heißt `GEMINI_API_KEY` (LiteLLM-Konvention). Also in `.env.example` vereinheitlichen: `GOOGLE_API_KEY` → `GEMINI_API_KEY`.

**Dateien:**
- `src/expert_advisor/routers/llm_router.py` — `DEFAULT_MODELS` Strings korrigieren
- `.env.example` — `GOOGLE_API_KEY` → `GEMINI_API_KEY`

---

### C2: Concurrency-Tests hinzufügen

**Neue Tests in `tests/test_router.py`:**

1. **`TestConcurrentCache`** — Parallele `get`/`set`-Aufrufe auf `TTLCache`:
   - 10 Tasks schreiben gleichzeitig, 10 Tasks lesen gleichzeitig
   - Assert: kein Crash, keine inkonsistenten Werte, keine verlorenen Einträge

2. **`TestConcurrentRateLimiter`** — Parallele `acquire`-Aufrufe:
   - `max_requests=3`: 10 parallele Tasks rufen `acquire` auf
   - Assert: genau 3 kriegen `True`, 7 kriegen `False` (keine Überschreitung)

3. **`TestConsultMultipleConcurrency`** — Integration:
   - `consult_multiple` mit 5 Experten, alle rufen dasselbe Modell
   - Assert: Cache-Logik korrekt, keine Duplikat-LLM-Calls

---

## Ausführungsreihenfolge

```
1. A3 (Cache-Key-Fix)           ← Schnellster Fix, isoliert, funktionaler Bug
2. A1 (TTLCache Lock)           ← Fundament für A2
3. A2 (RateLimiter Lock)        ← Baut auf A1-Pattern auf
4. B1 (Toter Code entfernen)    ← Nach A1/A2 da ModelConfig noch referenziert wird
5. B2 (Projekt-Müll löschen)    ← Unabhängig, kann parallel zu Phase A laufen
6. C1 (Modell-IDs korrigieren)  ← Teil von B1, wenn ModelConfig entfernt wird
7. C2 (Concurrency-Tests)       ← Nach A1+A2, validiert die Fixes
8. Full test run + Coverage     ← Abschlussvalidierung
```

## Erfolgskriterien

- [ ] `TTLCache` und `RateLimiter` nutzen `asyncio.Lock` — keine Race Conditions
- [ ] Cache-Key inkludiert model, temperature, max_tokens
- [ ] `consult_multiple` mit 5+ Experten läuft 20× ohne Cache-Korruption oder Rate-Limit-Verletzung
- [ ] Alle existierenden 57 Tests passen weiterhin (ggf. auf `async`/`await` migriert)
- [ ] Mindestens 4 neue Concurrency-Tests
- [ ] Coverage ≥ 89% (vorher: 89%)
- [ ] `package.json`, `package-lock.json`, `node_modules/`, `setup.py` gelöscht
- [ ] `.pi/` in `.gitignore`
- [ ] Keine toten Code-Pfade (`ModelConfig`, `_find_api_key_var`)
- [ ] Modell-IDs sind aktuelle, reale LiteLLM-IDs

---

## Risiken

| Risiko | Eintrittsw. | Mitigation |
|--------|-------------|------------|
| `asyncio.Lock` verlangsamt Cache unter Last | Mittel | Lock nur für `_data`-Mutationen, Hash-Berechnung außerhalb des Locks |
| API-Änderung bricht externe Aufrufer | Niedrig | `LLMRouter` ist interne Klasse, nur `server.py` ruft sie auf → mit anpassen |
| Gelöschte Dateien brechen CI/CD | Niedrig | Kein CI/CD existiert; `devbox run test` lokal prüfen |
| `node_modules/` löschen bricht devbox-Shell | Niedrig | `devbox.json` listet keine Node-Pakete → kein Einfluss |
