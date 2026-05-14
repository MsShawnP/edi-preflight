# edi-preflight

Free EDI tool for specialty food brands doing EDI by hand. Two modes:

- **Inbound 850 parser** — paste or upload a Purchase Order, get a
  structured table of line items, allowances, ship-to addresses, and
  totals. Export to CSV (for ERP import) or PDF.
- **Outbound 856 validator** — paste or upload an Advance Ship Notice,
  pick a retailer, get a three-layer report (structural, field-level,
  retailer-specific) with severity tags and chargeback-dollar
  estimates. Export the report to PDF.

Supports Walmart, Amazon, UNFI, KeHE, and Costco. Stateless — documents
are processed in memory and discarded.

## Running locally

```
pip install fastapi 'uvicorn[standard]' jinja2 python-multipart reportlab pytest
uvicorn src.main:app --reload
```

Then open `http://localhost:8000`.

## Tests

```
pytest
```

## Repo layout

- `src/` — FastAPI app, parser, validators, exporters
- `rules/` — retailer EDI specs in YAML (reference docs; see
  `rules/README.md`)
- `samples/` — synthetic 850 and 856 documents for trying the tool
  without your own data (see `samples/README.md`)
- `tests/` — pytest suite

## Deploy

`Dockerfile` and `fly.toml` are configured for Fly.io. From a host with
`flyctl` installed:

```
flyctl deploy
```
