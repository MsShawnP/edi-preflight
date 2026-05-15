# edi-preflight — Project Audit

Audited: 2026-05-15

---

## Phase 1: Baseline Assessment

### What was intended

A free, ungated web tool for $15M–$30M specialty food brands doing EDI
by hand. Two modes: inbound 850 parser with CSV/PDF export, outbound
856 validator with severity-tagged findings and chargeback-dollar
attribution. Five retailers (Walmart, Amazon, UNFI, KeHE, Costco).
Deployed at edi-preflight.fly.dev. Stateless. Purpose: lead-gen for a
$15K–$25K EDI Health Audit engagement.

### What actually exists

| Dimension | Status | Notes |
|-----------|--------|-------|
| Inbound 850 parsing | Complete | All 5 retailers, auto-detect |
| Outbound 856 validation | Complete | 3-layer report, severity tags, dollar estimates |
| CSV export (850) | Complete | One row per line item with PO header context |
| PDF export (850) | Complete | ReportLab, formatted with header card + tables |
| PDF export (856 validation) | Complete | Three-layer report with severity badges |
| Input validation | Complete | Format-specific diagnostics for bad input |
| Five retailers | Complete | Walmart, Amazon, UNFI, KeHE, Costco — both modes |
| Web UI | Complete | HTMX two-tab interface, paste + file upload |
| Deployment | Config only | Dockerfile + fly.toml ready; `flyctl deploy` not run |
| Lead generation | **Missing** | No CTA, no contact link, no audit mention |
| Analytics | **Missing** | No way to measure usage or conversion |
| SEO basics | **Missing** | No meta description, no OG tags |
| "Try it" UX | **Missing** | 24 samples in repo but no way to load from UI |

### Codebase snapshot

- **Source:** 2,767 lines across 15 Python files in `src/`
- **Tests:** 2,022 lines across 18 test files — 254 tests, all passing (1.67s)
- **Templates:** 5 HTML files (475 lines) + 585-line CSS
- **Rules:** 10 YAML retailer specs (1,478 lines)
- **Samples:** 24 synthetic EDI files across 5 retailers
- **Config:** pyproject.toml, Dockerfile, fly.toml, .dockerignore
- **Built in:** 3 days (2026-05-12 to 2026-05-14)

Architecture is clean and modular:
`x12_tokenizer → envelope → extract_850 / validate_856 → export → render`

### Intent vs. reality gaps

**Gap 1 — Lead generation is the stated business purpose, but the tool
has no lead-gen mechanism.** No CTA on any page. No mention of the EDI
Health Audit. No contact link, email capture, or "book a call" button.
The tool works, but it's a dead end — a user who finds value has no
path to a paid engagement. This is the single highest-leverage gap.

**Gap 2 — Not deployed.** Deploy config exists and looks correct, but
`flyctl deploy` hasn't been run. The tool can't generate leads if it's
not accessible. Blocked on operator having a Fly.io account + flyctl.

**Gap 3 — No "try it" experience.** 24 sample EDI files live in the
repo, but the web UI offers no way to load one. A first-time visitor
who doesn't have an EDI file on hand has nothing to do. For a lead-gen
tool targeting people doing EDI by hand (who may not have files readily
exportable), this is a real barrier.

**Gap 4 — No analytics.** Without usage data, you can't answer the
business question ("does this generate leads?"). At minimum: page
views, parse/validate submissions, export downloads.

**Gap 5 — No SEO or discoverability.** The HTML has no meta
description, no Open Graph tags, no favicon, no structured data. For a
tool meant to attract inbound traffic from brands searching for EDI
help, this limits organic reach.

**Gap 6 — HTMX loaded from CDN.** `unpkg.com` is a single point of
failure. If unpkg goes down, the tool is non-functional. For a
production lead-gen tool, self-hosting the 15KB file is safer.

### What's strong

- Code quality is solid — clean separation of concerns, consistent
  naming, no dead code
- Test coverage is high (1:1 source/test line ratio) and fast (1.67s)
- Error messages are helpful and specific
- The stateless design is right for this use case
- Retailer rule files are well-structured and extensible
- The architecture would support new document types (810, 820) with
  minimal changes to the web layer

---

## Phase 2: Internal Review

