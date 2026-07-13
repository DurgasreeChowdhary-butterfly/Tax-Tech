# Implementation Plan

Phased build plan. Each phase must meet its exit criteria (verified by its listed
tests) before the next phase starts. Keep phases small enough to verify empirically.
Cross-references: `docs/ARCHITECTURE.md`, `docs/DATA_MODEL.md`,
`docs/TAX_ENGINE_BOUNDARY.md`.

## Phase 0 — Repository knowledge & planning (this phase)

**Goal:** Produce `CLAUDE.md` + `docs/*` so future sessions don't need the full spec restated.
**Exit criteria:** All 7 documents exist, are internally consistent, and a
verification pass confirms no contradictions.
**Tests:** None (no code). Verification is a documentation self-review (see report).
**Status:** Complete.

## Phase 1 — Backend skeleton

**Goal:** Initialize FastAPI project skeleton with the directory structure from
`docs/ARCHITECTURE.md`, health-check endpoint under `/api/v1`, config/env loading,
PostgreSQL connection via SQLAlchemy, Alembic wired up with an empty baseline
migration.
**Exit criteria:** App boots, `/api/v1/health` returns 200, Alembic can migrate an
empty DB up/down.
**Tests:** One integration test hitting `/api/v1/health`; one test asserting Alembic
migration applies cleanly.

## Phase 2 — Core identity & session models

**Goal:** Implement `users`, `user_profiles`, `tax_profiles`, `filing_sessions`
models/migrations/repositories (per `docs/DATA_MODEL.md`). No auth yet — internal
service-level creation only.
**Exit criteria:** CRUD via repository layer, migrations reversible.
**Tests:** Repository unit tests for create/read/update per model; migration
up/down test.

## Phase 3 — Questionnaire engine (versioned)

**Goal:** `questionnaire_versions`, `questions`, `question_options`,
`question_rules`, `question_answers` (immutable history). Backend endpoints to
fetch current question for a session and submit an answer (creates new answer row,
never updates).
**Exit criteria:** A hardcoded minimal question graph (2-3 questions) can be walked
end-to-end via API calls only; answer history is append-only and queryable.
**Tests:** Unit tests for answer immutability (submitting twice creates two rows);
API test walking the mini graph.

## Phase 4 — Decision engine

**Goal:** Rule evaluation for `SHOW_QUESTION, SKIP_QUESTION, GO_TO_QUESTION,
SET_PROFILE_FLAG, SET_COMPLEXITY, REQUIRE_REVIEW, END_FLOW` against answers.
**Exit criteria:** Given a fixed rule set and answer sequence, routing output is
deterministic and matches expected fixtures.
**Tests:** Table-driven unit tests covering each decision action type.

## Phase 5 — Document service + storage integration

**Goal:** `tax_documents` model, private object storage adapter (S3-compatible),
upload endpoint issuing private (non-public) storage references.
**Exit criteria:** Upload → stored privately → retrievable only via authenticated
backend-mediated access, never a public URL.
**Tests:** Test asserting stored object is not reachable via a public/unsigned URL;
upload/download round-trip test.

## Phase 6 — Async extraction pipeline (document → extraction record)

**Goal:** `document_processing_jobs`, `document_extractions`, `extracted_fields`.
Background worker (can start synchronous/in-process; Redis-backed queue added when
needed) invokes an OCR/AI adapter (mockable) and writes extraction records only —
never writes to domain tables directly.
**Exit criteria:** Given a sample Form 16-like input, an extraction record with
field-level confidence is produced; no domain table is touched by this phase.
**Tests:** Unit test asserting the extraction path has no write access to
`salary_income`/domain tables; adapter is mocked for deterministic test output.

## Phase 7 — Extraction review & verified domain records

**Goal:** API + minimal logic for user to confirm/correct `extracted_fields` into
verified `salary_income` / `interest_income` records.
**Exit criteria:** Only user-confirmed data reaches domain tables; raw extraction
values never appear in domain tables unmodified without confirmation step having run.
**Tests:** Test that confirming an extraction writes a domain record with a
provenance link back to the extraction; test that an unconfirmed extraction cannot
be read by the tax engine layer (import/dependency-boundary test).

## Phase 8 — Tax rule sets & Supported Case Validator

**Goal:** `tax_rule_sets`, `tax_rules` for FY 2025-26/AY 2026-27 (old + new regime,
supported deductions only). Implement Supported Case Validator returning
`SUPPORTED / REVIEW_REQUIRED / NOT_SUPPORTED / INCOMPLETE`.
**Exit criteria:** Validator correctly classifies a set of fixture scenarios
(salaried single employer = SUPPORTED; freelance income present = NOT_SUPPORTED; etc).
**Tests:** Table-driven tests per `docs/PRODUCT_SCOPE.md` supported/excluded list.

## Phase 9 — Deterministic tax calculation engine

**Goal:** Full calculation pipeline per `docs/TAX_ENGINE_BOUNDARY.md` for
`SUPPORTED` cases only. `tax_calculations`, `calculation_line_items`. Decimal
arithmetic throughout.
**Exit criteria:** Given known salary/deduction fixtures, output matches
hand-calculated expected tax for both regimes; calculation is reproducible
(same inputs + rule set version → identical output) and persisted as a new
version each run.
**Tests:** Golden-fixture tests for old regime, new regime, multi-employer,
each supported deduction; a determinism test (run twice, compare).

## Phase 10 — Consent & audit services

**Goal:** `consent_definitions`, `user_consents`, `audit_logs`. Wire audit
emission into filing/document/calculation write paths.
**Exit criteria:** Every financial data mutation and calculation run produces an
audit_log entry; consent must be recorded before document upload/processing proceeds.
**Tests:** Test that upload without consent is rejected; test that each mutation
path emits exactly one audit event.

## Phase 11 — Auth (JWT)

**Goal:** JWT-based authentication across `/api/v1`, replacing internal-only access
from earlier phases.
**Exit criteria:** All endpoints require auth except health check; tokens scoped
per user.
**Tests:** Authz tests per endpoint; token expiry/refresh test.

## Phase 12 — Frontend skeleton (mobile-first React)

**Goal:** Vite + React + TS + Tailwind scaffold, API client, one-question-per-screen
questionnaire runner driven entirely by backend responses (no hardcoded routing).
**Exit criteria:** A user can walk the Phase 3 mini question graph from a mobile
viewport end-to-end against the real backend.
**Tests:** Component tests for question renderer per question type; one E2E
happy-path test.

## Phase 13 — Extraction review UI + regime comparison + tax summary UI

**Goal:** Review cards for extraction confirmation, regime comparison view,
final tax summary screen.
**Exit criteria:** Full guided journey from `docs/PRODUCT_SCOPE.md` walkable on a
mobile viewport against a `SUPPORTED` fixture case, ending in a tax summary.
**Tests:** E2E test of the full journey; visual/responsive check on mobile viewport.

---

Later phases (background job infra with Redis, admin case-review tooling, additional
income types/deductions, React Native client) are deliberately not detailed yet —
plan them when their preceding phases are done and scope is confirmed.
