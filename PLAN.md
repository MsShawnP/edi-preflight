# edi-preflight — Current Work Plan

The current arc of work. Updated when the arc changes, not every
session. For session-by-session state, see HANDOFF.md.

---

## Goal

Ship a working two-mode EDI web tool at edi-preflight.fly.dev — inbound
850 parser and outbound 856 validator covering Walmart, Amazon, UNFI,
KeHE, and Costco — as a free, ungated lead-gen asset for the EDI Health
Audit engagement.

## Why this arc, why now

Specific prospect doing EDI by hand across five retailers. Amazon is
disproportionate pain per order. Tool demonstrates capability, open-source
rule library builds credibility, ungated access drives inbound leads.
Slots into the lead-gen tool cadence alongside GTIN Validator.

## Business question this arc answers

Can a free two-mode EDI tool generate qualified leads for a $15K–$25K
EDI Health Audit engagement from specialty food brands doing EDI manually?

## Scope confirmed via /clarify (2026-05-12)

- **Two modes:** (A) inbound 850 parsing → structured table + CSV/PDF,
  (B) outbound 856 validation → severity-tagged report with
  chargeback-dollar attribution
- **Build order:** Inbound parser first (the hook), outbound validator
  second
- **Retailers:** All five (Walmart, Amazon, UNFI, KeHE, Costco) for
  both modes
- **Tech:** Custom EDI parser (no pyx12/bots-edi). FastAPI + HTMX +
  Jinja2 on Fly.io. Stateless.
- **URL:** edi-preflight.fly.dev (custom domain deferred)
- **Name:** EDI Pre-flight
- **Access:** Ungated, no login
- **Error handling:** Helpful diagnostics for invalid/garbage input
- **Not MVP:** Cinderhaven case study (follow-on content piece)
- **Not in scope:** EDI transmission, auto-repair, ERP integration,
  document types beyond 850/856, client-specific local tooling

---

## Decomposition: EDI Pre-flight MVP

### Milestone 1: Core Parser + Walmart 850 End-to-End

First vertical slice — raw EDI text to structured output in a browser.

- [x] 1.1: X12 tokenizer
    - Depends on: none
    - Done when: Tokenizes raw X12 into segments/elements/sub-elements
      with correct delimiter detection from ISA segment. Tests pass
      against a hand-crafted sample.

- [x] 1.2: Envelope parser + retailer detection
    - Depends on: 1.1
    - Done when: Parses ISA/GS/ST/SE/GE/IEA structure, extracts
      control numbers, identifies retailer from ISA/GS sender/receiver
      IDs. Tests pass with five different retailer headers.

- [x] 1.3: Walmart 850 spec research + synthetic samples
    - Depends on: none (research task — user-bottlenecked)
    - Done when: Walmart 850 spec captured in YAML rule file. At least
      3 synthetic samples in repo: basic PO, PO with SAC allowances,
      PO with catch-weight items.

- [x] 1.4: 850 extraction module — Walmart
    - Depends on: 1.1, 1.2, 1.3
    - Done when: Given a Walmart 850, extracts PO header, line items
      (PO1), allowances (SAC), ship-to (N1/N3/N4) as structured data.
      Correctly separates allowance lines from line items. Tests pass
      against all Walmart samples.

- [x] 1.5: FastAPI + HTMX skeleton with 850 inbound mode
    - Depends on: 1.4
    - Done when: Web page at localhost — paste or upload a Walmart 850,
      see structured table with header summary, line items, allowances,
      and retailer badge. Both paste and file upload work.

- [x] 1.6: CSV + PDF export for 850
    - Depends on: 1.5
    - Done when: Download buttons on results page produce correct CSV
      (importable into Excel/ERP) and formatted PDF with header + line
      items + allowances.

### Milestone 2: Expand 850 to All Retailers

Tasks 2.1–2.4 are independent of each other and can be parallelized.
Each involves spec research (user-bottlenecked) + extraction quirks +
samples.

- [x] 2.1: Amazon 850 — spec research + extraction + samples
    - Depends on: 1.4
    - Done when: Amazon 850 quirks documented in YAML. At least 2
      synthetic samples. Extraction handles Amazon-specific fields.
      Tests pass.

- [x] 2.2: UNFI 850 — spec research + extraction + samples
    - Depends on: 1.4
    - Done when: Same verification as 2.1, for UNFI.

- [x] 2.3: KeHE 850 — spec research + extraction + samples
    - Depends on: 1.4
    - Done when: Same verification as 2.1, for KeHE.

- [x] 2.4: Costco 850 — spec research + extraction + samples
    - Depends on: 1.4
    - Done when: Same verification as 2.1, for Costco.

- [x] 2.5: 850 integration — all five retailers in web UI
    - Depends on: 1.5, 2.1–2.4
    - Done when: Web UI auto-detects retailer from document headers.
      All five retailers parse correctly with retailer-specific
      handling. Tests pass against all sample docs.

### Milestone 3: Walmart 856 End-to-End

Second vertical slice — outbound validation mode in the browser.

- [x] 3.1: Walmart 856 spec research + synthetic samples
    - Depends on: none (research task — user-bottlenecked)
    - Done when: Walmart 856 spec in YAML. Chargeback fee schedule
      documented. At least 5 samples: 1 clean, 4 with errors (wrong HL
      loop order, missing MEA for catch-weight, bad DTM format, missing
      required segment).

- [x] 3.2: 856 structural validation
    - Depends on: 1.1, 1.2
    - Done when: Validates envelope completeness, segment ordering,
      control number matching. Catches missing GS, ST/SE mismatch,
      bad terminators. Tests pass.