Full-sweep review across code quality, architecture, tests, security,
performance, UX, and DevEx. Findings ranked by leverage — what would
move the needle most if fixed.

### Top opportunities (ranked)

#### 1. No input size limit — crash risk (Security + Performance)

`_read_edi_content` in `src/main.py:70-82` calls `await file.read()`
with no size check. The Fly.io VM has 256MB RAM. A single 30MB+ upload
would OOM the process. During tokenization, peak memory is 5–7x the
input size (raw bytes + decoded string + cleaned string + segment
objects). A 2MB cap is generous — a typical 850 with 500 line items is
under 100KB.

**Fix:** Add a size guard at the top of `_read_edi_content`. Also add
`max_upload_size` to the Starlette config. Trivial change, highest
production risk.

#### 2. Zero endpoint-level tests (Tests)

`src/main.py` (304 lines, 7 routes) has no tests via TestClient or
httpx. `test_input_validation.py` tests the underlying library
functions but never calls a FastAPI endpoint. Untested paths include:

- File upload + latin-1 fallback encoding
- Error response rendering through Jinja2 templates
- Retailer auto-detect vs. manual override in `/validate`
- Transaction-type guard (non-856 submitted to `/validate`)
- Content-Disposition headers and filenames on exports
- The `_extract_po_or_error` helper
- All generic `Exception` catch blocks

#### 3. Walmart validator is a 284-line duplicate (Architecture)

`validate_856_walmart.py` (284 lines) duplicates what the other four
retailers do in ~31 lines each via `validate_856_common.py`. The
`_validate_sscc18` function is byte-for-byte identical across both
files. The HL hierarchy, shipment, order, tare, and pack checks are
functionally identical, differing only in string interpolation of the
retailer name. Migrating Walmart to `RetailerConfig` would eliminate
~250 lines.

#### 4. HTMX from CDN without integrity hash (Security)

`base.html:9` loads HTMX from `unpkg.com` with no `integrity` or
`crossorigin` attribute. If unpkg is compromised, arbitrary JS
executes with access to every EDI document users paste. Self-hosting
the 14KB file eliminates both the supply chain risk and the CDN
latency/availability dependency.

#### 5. No security headers (Security)

No CSP, X-Content-Type-Options, X-Frame-Options, or Referrer-Policy.
The app can be iframed (clickjacking), and there's no defense-in-depth
against XSS. Fix with a simple middleware — about 10 lines.

#### 6. Sync blocking in async endpoints (Performance)

All POST endpoints are `async` but call synchronous CPU-bound
functions (tokenize, parse, validate, PDF generation) directly on the
event loop. Under uvicorn's single-worker config, one large document
blocks all other requests. Fix: remove `async` from POST endpoints and
let FastAPI auto-thread them.

#### 7. No responsive CSS (UX)

Zero `@media` queries in 585 lines of CSS. Data tables will overflow
on mobile. For a tool targeting operations staff at food brands (who
may be on tablets in a warehouse), this matters.

#### 8. Nine validation rules have no test coverage (Tests)

In `validate_856.py`, these rule paths are never exercised by any
test: GS/GE control mismatch, SE segment count mismatch, wrong GS
functional ID, no shipment HL, no transaction set, invalid BSN time,
missing BSN shipment ID, invalid transport method, missing SN1 UOM.
Each is a conditional branch that will never catch a regression.

#### 9. validate_856_common.py has no dedicated tests (Tests)

The shared validation engine (285 lines) used by 4 retailers has no
test file. Retailer tests exercise it indirectly through happy-path
scenarios, but several branches are untested: unknown HL level, pack
level children check, early returns when `require_prf`, `require_sscc18`,
or `check_catch_weight` are False.

#### 10. YAML rule files are dead weight (Architecture)

The 10 YAML files in `rules/` contain the same fee schedules and
requirements that are hardcoded in the Python retailer modules. The
YAML files are never loaded at runtime. If someone updates a fee in
YAML thinking it drives behavior, nothing changes. Either delete them
(they're reference docs only) or load them at runtime (adds PyYAML
dep, makes new retailers YAML-only).

### Additional findings

#### Security (lower priority)

- **Content-Disposition injection** — Export filenames built from
  unsanitized EDI fields (`po.po_number`, `shipment_id`). A crafted
  value could break the header. Fix: strip non-alphanumeric chars.
