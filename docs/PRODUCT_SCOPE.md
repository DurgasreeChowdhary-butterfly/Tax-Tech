# Product Scope

## V1 target

FY 2025-26 / AY 2026-27. Indian salaried individual taxpayers.

## Supported scenarios

- First-time or confused tax filers who don't understand tax terminology
- Salaried individuals with one or multiple employers
- Form 16 upload and guided data extraction
- Savings bank interest income (supported categories only)
- Fixed deposit interest income (supported categories only)
- Explicitly implemented deduction rules (defined in versioned tax rule sets, not
  an open-ended list — see `docs/TAX_ENGINE_BOUNDARY.md`)
- Old vs. new regime comparison (supported regimes only)
- Supported TDS / tax-credit inputs
- Output: a structured tax preparation summary (estimate), not a filed return

## Explicitly out of scope for V1 (excluded or routed to review)

These must produce a `REVIEW_REQUIRED` or `NOT_SUPPORTED` flag, never a guessed number:

- Direct filing to the Income Tax portal (out of scope entirely, all versions until
  explicitly revisited)
- Freelance / professional income
- Business income
- Capital gains not explicitly modeled as supported
- Crypto / virtual digital assets
- Foreign income or foreign assets
- Residency-status uncertainty (RNOR/NR edge cases)
- Any income type or deduction not present in the current published tax rule set

## Mobile-first user journey

One primary question per screen. Typical flow:

```
Welcome
→ filing intent
→ income period
→ taxpayer context
→ income discovery
→ complexity routing
→ salary questions
→ Form 16 upload
→ extraction review cards
→ bank interest questions
→ dynamically applicable tax questions
→ regime comparison
→ completeness checkpoint
→ tax summary
```

Assume slow/interrupted connectivity, browser closures, device switching, and users
returning days later. All workflow state is server-side (see
`docs/ARCHITECTURE.md` mobile/session notes) — never relied upon from localStorage.

## Product boundaries

- The product prepares and estimates; it does not file.
- Complexity routing and the Supported Case Validator (`docs/TAX_ENGINE_BOUNDARY.md`)
  are the mechanism that keeps unsupported cases out of a final calculation.
- Scope expansion (new income types, deductions, regimes) happens by publishing new
  versioned tax rule sets / questionnaire versions, not by editing this document's
  assumptions into code directly.
