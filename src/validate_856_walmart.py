"""Walmart-specific 856 ASN validation (layer 3).

Uses the shared retailer validation framework with Walmart's
chargeback fee schedule and strict S→O→T→P→I hierarchy.
"""

from __future__ import annotations

from src.validate_856 import ValidationResult
from src.validate_856_common import RetailerConfig, run_retailer_checks, validate_sscc18

_FEES = {
    "missing_asn": {"fee": 500.00, "per": "load"},
    "late_asn": {"fee": 500.00, "per": "load"},
    "missing_sscc18": {"fee": 100.00, "per": "case"},
    "invalid_sscc18_format": {"fee": 100.00, "per": "case"},
    "wrong_hl_hierarchy": {"fee": 0.00, "per": "document"},
    "missing_catch_weight": {"fee": 100.00, "per": "item"},
    "missing_po_reference": {"fee": 0.00, "per": "order"},
    "missing_ship_to": {"fee": 0.00, "per": "document"},
    "missing_ship_date": {"fee": 0.00, "per": "document"},
    "missing_carrier": {"fee": 0.00, "per": "document"},
}

_CONFIG = RetailerConfig(
    name="Walmart",
    fees=_FEES,
    # Walmart accepts Original, Cancellation, Replace (rules/walmart_856.yaml).
    allowed_bsn_purpose_codes={"00", "01", "05"},
)


def validate_856_walmart(result: ValidationResult) -> ValidationResult:
    """Add Walmart-specific validation findings to an existing ValidationResult."""
    return run_retailer_checks(result, _CONFIG)