- **OpenAPI docs exposed** — `/docs` and `/openapi.json` are public.
  Disable in production with `docs_url=None, openapi_url=None`.
- **Docker runs as root** — No `USER` directive in Dockerfile.
- **Exception messages leak internals** — Generic `Exception` catch
  returns `f"Unexpected error: {e}"` to users. Log server-side, return
  generic message.

#### Architecture (lower priority)

- **`_collect_all_nodes` is private but cross-module** — Underscore
  prefix but imported by both `validate_856_common.py` and
  `validate_856_walmart.py`. Rename to drop the underscore.
- **Formatting utilities duplicated 3x** — `_format_date`,
  `_currency`, `_qty` appear in `main.py`, `export_pdf.py`, and
  `export_validation_pdf.py` with identical logic.
- **Duplicated validation pipeline in main.py** — The
  tokenize→parse→validate→retailer chain appears in both `/validate`
  and `/export/validation-pdf`. Should be factored into a helper like
  `_extract_po_or_error`.
- **Unused imports** — `EnvelopeError` imported but unused in
  `extract_850.py` and `validate_856.py`.

#### Tests (lower priority)

- **Amazon retailer name test is vacuous** — Asserts
  `len(amazon_refs) > 0 or len(retailer_findings) > 0`. The second
  disjunct is always true, making the first irrelevant.
- **PDF tests are smoke-only** — 19 PDF tests check `%PDF-` header or
  relative size, never actual content. They verify ReportLab doesn't
  crash, not that correct data appears.
- **Tests import private Walmart function** — `test_validate_856_walmart.py`
  imports `_validate_sscc18` (private). Will break if Walmart is
  refactored to use the common version.

#### UX

- **No favicon** — browsers show generic tab icon.
- **No accessibility** — tab buttons lack ARIA roles/labels, no skip
  navigation.
- **Error panel has no retry path** — user sees error message but no
  button to go back or try again.

#### DevEx

- **No CI pipeline** — CLAUDE.md lists "CI: GitHub Actions" but no
  `.github/workflows/` directory exists.
- **No linting/formatting** — no ruff, black, mypy, or type checking
  configured.
- **No Makefile or scripts** — no `make test`, `make run`, `make lint`.

---

## Phase 3: Landscape Scan

Searched for direct competitors, adjacent tools, open-source projects,
and market signals across the EDI tool ecosystem.

### Competitor set

| Tool | Type | Price | 850 Parse | 856 Validate | Retailer Rules | Chargeback $ | Free/Ungated |
|------|------|-------|-----------|--------------|----------------|-------------|-------------|
| **EDI Pre-flight** | Web tool | Free | Yes + CSV/PDF | Yes, 3-layer | 5 retailers | Yes | Yes |
| Stedi EDI Inspector | Web viewer | Free | View only | Base spec only | No | No | Yes |
| EdiNation / EdiFabric | API + portal | Freemium | Parse only | Base spec only | No | No | Free tier |
| Orderful | EDI platform | $189/mo/TP | Full platform | Full platform | Yes | No | Paid (free validator) |
| Crstl | AI EDI platform | Custom quote | Full platform | Pre-transmit | Yes (UNFI, KeHE, Walmart) | No | No |
| SPS Commerce | EDI platform | ~$750/mo | Full platform | Full platform | Yes | Via SupplyPike | No |
| TrueCommerce | EDI platform | ~$500/mo | Full platform | Full platform | Yes | No | No |
| WebEDI / Edict | Forms-based | Subscription | Forms entry | Forms entry | Yes (grocery) | No | No |
| pyx12 | Python library | Open source | HIPAA only | HIPAA only | No | No | N/A |
| Walmart gozer | Java library | Open source | 850 WIP | 856 parse only | Walmart only | No | N/A |
| Bots-EDI | Self-hosted | Open source | Translator | Translator | No | No | N/A |

### Where EDI Pre-flight sits

**Unique position:** No tool in the market combines free/ungated access
+ structured 850 parsing with export + retailer-specific 856 validation
+ chargeback-dollar attribution in a single stateless web tool. This
territory is genuinely unoccupied.

**Better than the landscape at:**
- **Chargeback attribution** — Only tool that attaches dollar estimates
  to each finding. SPS Commerce has this via the SupplyPike acquisition
  ($206M, Aug 2024), but that's a $750+/mo enterprise product.