- [x] 3.3: 856 field-level validation
    - Depends on: 3.2
    - Done when: Validates required fields present and correctly
      formatted (dates in CCYYMMDD, valid qualifier codes, numeric
      ranges). Tests pass against samples with field-level errors.

- [x] 3.4: Walmart 856 retailer-specific rules + severity tagging
    - Depends on: 3.1, 3.3
    - Done when: HL loop ordering (S→O→I→P) validated. Catch-weight
      MEA*WT checked. ASN timing checked. Each finding tagged with
      severity (blocks-transmission / will-cause-chargeback /
      may-cause-chargeback / cosmetic) and dollar estimate from fee
      schedule. Tests pass against all Walmart 856 samples.

- [x] 3.5: Web UI — 856 outbound mode + validation report
    - Depends on: 3.4, 1.5
    - Done when: Second mode on landing page. Paste/upload 856, select
      retailer, see three-layer report (structural / field-level /
      retailer-spec) with severity badges and dollar estimates.

- [x] 3.6: PDF export for 856 validation report
    - Depends on: 3.5
    - Done when: Download button produces formatted PDF of the
      three-layer validation report with severity tags and dollar
      estimates.

### Milestone 4: Expand 856 to All Retailers

Tasks 4.1–4.4 are independent and parallelizable. Each involves spec
research (user-bottlenecked) + retailer-specific rules + samples.

- [x] 4.1: Amazon 856 — spec research + rules + samples
    - Depends on: 3.3
    - Done when: Amazon 856 rules in YAML with chargeback fees. Samples
      with errors. Validator catches Amazon-specific violations. Tests
      pass.

- [x] 4.2: UNFI 856 — spec research + rules + samples
    - Depends on: 3.3
    - Done when: Same verification as 4.1, for UNFI.

- [x] 4.3: KeHE 856 — spec research + rules + samples
    - Depends on: 3.3
    - Done when: Same verification as 4.1, for KeHE.

- [x] 4.4: Costco 856 — spec research + rules + samples
    - Depends on: 3.3
    - Done when: Same verification as 4.1, for Costco.

- [x] 4.5: 856 integration — all five retailers in web UI
    - Depends on: 3.5, 4.1–4.4
    - Done when: Retailer selector works for all five. Correct rule set
      applied per retailer. Tests pass against all 856 samples.

### Milestone 5: Error Handling + Input Validation

- [x] 5.1: Input validation and diagnostic messages
    - Depends on: 2.5, 4.5
    - Done when: Non-EDI input (CSV, JSON, plain text) returns helpful
      "this doesn't look like EDI" message. Truncated documents
      identified ("missing SE/IEA — document may be truncated"). Wrong
      transaction set flagged ("this is an 810 invoice, not an 850").
      Tests cover at least 6 bad-input scenarios.

### Milestone 6: Deploy + Finalize

- [x] 6.1: Dockerfile + fly.toml + deploy to Fly.io
    - Depends on: 5.1
    - Done when: Tool accessible at edi-preflight.fly.dev. Both modes
      functional. "We don't store your documents" notice visible on UI.

- [x] 6.2: Retailer spec rule library finalized
    - Depends on: 4.5
    - Done when: All five retailers' 850 + 856 rules in clean YAML in
      `rules/` directory. README documents the rule format and what
      each file covers.

- [x] 6.3: Sample EDI documents curated for repo
    - Depends on: 2.5, 4.5
    - Done when: 20+ sample documents in `samples/` covering all five
      retailers, both document types, common patterns and failure
      modes. README explains each sample's purpose.

---

## Dependency summary

```
1.1 (tokenizer) ──→ 1.2 (envelope) ──→ 1.4 (Walmart 850) ──→ 1.5 (web UI) ──→ 1.6 (export)
                                    ├──→ 3.2 (856 structural) ──→ 3.3 (field) ──→ 3.4 (Walmart rules)
                                    │                                           ├──→ 4.1–4.4 (other retailers)
                                    │                                           └──→ 3.5 (856 UI) ──→ 3.6 (PDF)
                                    └──→ 2.1–2.4 (other 850s) ──→ 2.5 (integration)
1.3 (Walmart spec) ─────────────────────→ 1.4
3.1 (Walmart 856 spec) ─────────────────→ 3.4
```

Tasks marked "user-bottlenecked" (1.3, 2.1–2.4, 3.1, 4.1–4.4) require
retailer spec research. Claude can help with research but the user needs
to verify accuracy against actual specs from vendor portals.

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

## Definition of done for this arc

- [x] Inbound 850 parser handles documents from all five retailers with
      correct line-item extraction, allowance separation, and retailer
      detection
- [x] Outbound 856 validator checks structural, field-level, and
      retailer-specific rules for all five retailers
- [x] Validation findings tagged with severity and chargeback-dollar
      estimates
- [x] CSV and PDF export working for inbound mode
- [x] PDF export working for outbound validation report
- [x] Helpful error messages for invalid/truncated/non-EDI input
- [ ] Deployed and accessible at edi-preflight.fly.dev (deploy config
      shipped; `flyctl deploy` not yet run)
- [x] Retailer spec rule library in YAML, in the repo
- [x] Sample EDI documents (synthetic) in the repo for try-without-data

---

## Arc history

When an arc completes, archive its goal, completion date, and outcome
here. Then start a new arc above. Provides continuity without bloating
the active plan.

### [Date completed] — [Goal]
- Outcome: [what shipped or what was decided]
- Tag: [git tag if one was created]
