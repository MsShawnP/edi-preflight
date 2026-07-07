"""Costco-specific 856 ASN validation (layer 3).

Costco Wholesale compliance checks. Costco has strict OTIF
requirements with some of the highest chargebacks in retail.
Standard S→O→I→P hierarchy, all levels enforced.
"""

from __future__ import annotations

from src.validate_856 import ValidationResult
from src.validate_856_common import RetailerConfig, run_retailer_checks

_FEES = {
    "missing_sscc18": {"fee": 150.00, "per": "pallet"},
    "invalid_sscc18_format": {"fee": 150.00, "per": "pallet"},
    "wrong_hl_hierarchy": {"fee": 0.00, "per": "document"},
    "missing_catch_weight": {"fee": 150.00, "per": "item"},
    "missing_po_reference": {"fee": 0.00, "per": "order"},
    "missing_ship_to": {"fee": 0.00, "per": "document"},
    "missing_ship_date": {"fee": 0.00, "per": "document"},
    "missing_carrier": {"fee": 0.00, "per": "document"},
}

_CONFIG = RetailerConfig(
    name="Costco",
    fees=_FEES,
)


def validate_856_costco(result: ValidationResult) -> ValidationResult:
    """Add Costco-specific validation findings to an existing ValidationResult."""
    return run_retailer_checks(result, _CONFIG)
