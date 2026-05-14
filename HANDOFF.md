# edi-preflight — Handoff Log

Session-by-session state. Updated by /log mid-session and /wrap at
session end.

For durable choices, see DECISIONS.md.
For the current work arc, see PLAN.md.
For things that didn't work, see FAILURES.md.

---

## 2026-05-14 — Milestone 1 + Milestone 2 complete (850 parsing, all five retailers)

**Phase:** Phase 2 — Build it right (Milestones 1–2 complete, Milestone 3 next)

**Goal:** Complete remaining Milestone 1 work (CSV + PDF export) and all of Milestone 2 (expand 850 parsing to Amazon, UNFI, KeHE, Costco).

**Completed:**
- Task 1.6: CSV + PDF export for 850
  - src/export_csv.py — one row per line item, denormalized headers, 15 columns
  - src/export_pdf.py — reportlab Platypus, sections for header/dates/addresses/line items/allowances/totals
  - POST /export/csv and POST /export/pdf endpoints in main.py
  - Hidden forms + export buttons in results template
  - 11 CSV tests, 8 PDF tests — all passing
- Tasks 2.1–2.4: All four retailers researched, coded, sampled, tested
  - rules/*.yaml spec files for Amazon, UNFI, KeHE, Costco
  - 8 synthetic samples (2 per retailer) in samples/
  - extract_850.py updated: new DTM labels, product ID qualifiers (UA/UI/PI/MG/IB/BP), REF IA/VR → vendor_number, AMT TT qualifier, CTT weight fields
  - envelope.py updated: DUNS IDs for UNFI, KeHE, Costco; name patterns for Amazon
  - ~50 multi-retailer tests in test_extract_850_multiretailer.py
- Task 2.5: Integration — auto-detection already works via envelope.py retailer detection. All five retailers parse correctly through the web UI.

**Key decisions logged:**
- Multi-retailer extraction stays in shared extract_850 module (no per-retailer modules)
- YAML spec files are documentation only, not runtime config
- reportlab for PDF (no system dependencies)
- CSV uses denormalized rows

**State:** 162 tests passing. Milestones 1 and 2 fully complete. All five retailers' 850 POs parse correctly with retailer-specific handling for dates, product IDs, allowances, terms, vendor numbers, and weight.

**Next concrete action:** Milestone 3 — Walmart 856 validation. Start with Task 3.1 (Walmart 856 spec research + synthetic samples).

**Blockers:** None

---

## 2026-05-12 — FastAPI + HTMX web skeleton complete (Task 1.5)

**Phase:** Phase 2 — Build it right (mid-implementation, Milestone 1 nearly complete)

**Goal:** Build the FastAPI + HTMX web skeleton for 850 inbound mode — paste or upload a Walmart 850, see structured table output in browser.

**Completed:**
- Created pyproject.toml with FastAPI, uvicorn, Jinja2, python-multipart dependencies
- Built src/main.py with GET / and POST /parse endpoints, Jinja2 filters for dates/currency/quantities
- Built Jinja2 templates: base layout (HTMX CDN), landing page (paste textarea + file upload), results partial (PO header card with retailer badge, key dates, addresses, line items with catch-weight badges and line-level allowances, header allowances, totals), error partial with message + hint
- Built src/static/style.css — clean, sober, data-forward styling
- Fixed ISA08 padding in 850_basic.edi and 850_catch_weight.edi (16 chars → 15, missed in previous session)
- Logged 2 failures: Starlette TemplateResponse API change, incomplete ISA padding fix

**Tried, didn't work:**
- Old Starlette TemplateResponse(name, context) API broke silently with Starlette 1.0 / FastAPI 0.136+ — context dict passed as template name, causing "unhashable type: dict" deep in Jinja2 cache. Fixed by switching to new API: TemplateResponse(request, name, context).
- Port 8000 zombie from background uvicorn required switching to port 8001 for preview testing.

**State:** Milestone 1 is 5/6 complete. Web UI works end-to-end for Walmart 850s — paste, upload, and error handling all verified. 80 tests pass.

**Next concrete action:** Task 1.6 — CSV + PDF export for 850. Download buttons on results page producing correct CSV (importable into Excel/ERP) and formatted PDF with header + line items + allowances.

**Blockers:** None

---

## 2026-05-12 20:30 — Core parser pipeline complete (Milestone 1, tasks 1.1–1.4)

**Phase:** Phase 2 — Build it right (post-clarify, mid-implementation)

**Goal:** Scaffold project, scope via /clarify, decompose into tasks, build the core parser pipeline for Walmart 850s.

**Completed:**
- Project scaffolded via /new-project (repo, state files, GitHub remote, v0.1-foundation tag)
- /clarify confirmed scope: two modes, five retailers both directions, custom parser, ungated, Fly.io
- /decompose produced 23 tasks across 6 milestones
- Task 1.1: X12 tokenizer (delimiter detection, segment splitting, line-break tolerance) — 21 tests
- Task 1.2: Envelope parser + retailer detection (all five retailers via name patterns + DUNS IDs) — 23 tests
- Task 1.3: Walmart 850 spec YAML + 3 synthetic samples (basic, allowances, catch-weight)
- Task 1.4: 850 extraction module (PO header, line items, SAC allowances, addresses, catch-weight, dates/terms/totals) — 36 tests

**Tried, didn't work:**
- .edi samples had ISA padding off by one (16 chars instead of 15 for receiver ID) — fixed
- SAC segments had element values at wrong positions (missing empty fields) — fixed

**State:** Milestone 1 is 4/6 complete. Backend parsing pipeline for Walmart 850 is fully functional with 80 passing tests. Next task shifts from parser code to web UI.

**Next concrete action:** Task 1.5 — FastAPI + HTMX skeleton with 850 inbound mode. Paste/upload a Walmart 850, see structured table output in browser.

**Blockers:** None

---

## 2026-05-12 18:56 — Project initialized

**Started from:** New project setup via /new-project.

**Did:** Created repo, set up CLAUDE.md/DECISIONS.md/HANDOFF.md/PLAN.md/
FAILURES.md, configured project structure, pushed to GitHub.

**State:** Foundation in place. PLAN.md arc not yet defined. Ready for
/clarify to scope the first arc of work.

**Next:** Run /clarify to scope the work, then define PLAN.md arc.

---
