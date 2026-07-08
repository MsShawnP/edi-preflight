"""Amazon-specific 856 ASN validation (layer 3).

Amazon Vendor Central compliance checks. Uses standard S→O→T→P→I
hierarchy with Amazon's chargeback fee schedule.
"""

from __future__ import annotations

from src.validate_856 import ValidationResult
from src.validate_856_common import RetailerConfig, run_retailer_checks

_FEES = {
    "missing_sscc18": {"fee": 50.00, "per": "case"},
    "invalid_sscc18_format": {"fee": 50.00, "per": "case"},
    "wrong_hl_hierarchy": {"fee": 0.00, "per": "document"},
    "missing_catch_weight": {"fee": 50.00, "per": "item"},
    "missing_po_reference": {"fee": 0.00, "per": "order"},
    "missing_ship_to": {"fee": 0.00, "per": "document"},
    "missing_ship_date": {"fee": 0.00, "per": "document"},
    "missing_carrier": {"fee": 0.00, "per": "document"},
}

_CONFIG = RetailerConfig(
    name="Amazon",
    fees=_FEES,
    # Amazon accepts Original and Replace (see rules/amazon_856.yaml BSN01).
    allowed_bsn_purpose_codes={"00", "05"},
)


def validate_856_amazon(result: ValidationResult) -> ValidationResult:
    """Add Amazon-specific validation findings to an existing ValidationResult."""
    return run_retailer_checks(result, _CONFIG)
