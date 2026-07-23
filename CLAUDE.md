# CLAUDE.md

Instructions for any Claude Code session working in this repository.

## Before doing anything

1. Read `docs/PRODUCT_SCOPE.md`, `docs/ARCHITECTURE.md`, `docs/TAX_ENGINE_BOUNDARY.md`,
   `docs/DATA_MODEL.md`, `docs/IMPLEMENTATION_PLAN.md`, `docs/DECISIONS.md` — whichever
   are relevant to the task — before asking the user for context or regenerating it.
2. Inspect existing code/config in the repo before assuming something doesn't exist.
3. Do not restate the full project specification back to the user. Report only:
   files changed, key decisions made, tests/verification performed, blockers,
   and recommended next step/phase.

## What this project is

Mobile-first, API-first guided income-tax preparation platform for Indian salaried
individuals. V1 target: FY 2025-26 / AY 2026-27. See `docs/PRODUCT_SCOPE.md` for
full scope. **V1 is not direct ITR filing.**

## Non-negotiable safety boundaries

- No direct filing to the Income Tax portal in V1. No Selenium/portal automation, ever.
- AI/LLM output never feeds a tax calculation directly. Raw extraction must pass
  normalization → validation → user confirmation before becoming a verified domain
  record usable by the tax engine. See `docs/TAX_ENGINE_BOUNDARY.md`.
- Tax calculations are deterministic, versioned, and implemented only in the backend
  tax engine (`backend/app/engines/tax/`). Never in the frontend, never via AI.
- Unsupported tax situations are blocked or routed to review — never guessed or
  silently approximated.
- All monetary values use Decimal/NUMERIC. Never float.
- Tax/questionnaire rule versions, once published, are immutable — corrections are
  new versions, not edits.
- Financial data changes and tax calculations must be audit-logged.
- Private tax documents are stored in private object storage only — never public URLs.
- Questionnaire routing logic lives in backend versioned config, not the frontend.

## Architecture rules

- Modular monolith (FastAPI), not microservices. See `docs/ARCHITECTURE.md`.
- Backend is the single source of truth; frontend and any future React Native app
  consume the same versioned REST API (`/api/v1`).
- Follow the backend/frontend directory structure in `docs/ARCHITECTURE.md`.

## Coding rules

- No speculative code or boilerplate ahead of the phase currently being built.
- Follow `docs/IMPLEMENTATION_PLAN.md` phase-by-phase; do not skip ahead.
- Each phase must meet its exit criteria and tests before starting the next.
- Prefer editing/extending existing modules over introducing new abstractions.

## Current status

Phases 0-13 complete (backend: identity/session, questionnaire + decision engines,
documents, async extraction, verification, tax rule sets + Supported Case
Validator, deterministic tax calculation engine, consent + audit, JWT auth;
frontend: mobile-first React shell, questionnaire runner, extraction review UI,
regime comparison, tax summary). See `docs/IMPLEMENTATION_PLAN.md` for what each
phase covered and what Phase 14+ (not yet scoped) would need to define first.
See the top-level `README.md` for how to run the app locally and demo credentials.