- **Retailer-specific 856 validation** — Stedi and EdiNation validate
  against the base X12 spec. EDI Pre-flight validates against retailer
  implementation guides (HL loop order, SSCC-18 format, OTIF timing).
- **Ungated access** — No login, no signup, no credit card. Orderful's
  free validator is the closest but is generic (no retailer rules).
- **Two-mode coverage** — Both inbound parsing and outbound validation
  in one tool. Most tools do one or the other.

**Worse than the landscape at:**
- **Connectivity** — Not an EDI transmission platform. SPS, TrueCommerce,
  Orderful, Crstl all handle sending/receiving. Pre-flight is
  diagnostic-only.
- **Ongoing monitoring** — No continuous compliance checking. SupplyPike
  (now SPS) monitors chargebacks and disputes them automatically.
- **Polish** — Stedi's UI is significantly more polished (interactive
  segment trees, JSON translation, copy-paste UX). Pre-flight is
  functional but plain.
- **Breadth** — Stedi supports all X12 and EDIFACT transaction sets.
  Pre-flight supports only 850 and 856.

**Missing from the landscape (opportunities):**
- **"Try with sample" UX** — No competitor offers this either. Stedi
  has a blank paste box. Pre-flight has 24 samples in the repo but no
  way to load them from the UI. First-mover opportunity for reducing
  friction.
- **Lead-gen CTA** — Orderful is the only competitor using a free tool
  as a lead-gen funnel (free validator → platform upsell). The pattern
  is validated but no one applies it to EDI consulting/audit services.
- **Food-brand framing** — Crstl is food-focused but paid. No free tool
  speaks directly to specialty food brands. The messaging, retailer
  coverage (UNFI, KeHE alongside Walmart/Amazon/Costco), and chargeback
  dollar amounts are all food-industry-specific differentiators.

### Key market signals

- **SPS Commerce acquired SupplyPike for $206M (Aug 2024)** — validates
  the chargeback-prevention market is large and growing. Consolidates
  the stack under enterprise pricing, leaving SMBs underserved.
- **Crstl raised Series A (Mar 2025)** with Shopify Ventures
  participating — validates the food-brand EDI automation thesis. But
  Crstl is a paid platform, not a free diagnostic tool.
- **Orderful's free-tool-as-lead-gen pattern** — proves the model
  works. Their free EDI Validator and GS1 Label Generator drive
  awareness for their $189/mo platform.
- **Platform pricing floor** — SPS (~$750/mo) + TrueCommerce (~$500/mo)
  + Orderful ($189/mo per TP) means a brand doing 3 retailers pays
  $500–$2,250/mo minimum. The free pre-flight tool eliminates
  commitment risk for brands unsure if they even have a problem.
- **Published chargeback amounts** — UNFI $500/PO for missing labels,
  Amazon 6% of product cost for ASN issues, Costco $5–10/carton for
  GS1-128 issues. These are the numbers that make 856 validation
  findings tangible.

### Analogies from other markets

The closest structural analogy is **MXToolbox** (free DNS/email
diagnostic) or **TurboTax Free Edition** (free tool surfaces your
situation, creates urgency, gates the fix behind paid service). The
pattern: free, ungated, stateless diagnostic → shows the user exactly
what's wrong → provides a clear path to paid help. EDI Pre-flight has
the first two but not the third.

---

## Phase 4: Synthesis & Next Moves

### The core insight

The engineering is done. The product isn't.

EDI Pre-flight occupies genuinely unoccupied territory — no other tool
combines free/ungated 850 parsing + retailer-specific 856 validation +
chargeback-dollar attribution. The landscape validates both the market
(SPS paid $206M for SupplyPike; Crstl raised a Series A) and the
funnel pattern (Orderful uses free tools as lead-gen). But the tool
currently has no mechanism to convert usage into leads, and it isn't
deployed. The business question can't be answered until both are fixed.

### Recommended next moves (ranked)

Grouped into two batches: **pre-deploy hardening** (things that must
be done before going live) and **product completion** (things that
make the tool answer the business question). A third batch covers code
quality improvements that can follow after deploy.

---

#### Batch A: Pre-deploy hardening

These are low-effort, high-importance fixes that should ship before
`flyctl deploy`. Total effort: ~1–2 hours.

