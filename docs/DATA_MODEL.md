# Data Model

Proposed tables and relationships. No SQLAlchemy models yet — this is planning only
(Phase 0). Actual models are implemented per `docs/IMPLEMENTATION_PLAN.md`.

## Identity & profile

- `users` — auth identity.
- `user_profiles` — general personal details (name, DOB, contact) supporting the
  questionnaire and eventual summary output. One per user.
- `tax_profiles` — protected taxpayer identity (PAN). Stable per user, not
  assessment-year-specific — a PAN doesn't change year to year, so it does not
  belong on a per-AY record. One per user.

## Filing workflow

- `filing_sessions` — one per user per assessment year attempt; holds current
  status, complexity classification, **and assessment-year-specific tax context
  (residency status, filer category)** — these can legitimately differ between
  assessment years and belong with the per-AY workflow record, not with the
  stable taxpayer identity in `tax_profiles`. Links everything else together.
  This is the resumable unit referenced in the mobile requirements (server-side
  state).
- `filing_flags` — `REVIEW_REQUIRED` / `NOT_SUPPORTED` / other blocking markers
  raised by the Decision Engine or Supported Case Validator, tied to a
  `filing_session`.

## Questionnaire (versioned, immutable once published)

- `questionnaire_versions` — a published, immutable snapshot of question graph +
  routing config for a given assessment year. New edits = new version row.
- `questions` — belongs to a `questionnaire_version`; type is one of
  `SINGLE_CHOICE, MULTI_CHOICE, BOOLEAN, CURRENCY, NUMBER, DATE, TEXT,
  DOCUMENT_UPLOAD, INFORMATION, REVIEW_CARD`.
- `question_options` — options for choice-type questions.
- `question_rules` — routing/decision rules attached to a question or answer value
  (`SHOW_QUESTION, SKIP_QUESTION, GO_TO_QUESTION, SET_PROFILE_FLAG, SET_COMPLEXITY,
  REQUIRE_REVIEW, END_FLOW`).
- `question_answers` — **immutable, append-only history**. Each new answer to a
  question is a new row (with timestamp + supersedes pointer), not an update, so
  answer history is fully auditable. "Current answer" is the latest row per
  `(filing_session, question)`.

## Income & deductions (verified domain data — post extraction/confirmation only)

- `filing_income_sources` — index of income sources attached to a filing session
  (salary, interest, etc.).
- `employers` — employer records per filing session (supports multiple employers).
- `salary_income` — verified salary figures per employer, sourced from confirmed
  Form 16 extraction or manual entry.
- `interest_income` — verified savings/FD interest entries.
- `deductions` — claimed deduction entries; stores `claimed_amount` distinct from
  engine-computed `eligible_amount`/`applied_amount` (see
  `docs/TAX_ENGINE_BOUNDARY.md`).

## Documents & extraction (raw → verified boundary)

- `tax_documents` — uploaded file metadata + private object storage pointer (never
  a public URL).
- `document_processing_jobs` — async job tracking for OCR/AI processing.
- `document_extractions` — raw extraction result per document/job, provenance-
  tagged (model/provider/version), never directly readable by the tax engine.
- `extracted_fields` — individual field-level candidates with confidence scores;
  linked to the domain record they become once user-confirmed.

## Tax rules & calculations (versioned, immutable once published)

- `tax_rule_sets` — one per financial year/assessment year (+ engine version),
  published immutably.
- `tax_rules` — individual slab/rebate/surcharge/cess/deduction rules belonging to
  a rule set.
- `tax_calculations` — one row per calculation run; references the exact
  `tax_rule_set` version and engine version used. Never updated in place — a
  recalculation is a new row.
- `calculation_line_items` — itemized breakdown belonging to a `tax_calculation`
  (income components, deduction applied amounts, slab tax, rebate, cess, credits).

## Consent & audit

- `consent_definitions` — versioned text/purpose of each consent type (e.g. data
  processing, document storage).
- `user_consents` — per-user acceptance record, linked to a `consent_definitions`
  version and timestamp.
- `audit_logs` — append-only log of financial data changes, calculation runs, and
  admin access to user cases. Never mutated or deleted.

## Admin

- Admin users are a distinct principal type (not just a `users` role flag) so that
  admin case access is separately auditable via `audit_logs`, per principle 11.

## Immutable / versioned records summary

| Concept | Versioned/immutable how |
|---|---|
| `questionnaire_versions` | new version row per published change |
| `question_answers` | append-only history, no updates |
| `tax_rule_sets` / `tax_rules` | published immutably per FY/AY |
| `tax_calculations` | new row per run, never overwritten |
| `audit_logs` | append-only |

## Sensitive-data notes

- PAN, income figures, and uploaded documents are sensitive PII/financial data.
- Documents live only in private object storage; DB stores pointers, not files.
- All monetary columns are NUMERIC/Decimal, never float (principle 13).
- Access to another user's filing data (by admins/support) must be logged via
  `audit_logs`, not just permitted by role.
