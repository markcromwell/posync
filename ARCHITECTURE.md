# PO Sync Digest Architecture Contract

Canonical architecture contract for the PO Sync Digest service. All subsequent specs
must reference paths, naming rules, and design decisions documented here — not invent
parallel layouts.

**Purpose:** Standalone FastAPI service that produces a Product Owner weekly-sync digest
per program by consuming SOV's HTTP API (read-only; never touches SOV's database).

**Key entities:** `Digest` (per-program packet) with sections: shipped-since-last-sync,
awaiting-PO-decision, MVP/sprint status, and blockers.

## File Structure

```
main.py                     # ASGI entrypoint; exposes `app = create_app()` (uvicorn main:app)
app/
  __init__.py               # create_app() factory; auto-includes app/routers/*; conditional DB init
  config.py                 # pydantic-settings Settings (app_name, version, sov_url, api keys)
  health.py                 # Immutable GET /health contract (no auth)
  auth.py                   # X-API-Key verification dependency (planned)
  routers/
    __init__.py             # Feature routers package
    digest.py               # GET /digest/{program_code} JSON (+ optional HTML view) (planned)
  schemas/
    digest.py               # Pydantic Digest and section models (planned)
services/
  sov_client.py             # Isolated SOV HTTP client — sole module that calls SOV (planned)
templates/                  # Jinja2 HTML for digest view (planned)
scripts/
  smoke_boot.py             # Boot gate: import main:app, assert /health (no sys.path hacks)
  test_unit.py              # Fast pytest smoke suite (app factory + contracts)
  tests/                    # Topic-specific tests (e.g. test_digest.py) (planned)
  setup.py                  # Operational installer
Dockerfile                  # python:3.12-slim; CMD uvicorn main:app
docker-compose.yml          # Local container stack
requirements.in             # Direct dependencies (compile to requirements.lock)
pyproject.toml              # pytest testpaths=scripts, ruff line-length 100
PROGRAM_MAP.md              # Generated program map (curated + AST-generated sections)
```

**Layout rules (enforced by pipeline):**

- Entrypoint is always `main:app` at the repo root. No `src/` layout, no `PYTHONPATH`.
- New HTTP surfaces go in `app/routers/<feature>.py`, each exposing `router = APIRouter(...)`.
  `create_app()` auto-includes every module under `app/routers/` via `pkgutil.iter_modules`.
- All outbound SOV HTTP traffic lives in `services/sov_client.py` only.
- Tests live under `scripts/`; never create `scripts/tests/test_misc.py` (banned by semgrep gate).

## Naming Conventions

| Kind | Convention | Example |
|------|------------|---------|
| Modules / files | `snake_case.py` | `sov_client.py`, `digest.py` |
| Functions | `snake_case` | `build_digest()`, `verify_api_key()` |
| Classes | `PascalCase` | `SovClient`, `DigestOut`, `DigestSection` |
| Router variable | `router` (module-level) | `router = APIRouter(prefix="/digest", tags=["digest"])` |
| Pydantic schemas | `<Entity>Out`, `<Section>Out` | `DigestOut`, `ShippedItemOut` |
| Settings fields | `snake_case`, env-mapped | `sov_url`, `sov_api_key`, `digest_api_key` |
| Template files | `snake_case.html` in `templates/` | `digest.html` |

**`program_code` path parameter**

- Route shape: `GET /digest/{program_code}` (JSON) and optionally `GET /digest/{program_code}/view` (HTML).
- Validate with regex before any SOV call:

  ```text
  ^[A-Z][A-Z0-9_]{0,19}$
  ```

  (1–20 characters; starts with uppercase letter; remaining chars uppercase alphanumeric or underscore.)
  Invalid codes return HTTP 422 without calling SOV.

- Normalize to uppercase when building SOV URLs; reject codes that fail the regex.

**Auth header**

- Incoming digest requests require header `X-API-Key` matching the configured service key
  (`DIGEST_API_KEY` / `settings.digest_api_key`).
- Outbound SOV requests always send `X-API-Key: {SOV_API_KEY}` from `settings.sov_api_key`.

**Style:** Ruff line-length 100. Snake_case for functions and variables; PascalCase for classes.

## Module Responsibilities

