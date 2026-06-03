# EDI Preflight

[![CI](https://github.com/MsShawnP/edi-preflight/actions/workflows/ci.yml/badge.svg)](https://github.com/MsShawnP/edi-preflight/actions/workflows/ci.yml)

A free web tool for specialty food brands doing EDI by hand. Parses
inbound Purchase Orders and validates outbound Advance Ship Notices
against retailer-specific specs, with chargeback-dollar attribution.

**Live:** https://edi.lailarallc.com

## What this does

Specialty food manufacturers in the $15M--$30M range often process
EDI documents manually -- keying line items from 850 Purchase Orders
into spreadsheets, assembling 856 ASNs by hand, and hoping nothing
triggers a chargeback. EDI Preflight handles both sides of that
problem.

**Inbound 850 parser.** Paste or upload a raw X12 850. The tool
extracts PO header, line items, allowances, ship-to addresses,
catch-weight flags, dates, terms, and totals into a structured table.
Export to CSV (for ERP import) or a formatted PDF.

**Outbound 856 validator.** Paste or upload a raw X12 856, select a
retailer, and get a three-layer validation report:

| Layer | What it checks |
|---|---|
| Structural | Envelope integrity, segment counts, HL hierarchy |
| Field-level | Date formats, SSCC-18 check digits, weight/measure units |
| Retailer-specific | Spec requirements unique to each trading partner |

Every finding is tagged with a severity level and, where applicable,
the chargeback dollar amount the retailer would assess. Results export
to PDF.

**Supported retailers:** Walmart, Amazon, UNFI, KeHE, Costco.

**Stateless.** Documents are processed in memory and discarded. Nothing
is stored.

**Cinderhaven context:** Built on the Cinderhaven synthetic dataset — a ~$25M specialty food brand, 50 SKUs across 5 product lines and 6 contracted retailers. Data is synthetic; methodology and deliverables are real.

## Tech stack

- **Backend** -- Python, FastAPI, Jinja2 server-side templates
- **Frontend** -- HTMX (self-hosted), vanilla CSS
- **PDF export** -- ReportLab
- **Parser** -- custom X12 tokenizer and extraction pipeline (no
  external EDI library)
- **Hosting** -- Fly.io (shared-cpu-1x, 256 MB, SEA region)
- **CI** -- GitHub Actions (`pytest` on push and PR to main)

## Repository structure

```
src/                   FastAPI app, parser, validators, exporters
  x12_tokenizer.py     Delimiter detection, segment splitting
  envelope.py          ISA/GS envelope parsing, retailer detection
  extract_850.py       PO extraction (header, lines, allowances, addresses)
  validate_856.py      Structural + field-level 856 validation
  validate_856_common.py  Shared retailer validation via RetailerConfig
  validate_856_*.py    Per-retailer validators (5 modules)
  export_csv.py        CSV export for parsed 850s
  export_pdf.py        PDF export for parsed 850s
  export_validation_pdf.py  PDF export for 856 validation reports
  formatting.py        Shared date/currency/quantity formatting
  main.py              FastAPI routes and middleware
  templates/           Jinja2 templates (base, index, results, validation)
  static/              CSS, JS, HTMX
rules/                 Retailer EDI specs in YAML (10 files, reference docs)
samples/               24 synthetic EDI files across 5 retailers
tests/                 19 test modules, 297 tests
Dockerfile             Python 3.13-slim, non-root user
fly.toml               Fly.io deployment config
pyproject.toml         Dependencies and project metadata
```\n
## Data contract

Canonical Cinderhaven conformance — 50 SKUs across 5 product lines and 6 contracted retailers.

## Run locally

```
pip install -e ".[dev]"
uvicorn src.main:app --reload
```

Opens at `http://localhost:8000`. No database, no external services.

## Tests

```
pytest
```

297 tests covering tokenization, envelope parsing, 850 extraction
(all 5 retailers), 856 validation (structural, field-level, and
retailer-specific rules), CSV/PDF export, input validation, and all
HTTP endpoints.

## Deploy

`Dockerfile` and `fly.toml` are configured for Fly.io:

```
flyctl deploy
```

Live at [edi.lailarallc.com](https://edi.lailarallc.com).

---
Built by [Lailara LLC](https://lailarallc.com) — data hygiene and analytics consulting for specialty food brands scaling into national retail.
