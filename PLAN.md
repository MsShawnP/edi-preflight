# edi-preflight — Current Work Plan

The current arc of work. Updated when the arc changes, not every
session. For session-by-session state, see HANDOFF.md.

---

## Goal

Harden, complete the product layer, and improve code quality so
edi-preflight can go live as a working lead-gen asset. Derived from the
full project audit (2026-05-15, see AUDIT.md).

## Why this arc, why now

The engineering is done (23/23 MVP tasks, 254 tests). But the tool
can't answer its business question — "does this generate leads?" —
because it has no lead-gen mechanism, isn't deployed, and lacks
production hardening. The landscape scan confirmed the position is
unique (no competitor combines free + retailer-specific + chargeback
dollars), so the gap is product completion, not more features.

## Business question this arc answers

Same as the MVP arc: Can a free two-mode EDI tool generate qualified
leads for a $15K–$25K EDI Health Audit engagement from specialty food
brands doing EDI manually?

This arc adds the mechanisms needed to actually measure the answer.

---

## Decomposition: Production + Product + Quality

### Milestone 7: Pre-deploy hardening

Low-effort, high-importance fixes that must ship before `flyctl deploy`.
All items are independent and parallelizable.

- [x] 7.1: Add input size limit
    - Depends on: none
    - Done when: Uploaded files and pasted text capped at 2MB.
      Oversized input returns a clear error message with the limit
      stated. Test covers the rejection path.

- [x] 7.2: Self-host HTMX
    - Depends on: none
    - Done when: `htmx.min.js` served from `/static/`, CDN script tag
      removed from `base.html`. No external JS dependencies.

- [x] 7.3: Add security headers middleware
    - Depends on: none
    - Done when: All responses include Content-Security-Policy,
      X-Content-Type-Options (nosniff), X-Frame-Options (DENY), and
      Referrer-Policy. CSP allows `'self'` only for scripts (after 7.2
      removes the CDN).

- [x] 7.4: Fix async endpoint blocking
    - Depends on: none
    - Done when: POST endpoints (`/parse`, `/validate`, `/export/*`)
      are sync `def` (not `async def`), so FastAPI runs them in the
      thread pool automatically. Existing tests still pass.

- [x] 7.5: Production-harden FastAPI and Docker
    - Depends on: none
    - Done when: OpenAPI docs disabled (`docs_url=None`,
      `openapi_url=None`). Dockerfile adds a non-root `appuser` and
      runs as that user. Export filenames sanitized (strip
      non-alphanumeric chars from PO number / shipment ID). Generic
      exception catch blocks return a fixed message, not `str(e)`.

### Milestone 8: Product completion

The moves that connect the working tool to the business purpose.
Without these, the tool works but generates zero leads.

- [x] 8.1: Add lead-gen CTA
    - Depends on: none
    - Done when: Results pages (both 850 and 856) show a non-intrusive
      CTA section below the output. Copy references the EDI Health
      Audit and links to a contact/booking page. Not a modal, not a
      gate — a clear next step for users who found value. Footer also
      includes a brief "Built by [company]" with link.

- [x] 8.2: Add "Try a sample" buttons
    - Depends on: none
    - Done when: Both mode panels show a "Try a sample" link that
      loads a representative EDI document into the textarea and
      auto-submits. Inbound mode loads a Walmart 850 with allowances.
      Outbound mode loads a Walmart 856 with errors (so the user sees
      findings). Samples served from a new endpoint or embedded in the
      template.

- [x] 8.3: Add SEO meta tags and favicon
    - Depends on: none
    - Done when: `base.html` includes meta description, Open Graph
      tags (title, description, type, url), and a favicon. Description
      targets the search query "free EDI validation tool" and
      references specialty food brands.

- [x] 8.4: Add responsive CSS breakpoints
    - Depends on: none
    - Done when: Data tables scroll horizontally on narrow screens.
      Form layout stacks vertically on mobile. Address grid stacks.
      Tested at 375px (phone) and 768px (tablet) widths. No horizontal
      overflow on any page state.

- [x] 8.5: Add analytics
    - Depends on: none
    - Done when: Privacy-respecting analytics (Plausible, Fathom, or
      similar — no cookies, no PII) tracks page views and custom
      events for parse submissions, validate submissions, and export
      downloads. Script tag added to `base.html`. Event firing added
      to relevant endpoints or HTMX attributes.

### Milestone 9: Code quality

Improves maintainability and test confidence. Items are independent
unless noted.

