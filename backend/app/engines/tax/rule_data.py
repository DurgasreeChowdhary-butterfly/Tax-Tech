"""FY 2025-26 / AY 2026-27 V1 tax rule data — old and new regime, salaried
individuals (Resident, not senior/super-senior — no age-banded slabs are
modeled in V1; docs/PRODUCT_SCOPE.md scopes salaried individuals only).

Every numeric rule below was verified against official Indian government
sources before being written here (per this session's tax-rule-sourcing
requirement) — no blog, tax-prep vendor site, or model memory was used as
authority. Sources, verified 2026-07-14:

- New + old regime slab rates, Section 87A rebate amounts/thresholds,
  Health & Education Cess rate (4%, both regimes):
  https://www.incometax.gov.in/iec/foportal/help/individual/return-applicable-1
  (Income Tax Department, "Salaried Individuals for AY 2026-27")

- New regime standard deduction (Rs. 75,000, raised by Budget 2025-26):
  https://www.pib.gov.in/PressReleasePage.aspx?PRID=2035605
  ("GOVERNMENT MAKES NEW TAX REGIME MORE ATTRACTIVE", PIB) and corroborated
  by the Rs. 12,75,000 nil-tax figure on the incometax.gov.in page above.

- Old regime standard deduction (Rs. 50,000, unchanged):
  https://www.incometax.gov.in/iec/foportal/help/new-tax-vs-old-tax-regime-faqs
  ("Standard deduction of Rs.50,000 or the amount of salary, whichever is
  lower, is available for both old and new tax regimes").

- Section 87A marginal relief for the new regime (Rs. 12,00,000 threshold)
  and the absence of marginal relief for the old regime's Rs. 5,00,000
  threshold (hard cutoff):
  https://www.incometaxindia.gov.in/w/section-87a-30
  https://www.incometaxindia.gov.in/w/what-is-rebate-under-section-87a-for-f.y-2025-26-and-who-can-claim-it-

- Section 80C cap (Rs. 1,50,000) and old-regime-only availability (new
  regime disallows Chapter VI-A deductions except 80CCD(2)/80CCH/80JJAA,
  none implemented in V1):
  https://www.incometaxindia.gov.in/w/section-80c
  https://www.incometaxindia.gov.in/w/deductions
  https://www.incometax.gov.in/iec/foportal/help/new-tax-vs-old-tax-regime-faqs

- Section 288A / 288B rounding (nearest Rs. 10, paise ignored — see
  app/engines/tax/rounding.py for the full citation).

Deliberately NOT modeled in V1 (see Phase 9 report for the full rationale):
surcharge (any regime, any threshold), any Chapter VI-A deduction other than
80C (80D, 80CCD(2), 80E, 80G, 80TTA/80TTB, HRA u/s 10(13A), etc.), senior/
super-senior citizen slabs, and any income type the Supported Case Validator
(Phase 8) already routes to REVIEW_REQUIRED/NOT_SUPPORTED.
"""

from app.models.enums import TaxRegime, TaxRuleType

ASSESSMENT_YEAR = "2026-27"
ENGINE_VERSION = "v1"

_VERIFIED_ON = "2026-07-14"


def _rule(regime: TaxRegime, rule_type: TaxRuleType, code: str, order_index: int, **parameters) -> dict:
    return {
        "regime": regime,
        "rule_type": rule_type,
        "code": code,
        "order_index": order_index,
        "parameters": {**parameters, "verified_on": _VERIFIED_ON},
    }


