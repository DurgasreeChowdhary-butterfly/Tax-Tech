# Tax Engine Boundary

Authoritative rules for what may and may not compute a tax result. See
`docs/ARCHITECTURE.md` for where the engine lives (`backend/app/engines/tax/`).

## Core rule

**AI is not the tax calculator.** AI/OCR may assist document extraction and produce
plain-language explanations only. Raw AI/LLM output must never be passed directly
into a tax calculation. A failure or low-confidence result from AI must degrade to
"needs user review," never to a guessed or silently substituted number, and must
never crash or corrupt a deterministic calculation already in progress.

## Document verification boundary (extraction → domain)

```
Document
→ parser/OCR/AI candidate extraction
→ extraction record          (raw, provenance-tagged, never trusted)
→ normalization               (units, formats, currency)
→ validation                  (range/consistency checks)
→ confidence scoring
→ user confirmation/correction (mandatory human checkpoint)
→ verified domain record       (e.g. salary_income, interest_income)
→ tax engine
```

Never: `LLM JSON → tax calculator`. Only verified domain records (post user
confirmation) are readable by the tax engine.

## Supported Case Validator

Runs before any calculation. Outcomes:

- `SUPPORTED` — proceed to full calculation
- `REVIEW_REQUIRED` — human review needed; no final estimate produced
- `NOT_SUPPORTED` — scenario outside V1 scope (see `docs/PRODUCT_SCOPE.md` exclusions)
- `INCOMPLETE` — required inputs missing; ask more questions

Only `SUPPORTED` cases receive a complete V1 estimate. The other three states block
calculation and surface a `filing_flag` instead of a number.

## Calculation pipeline

```
Load filing session
→ resolve assessment year
→ load published rule set
→ supported-case validation
→ load verified income
→ load verified tax credits
→ load deduction claims
→ validate required inputs
→ calculate income components
→ gross total income
→ evaluate deductions
→ taxable income
→ slab rules
→ supported rebate rules
→ supported surcharge rules (only if explicitly implemented)
→ cess
→ final tax liability
→ verified tax credits
→ estimated refund/tax payable
→ calculation line items
→ persist calculation version
→ audit event
```

The engine is deterministic and versioned: same inputs + same rule set version +
same engine version = same output, reproducible after the fact.

## Amount distinctions

The engine must always distinguish, per deduction/credit:

- `CLAIMED_AMOUNT` — what the user entered/claimed
- `ELIGIBLE_AMOUNT` — what the rule set permits given the facts
- `APPLIED_AMOUNT` — what was actually used in the calculation

These are stored separately (not collapsed into one number) so calculations remain
auditable and explainable.

## Rule and calculation versioning

- Tax rules are grouped into `tax_rule_sets`, scoped by financial year/assessment
  year, and published as immutable once live (`docs/DATA_MODEL.md`).
- Every calculation run persists as a `tax_calculation` version referencing the
  exact rule set version and engine version used — never overwritten in place.
- Corrections to rules or calculation logic ship as new versions.

## Blocking/review behavior

- `REVIEW_REQUIRED` and `NOT_SUPPORTED` results create a `filing_flag` on the
  filing session and stop the pipeline before producing a tax number.
- The user sees a clear message that their situation needs manual review / is not
  yet supported — never a partial or best-guess tax figure.
- Admin/reviewer access to flagged cases must itself be auditable
  (`docs/DATA_MODEL.md` — admin/audit notes).