- [x] 9.1: Add endpoint tests for main.py
    - Depends on: 7.1, 7.4, 7.5 (tests should cover hardened behavior)
    - Done when: TestClient tests cover all 7 routes: GET `/`,
      POST `/parse` (valid + invalid + file upload), POST `/validate`
      (valid + invalid + retailer override + wrong transaction type),
      POST `/export/csv`, `/export/pdf`, `/export/validation-pdf`
      (valid + error cases). Content-Disposition headers verified.
      Error responses verified.

- [x] 9.2: Migrate Walmart validator to RetailerConfig
    - Depends on: none
    - Done when: `validate_856_walmart.py` is a thin wrapper (~30–40
      lines) using `RetailerConfig` + `run_retailer_checks()` from
      `validate_856_common.py`, matching the pattern of the other four
      retailers. All existing Walmart validation tests pass unchanged.
      `_validate_sscc18` removed from Walmart module (common version
      used). Net line reduction of ~200+.

- [x] 9.3: Add tests for untested validation rules
    - Depends on: none
    - Done when: Dedicated tests exercise all 9 previously untested
      rule paths in `validate_856.py`: GS/GE mismatch, SE count
      mismatch, wrong GS functional ID, no shipment HL, no transaction
      set, invalid BSN time, missing BSN shipment ID, invalid transport
      method, missing SN1 UOM. Each test provides a crafted input that
      triggers the specific rule and asserts the correct finding.

- [x] 9.4: Add tests for validate_856_common.py
    - Depends on: none
    - Done when: New `tests/test_validate_856_common.py` covers:
      unknown HL level, pack level with children, early returns for
      `require_prf=False`, `require_sscc18=False`,
      `check_catch_weight=False`. At least 5 new tests.

- [x] 9.5: Resolve YAML rule files
    - Depends on: none (decision task)
    - Done when: Either (A) YAML files deleted and `rules/README.md`
      updated to note that retailer specs are defined in Python
      modules, or (B) YAML files loaded at runtime via PyYAML and
      `RetailerConfig` generated from them. Current state (exists but
      unused) resolved either way.

- [x] 9.6: Extract shared formatting utilities
    - Depends on: none
    - Done when: `_format_date`, `_format_currency`, `_format_quantity`
      live in one place (e.g., `src/formatting.py`) and are imported by
      `main.py`, `export_pdf.py`, and `export_validation_pdf.py`.
      Duplicates removed. Existing tests pass.

- [x] 9.7: Factor out validation pipeline helper
    - Depends on: none
    - Done when: The tokenize→parse→validate→retailer chain in
      `/validate` and `/export/validation-pdf` is extracted into a
      `_validate_or_error` helper (matching the existing
      `_extract_po_or_error` pattern). Both endpoints use the helper.

- [x] 9.8: Add CI pipeline
    - Depends on: none
    - Done when: `.github/workflows/ci.yml` runs `pytest` on push and
      PR to main. Python version matches `requires-python` in
      `pyproject.toml` (3.11+). Badge in README.

- [x] 9.9: Fix minor test issues
    - Depends on: none
    - Done when: Amazon retailer name test assertion fixed (remove
      vacuous `or` disjunct). `_validate_sscc18` import in Walmart
      tests updated to use the public common version (or test through
      the public `validate_856_walmart()` interface). Unused
      `EnvelopeError` imports removed from `extract_850.py` and
      `validate_856.py`. `_collect_all_nodes` renamed to drop
      underscore prefix.

---

## Out of scope for this arc

- Cinderhaven 90-day case study and synthetic dataset
- EDI transmission (AS2/SFTP/VAN integration)
- Auto-repair / auto-fix of outbound documents
- Real-time monitoring or alerting
- Document types beyond 850 and 856
- Direct ERP/order-system integration
- Custom domain setup
- Client-specific local deliverable tooling
- Rate limiting (evaluate after deploy based on actual traffic)
- Content strategy / SEO content (separate arc)

## Definition of done for this arc

- [x] All Milestone 7 items complete — tool is safe to deploy
- [x] All Milestone 8 items complete — tool can generate and measure
      leads
- [x] All Milestone 9 items complete — code is clean and well-tested
- [x] Deployed and accessible at edi-preflight.fly.dev
- [x] 297 tests passing (up from 254)

---

## Arc history

### 2026-05-14 — Ship MVP: two-mode EDI tool for five retailers
- Outcome: All 23 tasks complete. Inbound 850 parser + outbound 856
  validator covering Walmart, Amazon, UNFI, KeHE, Costco. CSV/PDF
  export. 254 tests passing. Deploy config shipped but `flyctl deploy`
  not run.
- Tag: none (no deploy yet)
