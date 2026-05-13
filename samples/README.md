# Sample EDI Documents

Synthetic EDI X12 documents for testing and demonstration. All documents
use the fictional company "Cinderhaven Foods" as the sender/supplier.

## Document count: 24

### 850 Purchase Orders (11 samples)

| File | Retailer | Purpose |
|------|----------|---------|
| `walmart/850_basic.edi` | Walmart | Standard PO with 3 line items |
| `walmart/850_with_allowances.edi` | Walmart | PO with SAC allowance/discount lines |
| `walmart/850_catch_weight.edi` | Walmart | PO with catch-weight items (LB/KG UOM) |
| `amazon/850_basic.edi` | Amazon | Standard Vendor Central PO |
| `amazon/850_with_allowances.edi` | Amazon | PO with Amazon co-op allowances |
| `unfi/850_basic.edi` | UNFI | Standard distributor PO |
| `unfi/850_with_allowances.edi` | UNFI | PO with promotional allowances |
| `kehe/850_basic.edi` | KeHE | Standard distributor PO |
| `kehe/850_with_allowances.edi` | KeHE | PO with intro/slotting allowances |
| `costco/850_basic.edi` | Costco | Standard club PO |
| `costco/850_catch_weight.edi` | Costco | PO with catch-weight bulk items |

### 856 Advance Ship Notices (13 samples)

| File | Retailer | Purpose |
|------|----------|---------|
| `walmart/856_clean.edi` | Walmart | Valid ASN — passes all checks |
| `walmart/856_bad_dtm.edi` | Walmart | Invalid date formats (not CCYYMMDD) |
| `walmart/856_wrong_hl_order.edi` | Walmart | HL levels out of S→O→I→P order |
| `walmart/856_missing_mea.edi` | Walmart | Catch-weight items without MEA*WT |
| `walmart/856_missing_segment.edi` | Walmart | Missing N1*ST and PRF segments |
| `amazon/856_clean.edi` | Amazon | Valid ASN |
| `amazon/856_missing_sscc18.edi` | Amazon | Tare level without MAN segment |
| `unfi/856_clean.edi` | UNFI | Valid ASN |
| `unfi/856_missing_catch_weight.edi` | UNFI | Bulk items (LB/KG) without MEA*WT |
| `kehe/856_clean.edi` | KeHE | Valid ASN |
| `kehe/856_wrong_hl_order.edi` | KeHE | S→I→P (skips order level) |
| `costco/856_clean.edi` | Costco | Valid ASN |
| `costco/856_missing_segments.edi` | Costco | Missing ship-to, PO ref, catch-weight |

## Using these samples

Paste any sample into the web tool at edi-preflight.fly.dev to see it
parsed (850) or validated (856). The 856 error samples demonstrate the
three-layer validation report with severity badges and chargeback estimates.

## Note

All data is fictional. Company names, addresses, PO numbers, SSCC-18
barcodes, and product descriptions are synthetic. SSCC-18 barcodes have
valid mod-10 check digits.