| Module | Owns | Must NOT |
|--------|------|----------|
| `main.py` | `app = create_app()` re-export for uvicorn/Docker | Business logic, routes, or settings |
| `app/__init__.py` | App assembly, router auto-include, conditional SQLite init | HTTP handlers, SOV calls, auth logic |
| `app/config.py` | `Settings` and `settings` singleton (`sov_url`, API keys) | HTTP routing or outbound HTTP |
| `app/health.py` | `GET /health` returning exactly `{"status": "ok"}` | Auth, DB access, SOV calls |
| `app/auth.py` | `X-API-Key` verification FastAPI dependency | Routing, digest assembly, SOV HTTP |
| `app/routers/digest.py` | `/digest` endpoints, request validation, response assembly | Direct `httpx`/`requests` calls to SOV |
| `app/schemas/digest.py` | Pydantic models for digest JSON shape | HTTP or I/O |
| `services/sov_client.py` | All SOV HTTP GETs, headers, timeouts, response parsing | FastAPI routes, auth, digest formatting |
| `templates/` | Jinja HTML presentation | Business logic or SOV access |
| `scripts/smoke_boot.py` | Import `main:app`, verify `/health` | Modify `sys.path` |
| `scripts/test_unit.py` | Fast contract tests via `create_app()` + mocks | Live SOV or DB dependencies |

**Invariants**

- READ-ONLY over SOV via its HTTP API (`SOV_API_KEY`); never connect to SOV's database; never write SOV data.
- Auth is separated from routing: routers depend on `app/auth.py`; routers do not implement key comparison inline.
- SOV client is isolated: only `services/sov_client.py` constructs SOV URLs and performs HTTP I/O.

## Key Decisions

1. **Sequential SOV calls.** Digest sections are fetched one after another (not concurrent).
   Simplifies error attribution, respects SOV rate limits, and keeps partial-failure handling predictable.
   `services/sov_client.py` exposes discrete fetch functions; `app/routers/digest.py` orchestrates them in order.

2. **Graceful degradation.** If an individual SOV fetch fails (timeout, 5xx, parse error), the digest still
   returns HTTP 200 with the sections that succeeded. Failed sections carry an `error` field (or empty list +
   `status: "unavailable"`) instead of failing the entire response. Only auth failure (401), invalid
   `program_code` (422), or unknown program (404 after existence check) abort the request.

3. **Existence-check-first.** Before assembling sections, call SOV to confirm the program exists
   (e.g. `GET /coding/programs/{program_code}` or equivalent). Return 404 when the program is absent;
   do not fan out section queries for unknown programs.

4. **`main:app` immutability.** Docker CMD, compose healthcheck, and `scripts/smoke_boot.py` all assume
   `uvicorn main:app`. Do not rename `app` or relocate `main.py`.

5. **Since-last-sync filtering.** The shipped-since-last-sync section filters SOV results by a configurable
   last-sync timestamp (query param or stored preference). Date boundaries are applied in the router/service
   layer after fetch, not by mutating SOV data.

6. **No SOV DB access.** All program, spec, phase, and blocker data comes from SOV HTTP JSON responses.
   This service holds no authoritative copy of SOV state.

## Testing

Run from the repository root (no `PYTHONPATH`, no `sys.path` manipulation):

```bash
# Fast smoke (<15s) — mandatory before every push
python -m pytest scripts/test_unit.py -x -q --tb=short

# Boot gate (imports main:app exactly like Docker)
python -m scripts.smoke_boot
```

When adding or modifying topic tests under `scripts/tests/`, also run the matching file:

```bash
python -m pytest scripts/tests/test_<topic>.py -x -q --tb=short
```

Do not run the full `scripts/tests/` suite in CI workers (10+ minutes).

**Mocking rules**

- Use `fastapi.testclient.TestClient(create_app())` for HTTP contract tests.
- Mock all SOV HTTP in unit tests — patch `services/sov_client` functions or the underlying HTTP client;
  never require a live SOV instance in `scripts/test_unit.py`.
- If testing code that calls `os._exit()`, always patch it:
  `with unittest.mock.patch("os._exit"):` — unmocked `os._exit` kills the pytest process.

**`/digest` endpoint test expectations (for later specs)**

- Missing or wrong `X-API-Key` → 401.
- Invalid `program_code` (fails regex) → 422.
- Program not found in SOV (existence check) → 404.
- Happy path with mocked sequential SOV responses → 200 JSON digest with all section keys.
- One section fetch raises / returns error → 200 with degraded section, other sections populated.