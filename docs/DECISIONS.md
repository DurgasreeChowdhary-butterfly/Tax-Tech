# Architecture Decision Log

Concise record of current decisions and reasons. Add new entries at the bottom with
a date; do not delete superseded entries — mark them superseded instead.

## 2026-07-13 — PostgreSQL over MongoDB

Financial/tax domain data is inherently relational (users → filing sessions →
income sources → deductions → calculations, all versioned and cross-referenced).
Strong schema, transactional integrity, and NUMERIC types for money outweigh
document-store flexibility here. See `docs/DATA_MODEL.md`.

## 2026-07-13 — Modular monolith over microservices

Premature microservices add operational and consistency overhead the team doesn't
need at V1 scale. A modular monolith (`docs/ARCHITECTURE.md`) gives clean module
boundaries (questionnaire, decision, tax engine, documents, extraction, consent,
audit) without distributed-systems cost. Split out later only if a module
demonstrably needs independent scaling/deployment.

## 2026-07-13 — API-first

All product logic is exposed via versioned REST (`/api/v1`) so the current React
web client and a future React Native client share the exact same backend contract
and business logic, with zero duplicated tax/routing logic in either client.

## 2026-07-13 — Mobile-first web

Primary users are first-time/confused filers on phones, often on slow or
interrupted connections. One-question-per-screen UX and server-side session state
(not localStorage) follow directly from this. See `docs/PRODUCT_SCOPE.md` mobile
journey section.

## 2026-07-13 — Deterministic, versioned tax engine; AI excluded from calculation

Tax calculations must be correct, reproducible, and auditable — properties LLMs do
not reliably provide. AI is scoped to document extraction assistance and plain-
language explanations only, with a mandatory user-confirmation checkpoint before
any AI-touched value can reach the tax engine. See `docs/TAX_ENGINE_BOUNDARY.md`.

## 2026-07-13 — No direct filing in V1

Direct filing carries legal/compliance weight (portal integration, e-verification,
liability for incorrect submission) disproportionate to a V1 aimed at guided
preparation and estimation. V1 explicitly stops at a structured summary. Selenium-
based portal automation is excluded outright, in any phase, as an anti-pattern
(fragile, ToS-risk, and a poor substitute for a real filing integration if pursued
later). Revisit direct filing only as a deliberate, separately-scoped future
decision — not an incremental addition to V1.
