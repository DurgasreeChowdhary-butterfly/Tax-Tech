# ITR Filing

Mobile-first, API-first guided income-tax preparation platform for Indian
salaried individuals (V1: FY 2025-26 / AY 2026-27). See `docs/PRODUCT_SCOPE.md`
for scope and `docs/ARCHITECTURE.md` for the system shape. **V1 does not file
directly to the Income Tax portal.**

## Running locally

The backend and frontend are two separate processes. **The backend must be
running before the frontend can log in** — if the browser shows `Request
failed with status 502` on login, it means the Vite dev proxy
(`frontend/vite.config.ts`, `/api` → `http://localhost:8000` by default)
couldn't reach a backend at all, almost always because it isn't running yet.
A 502 from this proxy is never a bug in the frontend's auth code — start the
backend first and it goes away.

### 1. Backend

```
cd backend
python -m venv .venv
.venv/Scripts/activate   # .venv/bin/activate on macOS/Linux
pip install -r requirements.txt -r requirements-dev.txt
```

The backend needs a database. `app/core/config.py` defaults to Postgres
(`postgresql+psycopg2://postgres:postgres@localhost:5432/itr_filing`) — set
`DATABASE_URL` (env var or `backend/.env`, gitignored) to point at your own
instance, then apply migrations:

```
alembic upgrade head
```

For local/demo use without a Postgres server, point `DATABASE_URL` at a
sqlite file instead (the app creates the schema itself via
`Base.metadata.create_all`, so no migration step is needed in this mode):

```
set DATABASE_URL=sqlite:///./var/dev.db      # PowerShell: $env:DATABASE_URL=...
python scripts/seed_demo_user.py             # prints demo credentials — see below
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`scripts/seed_demo_user.py` is idempotent — safe to re-run, it never creates
duplicates. There is no registration UI in the frontend yet, so this script
(or `POST /api/v1/auth/register` directly) is the supported way to get a
login.

### 2. Frontend

```
cd frontend
npm install
npm run dev
```

Open the URL Vite prints (`http://localhost:5173`) and log in.

## Demo credentials

`python backend/scripts/seed_demo_user.py` (re-runnable, idempotent) creates:

- **Email:** `demo@example.com`
- **Password:** `DemoPassword123!`

This account has a filing session already set up (filer category, residency,
consents) to walk the full guided journey end to end: log in → open the
filing session's questionnaire → upload a document (any PDF/JPEG/PNG) →
accept/edit the extracted fields → regime comparison → tax summary.

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
