# Architecture

See `docs/PRODUCT_SCOPE.md` for what the system does; this document covers how it's built.

## Shape

Modular monolith, not microservices (rationale: `docs/DECISIONS.md`).

```
Mobile-first React Web / Future Mobile App
                |
          Versioned REST API
              /api/v1
                |
       FastAPI Modular Monolith
                |
Authentication | Filing Workflow | Questionnaire Engine | Decision Engine
Document Service | Extraction Service | Tax Engine | Consent Service | Audit Service
                |
PostgreSQL / Private Object Storage / Background Jobs
```

## Backend responsibilities (source of truth)

All business logic, questionnaire routing, tax calculation, validation, and audit
logging live here. The frontend never makes tax or routing decisions.

Directory direction:

```
backend/app/
  api/v1/          # versioned REST endpoints only, thin controllers
  core/            # config, security, shared infra
  models/          # SQLAlchemy ORM models
  schemas/         # Pydantic request/response schemas
  repositories/    # data access
  services/        # orchestration: filing workflow, document service, consent, audit
  engines/
    questionnaire/ # question graph, versioned config, answer capture
    decision/      # routing/decision rule evaluation (SET_FLAG, SKIP, etc.)
    tax/           # deterministic tax calculation engine
    extraction/    # normalization/validation of AI/OCR output before domain entry
  integrations/
    ai/            # LLM provider adapters (extraction assistance only)
    ocr/           # OCR provider adapters
    storage/       # private object storage adapters
  workers/         # async job handlers (document processing, etc.)
  audit/           # audit event emission/query
  tests/
```

## Frontend responsibilities

Rendering, one-question-per-screen UX, calling the versioned API, displaying
extraction review cards, and displaying the tax summary. No tax logic, no
questionnaire routing logic — both are fetched from backend config/API responses.

Directory direction:

```
frontend/src/
  api/            # typed API client
  components/     # shared UI
  features/
    auth/
    filing/
    questionnaire/
    documents/
    review/
    tax-summary/
  hooks/
  layouts/
  routes/
  stores/
  types/
  utils/
```

## Future mobile app compatibility

- All product logic is reachable only via `/api/v1`. No logic embedded in the web
  client that a React Native client couldn't also rely on.
- Auth is token-based (JWT, added later) rather than cookie/session tied to browser
  behavior, so it works identically from a mobile app.
- Filing/questionnaire state is persisted server-side per `filing_session`, not in
  browser storage, so the same session can resume on a different device or client.

## Module boundaries

- **Questionnaire Engine**: owns question graph, versions, and per-user answer
  history. Does not decide tax outcomes.
- **Decision Engine**: evaluates routing/flag rules (complexity routing, profile
  flags, skip logic) against answers. Does not calculate tax.
- **Document Service**: upload, storage pointers, job orchestration. Does not
  interpret document contents.
- **Extraction Service**: runs AI/OCR adapters, produces extraction records with
  confidence scores; never writes directly to domain income/deduction tables.
- **Tax Engine**: consumes only verified domain records (post user-confirmation),
  runs the Supported Case Validator, then the deterministic calculation pipeline.
  See `docs/TAX_ENGINE_BOUNDARY.md`.
- **Consent Service** / **Audit Service**: cross-cutting, called by the above; not
  bypassable.

## Async document processing direction

Document upload → `document_processing_job` enqueued (Redis-backed worker, added
later) → OCR/AI adapter runs → `document_extraction` + `extracted_fields` written
→ user reviews/corrects via extraction review cards → confirmed values become
verified domain records (e.g. `salary_income`) → available to the tax engine.
Processing is async so slow/unreliable mobile uploads don't block the UI thread or
require a persistent connection.
