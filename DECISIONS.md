# edi-preflight — Decisions Log

Permanent record of choices that should survive session turnover.
If a decision is reversed, strike it through and add the replacement
below — don't delete.

---

## Format

Each entry:
- **Date** — when decided
- **Decision** — one sentence, imperative voice
- **Why** — the reasoning, including what was tried and rejected
- **Scope** — what this applies to (file, chunk, deliverable, or "global")
- **Do not** — explicit anti-instructions, if any

---

## Architecture & Pipeline

### 2026-05-12 — Build a custom X12 parser instead of using pyx12 or bots-edi
- **Why:** Stronger portfolio signal ("we built the parser" vs "we wrapped a library"). No dependency risk from unmaintained libraries. Full control over how retailer quirks are handled — the parser only needs to handle 850 and 856, not all X12 transaction sets. pyx12 is mature but old; bots-edi is more active but small community.
- **Scope:** global — affects all parsing, extraction, and validation code
- **Do not:** Pull in pyx12, bots-edi, or any other EDI parsing library

### 2026-05-12 — Retailer detection uses pattern matching on ISA/GS identifiers
- **Why:** Retailer ISA/GS IDs are trading-partner-specific and not universally published. Exact ID configuration would require each user to know their trading partner's ISA06 value. Pattern matching on name substrings (WALMART, AMAZON, AMZN, WMT, etc.) plus known DUNS IDs covers the common cases for a lead-gen tool. Falls back to "Unknown" with manual retailer selection as escape hatch.
- **Scope:** src/envelope.py — retailer detection logic
- **Do not:** Require users to configure exact retailer IDs before using the tool

---

## Data & Schema

[Decisions about data sources, schemas, transformations]

---

## Visualization

[Chart conventions, palette decisions, interactivity choices]

---

## Output Formats

### 2026-05-12 — Use reportlab for PDF export instead of weasyprint
- **Why:** reportlab is pure Python with no system-level dependencies (no cairo, pango, GDK). weasyprint produces nicer HTML-to-PDF output but requires heavy system libraries that complicate Docker builds and Windows dev setups. The 850 export is a structured tabular report, not a design-heavy document — reportlab's Table/Platypus API handles this well. Simpler Fly.io deploy story.
- **Scope:** src/export_pdf.py, pyproject.toml
- **Do not:** Pull in weasyprint or other HTML-to-PDF converters

### 2026-05-12 — CSV export uses one row per line item with denormalized header fields
- **Why:** Target users import into Excel or lightweight ERP systems. Denormalizing PO number, date, retailer, and ship-to into each row makes the CSV self-contained — no need for a separate header row or relational join. This matches how ERP import wizards expect flat data.
- **Scope:** src/export_csv.py

### 2026-05-14 — Multi-retailer 850 extraction via shared extract_850 module, not per-retailer modules
- **Why:** All five retailers use the same X12 850 structure — BEG, REF, DTM, SAC, N1 loop, PO1 loop, CTT, AMT. The differences are which elements are present and which qualifiers mean what, not different control flows. A single extraction function with retailer-agnostic qualifier mappings (DTM labels, product ID pairs, REF qualifiers for vendor number, AMT "35" vs "TT") covers all five retailers without if/else branching per retailer. Per-retailer modules would duplicate 90% of the logic.
- **Scope:** src/extract_850.py
- **Do not:** Create separate extract_850_amazon.py, extract_850_kehe.py etc. unless structural divergence actually requires it

### 2026-05-14 — Retailer spec YAML files are documentation, not runtime config
- **Why:** The YAML files in rules/ document each retailer's 850 quirks for human reference — which qualifiers they use, which segments are absent, which IDs to expect. The extraction code reads from the EDI directly using qualifier-based mappings. Loading YAML at runtime would add complexity (schema validation, file I/O, a rules engine) for zero functional benefit when the set of retailers is small and known. If the retailer set grows past 10 or rules become user-configurable, revisit.
- **Scope:** rules/*.yaml, src/extract_850.py
- **Do not:** Import or parse YAML files at runtime for extraction logic

---

## Writing & Voice

[Voice, style, terminology decisions specific to this project]

---

## Reversed / Superseded

When a decision is overturned:
1. Strike through the original entry above (don't delete)
2. Add a new entry below with the replacement decision
3. Note the link in both directions

This preserves the history of why something is the way it is.
