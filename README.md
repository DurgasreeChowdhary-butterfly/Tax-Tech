# ITR Filing

Mobile-first, API-first guided income-tax preparation platform for Indian
salaried individuals (V1: FY 2025-26 / AY 2026-27). See `docs/PRODUCT_SCOPE.md`
for scope and `docs/ARCHITECTURE.md` for the system shape. **V1 does not file
directly to the Income Tax portal.**

## One-time setup

```
cd backend
python -m venv .venv
.venv/Scripts/activate   # .venv/bin/activate on macOS/Linux
pip install -r requirements.txt -r requirements-dev.txt
cd ..
cd frontend
npm install
cd ..
```

## How to start

```
python scripts/dev.py
```

This one command: starts the backend, waits until it's actually healthy
(`GET /docs`), starts the frontend, waits until it's actually healthy, then
prints both URLs and stops immediately with a clear error if either process
fails to start, crashes later, or if ports 8000/5173 are already in use.

```
[dev] ================================================================
[dev] Everything is running.
[dev]   Backend:  http://127.0.0.1:8000/docs
[dev]   Frontend: http://127.0.0.1:5173/
[dev]   Demo login: demo@example.com / DemoPassword123!
[dev] Press Ctrl+C to stop both.
[dev] ================================================================
```

If `DATABASE_URL` isn't already set in your environment, it defaults to a
local sqlite file (`backend/var/dev.db`) and seeds the demo user below
automatically — no Postgres required for local dev. If you *have* set
`DATABASE_URL` (pointing at your own Postgres instance with migrations
already applied), `scripts/dev.py` leaves it alone and starts the backend
against it instead.

Backend and frontend output are streamed live, prefixed `[backend]` /
`[frontend]`, so a crash or exception from either is visible immediately in
the same terminal.

## How to stop

Press **Ctrl+C** in the terminal running `scripts/dev.py`. Both the backend
and frontend (and, on Windows, their full process trees — `npm` spawns
`node` as a child, and a plain `Ctrl+C` sent only to the top process leaves
that child running) are stopped before the script exits.

If a previous run ever gets killed some other way (window closed, terminal
crashed) and a later `python scripts/dev.py` reports a port already in use,
see Troubleshooting below.

## Demo credentials

Created automatically by `scripts/dev.py` on first run (via
`backend/scripts/seed_demo_user.py`, idempotent — safe to re-run, never
duplicates):

- **Email:** `demo@example.com`
- **Password:** `DemoPassword123!`

This account has a filing session already set up (filer category, residency,
consents) to walk the full guided journey end to end: log in → open the
filing session's questionnaire → upload a document (any PDF/JPEG/PNG) →
accept/edit the extracted fields → regime comparison → tax summary. There is
no registration UI in the frontend yet; `POST /api/v1/auth/register` is
available directly if you need a second account.

## Troubleshooting

**Login shows `Request failed with status 502`.** The Vite dev proxy
(`frontend/vite.config.ts`, `/api` → `http://localhost:8000` by default)
couldn't reach a backend at all — almost always because it isn't running, or
because it crashed and something is still holding the port. This is never a
bug in the frontend's auth code. Stop everything and use `python
scripts/dev.py`, which won't report the frontend as ready until the backend
has already answered a real health check — this specific failure mode isn't
reachable if you start through it.

**`scripts/dev.py` says a port is already in use.** A previous run wasn't
stopped cleanly (or something else is using 8000/5173). Find and stop it:

```
netstat -ano | findstr :8000
netstat -ano | findstr :5173
taskkill /PID <pid> /T /F
```

**`scripts/dev.py` says `backend/.venv not found`.** Run the one-time setup
above first.

**`scripts/dev.py` says `npm not found on PATH`.** Install
[Node.js](https://nodejs.org), then re-run.

**Backend or frontend crashes right after starting.** `scripts/dev.py`
prints the last ~20 lines of that process's own output before exiting —
that's the real error (a Python traceback for the backend, an npm/Vite error
for the frontend), not something this script is masking.

**Running the backend or frontend manually instead of through
`scripts/dev.py`** (e.g. for debugging one side in isolation):

```
# Backend
cd backend
set DATABASE_URL=sqlite:///./var/dev.db      # PowerShell: $env:DATABASE_URL=...
python scripts/seed_demo_user.py             # prints demo credentials
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Frontend (in a second terminal)
cd frontend
npm run dev
```

For a real Postgres instance instead of the sqlite dev convenience path, set
`DATABASE_URL` (env var or `backend/.env`, gitignored) and apply migrations
first: `alembic upgrade head`. `app/core/config.py` documents the default
connection string.

## Tests

```
# Backend
cd backend && .venv/Scripts/python.exe -m pytest app/tests -q --deselect app/tests/test_auth_postgres.py

# Frontend unit/component tests
cd frontend && npm run test

# Frontend E2E (spins up its own scratch backend + database automatically)
cd frontend && npx playwright test
```

`test_auth_postgres.py` requires a real running Postgres instance and is
excluded above for that reason; run it separately if Postgres is available.

## More detail

`CLAUDE.md` and `docs/` (`PRODUCT_SCOPE.md`, `ARCHITECTURE.md`,
`TAX_ENGINE_BOUNDARY.md`, `DATA_MODEL.md`, `IMPLEMENTATION_PLAN.md`,
`DECISIONS.md`) are the authoritative project references.
