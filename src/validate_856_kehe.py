"""KeHE-specific 856 ASN validation (layer 3).

KeHE Distributors compliance checks. Standard S→O→I→P hierarchy
with moderate chargeback enforcement.
"""

from __future__ import annotations

from src.validate_856 import ValidationResult
from src.validate_856_common import RetailerConfig, run_retailer_checks

_FEES = {
    "missing_sscc18": {"fee": 75.00, "per": "case"},
    "invalid_sscc18_format": {"fee": 75.00, "per": "case"},
    "wrong_hl_hierarchy": {"fee": 0.00, "per": "document"},
    "missing_catch_weight": {"fee": 75.00, "per": "item"},
    "missing_po_reference": {"fee": 0.00, "per": "order"},
    "missing_ship_to": {"fee": 0.00, "per": "document"},
    "missing_ship_date": {"fee": 0.00, "per": "document"},
    "missing_carrier": {"fee": 0.00, "per": "document"},
}

_CONFIG = RetailerConfig(
    name="KeHE",
    fees=_FEES,
    # KeHE accepts Original only (see rules/kehe_856.yaml BSN01).
    allowed_bsn_purpose_codes={"00"},
)


def validate_856_kehe(result: ValidationResult) -> ValidationResult:
    """Add KeHE-specific validation findings to an existing ValidationResult."""
    return run_retailer_checks(result, _CONFIG)