FY_2025_26_RULES: list[dict] = [
    # --- New regime (Section 115BAC(1A)) slabs ---
    _rule(TaxRegime.NEW, TaxRuleType.SLAB, "SLAB_1", 1, min="0.00", max="400000.00", rate="0.00",
          source="incometax.gov.in/iec/foportal/help/individual/return-applicable-1"),
    _rule(TaxRegime.NEW, TaxRuleType.SLAB, "SLAB_2", 2, min="400000.00", max="800000.00", rate="0.05",
          source="incometax.gov.in/iec/foportal/help/individual/return-applicable-1"),
    _rule(TaxRegime.NEW, TaxRuleType.SLAB, "SLAB_3", 3, min="800000.00", max="1200000.00", rate="0.10",
          source="incometax.gov.in/iec/foportal/help/individual/return-applicable-1"),
    _rule(TaxRegime.NEW, TaxRuleType.SLAB, "SLAB_4", 4, min="1200000.00", max="1600000.00", rate="0.15",
          source="incometax.gov.in/iec/foportal/help/individual/return-applicable-1"),
    _rule(TaxRegime.NEW, TaxRuleType.SLAB, "SLAB_5", 5, min="1600000.00", max="2000000.00", rate="0.20",
          source="incometax.gov.in/iec/foportal/help/individual/return-applicable-1"),
    _rule(TaxRegime.NEW, TaxRuleType.SLAB, "SLAB_6", 6, min="2000000.00", max="2400000.00", rate="0.25",
          source="incometax.gov.in/iec/foportal/help/individual/return-applicable-1"),
    _rule(TaxRegime.NEW, TaxRuleType.SLAB, "SLAB_7", 7, min="2400000.00", max=None, rate="0.30",
          source="incometax.gov.in/iec/foportal/help/individual/return-applicable-1"),
    _rule(TaxRegime.NEW, TaxRuleType.DEDUCTION, "STANDARD_DEDUCTION", 1, amount="75000.00",
          source="pib.gov.in/PressReleasePage.aspx?PRID=2035605"),
    _rule(TaxRegime.NEW, TaxRuleType.REBATE, "SECTION_87A", 1, threshold="1200000.00", max_rebate="60000.00",
          marginal_relief=True,
          source="incometaxindia.gov.in/w/section-87a-30; incometaxindia.gov.in/w/what-is-rebate-under-section-87a-for-f.y-2025-26-and-who-can-claim-it-"),
    _rule(TaxRegime.NEW, TaxRuleType.CESS, "HEALTH_EDUCATION_CESS", 1, rate="0.04",
          source="incometax.gov.in/iec/foportal/help/individual/return-applicable-1"),

    # --- Old regime slabs (individual, resident, non-senior) ---
    _rule(TaxRegime.OLD, TaxRuleType.SLAB, "SLAB_1", 1, min="0.00", max="250000.00", rate="0.00",
          source="incometax.gov.in/iec/foportal/help/individual/return-applicable-1"),
    _rule(TaxRegime.OLD, TaxRuleType.SLAB, "SLAB_2", 2, min="250000.00", max="500000.00", rate="0.05",
          source="incometax.gov.in/iec/foportal/help/individual/return-applicable-1"),
    _rule(TaxRegime.OLD, TaxRuleType.SLAB, "SLAB_3", 3, min="500000.00", max="1000000.00", rate="0.20",
          source="incometax.gov.in/iec/foportal/help/individual/return-applicable-1"),
    _rule(TaxRegime.OLD, TaxRuleType.SLAB, "SLAB_4", 4, min="1000000.00", max=None, rate="0.30",
          source="incometax.gov.in/iec/foportal/help/individual/return-applicable-1"),
    _rule(TaxRegime.OLD, TaxRuleType.DEDUCTION, "STANDARD_DEDUCTION", 1, amount="50000.00",
          source="incometax.gov.in/iec/foportal/help/new-tax-vs-old-tax-regime-faqs"),
    _rule(TaxRegime.OLD, TaxRuleType.REBATE, "SECTION_87A", 1, threshold="500000.00", max_rebate="12500.00",
          marginal_relief=False,
          source="incometaxindia.gov.in/w/what-is-rebate-under-section-87a-for-f.y-2025-26-and-who-can-claim-it-"),
    _rule(TaxRegime.OLD, TaxRuleType.CESS, "HEALTH_EDUCATION_CESS", 1, rate="0.04",
          source="incometax.gov.in/iec/foportal/help/individual/return-applicable-1"),
    _rule(TaxRegime.OLD, TaxRuleType.DEDUCTION, "SECTION_80C", 2, cap="150000.00",
          source="incometaxindia.gov.in/w/section-80c; incometaxindia.gov.in/w/deductions"),
]


def seed_fy_2025_26_v1_rule_set(db):
    """Creates, populates, and publishes the FY 2025-26/AY 2026-27 V1 tax
    rule set from FY_2025_26_RULES. This is the "explicit controlled
    publication mechanism" for V1 rule sets — never invoked automatically by
    a migration (a mistake discovered later must ship as a new version, not
    an edit to an already-published row; baking it into migration DDL would
    make that harder, not easier)."""
    from app.repositories import tax_rule_set as tax_rule_set_repo

    rule_set = tax_rule_set_repo.create_tax_rule_set(
        db, assessment_year=ASSESSMENT_YEAR, engine_version=ENGINE_VERSION
    )
    for rule in FY_2025_26_RULES:
        tax_rule_set_repo.add_tax_rule(
            db,
            rule_set,
            regime=rule["regime"],
            rule_type=rule["rule_type"],
            code=rule["code"],
            order_index=rule["order_index"],
            parameters=rule["parameters"],
        )
    return tax_rule_set_repo.publish_tax_rule_set(db, rule_set)
