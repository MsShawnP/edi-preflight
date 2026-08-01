"""Walmart-specific 856 ASN validation (layer 3).

Uses the shared retailer validation framework with Walmart's
chargeback fee schedule and strict S→O→T→P→I hierarchy.
"""

from __future__ import annotations

from src.validate_856 import ValidationResult
from src.validate_856_common import RetailerConfig, run_retailer_checks, validate_sscc18

# Fees follow Walmart's documented SQEP schedule (verified 2026-08 against
# SPS Commerce/SupplierWiki and Harvest Group summaries):
#   - ASN defects (missing / late / not downloaded): flat $25 per PO.
#   - Labeling/barcode defects: $1 per case manual-inspection charge. Walmart
#     also bills a $200 administrative fee per defect event, which this
#     per-unit fee model does not represent — per-case subtotals are a floor,
#     not the full exposure.
#   - Catch-weight data errors surface as PO-accuracy defects: $1 per case
#     impacted (+ the same $200 admin fee, not modeled).
#   - The larger real exposure on a late/missing ASN is OTIF: 3% of COGS on
#     cases scored late, billed under a separate program and not modeled here.
_FEES = {
    "missing_asn": {"fee": 25.00, "per": "PO"},
    "late_asn": {"fee": 25.00, "per": "PO"},
    "missing_sscc18": {"fee": 1.00, "per": "case"},
    "invalid_sscc18_format": {"fee": 1.00, "per": "case"},
    "wrong_hl_hierarchy": {"fee": 0.00, "per": "document"},
    "missing_catch_weight": {"fee": 1.00, "per": "item"},
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
