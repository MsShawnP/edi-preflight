# Retailer Spec Rule Library

YAML files documenting EDI X12 specifications and compliance rules for
each supported retailer. Used as reference for the validation modules —
the validators read fee schedules from code, not directly from these files.

## Files

### 850 Purchase Order Specs

| File | Retailer | Covers |
|------|----------|--------|
| `walmart_850.yaml` | Walmart | BEG, PO1, SAC, N1 segments; product ID qualifiers |
| `amazon_850.yaml` | Amazon | Vendor Central quirks; dropship vs stand-alone POs |
| `unfi_850.yaml` | UNFI | Natural/organic distributor; DC-specific IDs |
| `kehe_850.yaml` | KeHE | Specialty distributor; DUNS-based identification |
| `costco_850.yaml` | Costco | Club pack handling; catch-weight items |

### 856 ASN Specs

| File | Retailer | Covers |
|------|----------|--------|
| `walmart_856.yaml` | Walmart | HL hierarchy, SSCC-18, catch-weight MEA, OTIF chargebacks |
| `amazon_856.yaml` | Amazon | Vendor compliance chargebacks; SSCC-18 required |
| `unfi_856.yaml` | UNFI | Lower chargeback rates; SSCC-18 recommended |
| `kehe_856.yaml` | KeHE | Moderate enforcement; standard hierarchy |
| `costco_856.yaml` | Costco | Strict OTIF; highest chargeback rates |

## Format

Each 856 YAML file includes:

- **Envelope requirements** — GS functional ID, ST transaction type
- **BSN segment** — required elements and valid codes
- **HL loop structure** — level hierarchy (S→O→I→P), required child segments
- **Chargeback fee schedule** — fee amount, per-unit, severity, description
- **Severity levels** — ordered from blocks-transmission to cosmetic

## Accuracy note

These specs are synthesized from publicly available retailer EDI
guidelines and may not reflect every retailer-specific edge case.
Verify against your trading partner's current spec before relying
on these for production compliance.