| # | Move | Why | Effort |
|---|------|-----|--------|
| A1 | Add input size limit (2MB) | Single upload can crash the 256MB VM | Trivial |
| A2 | Self-host HTMX | Eliminate CDN supply chain + availability risk | Trivial |
| A3 | Add security headers middleware | CSP, X-Frame-Options, nosniff, referrer | 10 lines |
| A4 | Remove `async` from POST endpoints | Prevents event-loop blocking under load | Trivial |
| A5 | Disable OpenAPI docs in production | Don't expose API schema publicly | 1 line |
| A6 | Add non-root Docker user | Principle of least privilege | 2 lines |
| A7 | Sanitize export filenames | Prevent Content-Disposition injection | 5 lines |
| A8 | Genericize exception messages | Don't leak internals to users | 5 lines |

#### Batch B: Product completion

These are the moves that make the tool answer the business question.
Without them, the tool works but generates zero leads. Total effort:
~half a day.

| # | Move | Why | Effort |
|---|------|-----|--------|
| B1 | **Add lead-gen CTA** | The #1 gap. A user who finds value has no path to a paid engagement. Add a non-intrusive CTA on the results page: "This report shows what a full EDI Health Audit finds. [Book a free consultation →]" linking to a calendar/contact page. Not a modal, not a gate — just a clear next step. | Low |
| B2 | **Add "Try a sample" buttons** | First-time visitors with no EDI file have nothing to do. Load a sample Walmart 850 or 856 with one click. No competitor offers this. First-mover advantage for reducing friction. | Low |
| B3 | **Add SEO meta tags** | Meta description, OG tags, favicon. Required for organic discoverability. The food-brand audience searches for "EDI help" and "Walmart chargeback" — the tool should be findable. | Trivial |
| B4 | **Add responsive breakpoints** | Operations staff at food brands may be on tablets. Zero `@media` queries currently. Data tables overflow on mobile. | Medium |
| B5 | **Add basic analytics** | Without usage data, the business question is unanswerable. Plausible Analytics (privacy-respecting, no cookies, one script tag) tracks page views, parse/validate submissions, and export downloads. | Trivial |

#### Batch C: Code quality (post-deploy)

These improve maintainability and test confidence. They don't affect
users directly and can follow at a natural pace.

| # | Move | Why | Effort |
|---|------|-----|--------|
| C1 | Add endpoint tests for main.py | 7 routes, zero tests. Biggest test gap. | Medium |
| C2 | Migrate Walmart validator to RetailerConfig | Eliminate 250 lines of duplication | Low |
| C3 | Add tests for 9 untested validation rules | Conditional branches that can't catch regressions | Medium |
| C4 | Add tests for validate_856_common.py | Shared engine, 5 untested branches | Medium |
| C5 | Decide on YAML rule files | Delete (reference-only) or load at runtime. Current state is worst of both. | Decision |
| C6 | Extract shared formatting utilities | Same functions in 3 files | Low |
| C7 | Factor out `_validate_or_error` helper | Duplicated validation pipeline in main.py | Low |
| C8 | Add CI pipeline (GitHub Actions) | CLAUDE.md lists it; it doesn't exist | Low |
| C9 | Fix vacuous Amazon test assertion | `or` disjunct makes the check meaningless | Trivial |

### Strategic recommendation

**Ship Batch A + B as a single arc, then deploy.**

The engineering side is mature — 254 tests, clean architecture, solid
error handling. What's missing is the product wrapper that turns a
working tool into a working lead-gen asset. Batch A is production
hygiene (~1 hour). Batch B is the business-critical gap (~half day).
Together they represent roughly one session of work.

After deploy, measure for 2–4 weeks (analytics from B5 will tell you
if the tool gets traffic and if users reach the CTA from B1). Then
decide whether Batch C is worth the investment based on real usage
data.

The landscape position is strong and defensible: no competitor
combines free access + retailer-specific validation + chargeback
dollars. The gap is not "build more features" — it's "connect the
working tool to the business purpose it was built for."

### What this audit does NOT cover

- Content strategy (how to drive traffic to the tool)
- Pricing/packaging of the EDI Health Audit engagement
- Whether the five-retailer coverage is the right set
- The Cinderhaven case study (explicitly out of scope per PLAN.md)
