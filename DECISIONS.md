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

### 2026-05-15 — All JavaScript must be in external files, never inline
- **Why:** CSP `script-src 'self'` blocks inline `onclick` attributes and `<script>` blocks. This broke all interactive elements on the production site. External `.js` files served from `/static/` are allowed by `'self'`. Using `addEventListener` with `data-*` attributes instead of inline handlers.
- **Scope:** All templates (base.html, index.html, any future templates)
- **Do not:** Add inline `onclick`, `onsubmit`, or `<script>` blocks to templates. All JS goes in `/static/*.js`.

### 2026-05-15 — Use CSS classes instead of inline style attributes for visibility
- **Why:** CSP `style-src 'self'` (even with `'unsafe-inline'` added later as fallback) can strip inline `style` attributes. Using CSS classes for show/hide is CSP-safe and more maintainable.
- **Scope:** All templates
- **Do not:** Use `style="display: none"` or similar inline styles for layout control. Use CSS classes toggled by JavaScript.

---

## Data & Schema

[Decisions about data sources, schemas, transformations]

---

## Visualization

[Chart conventions, palette decisions, interactivity choices]

---

## Output Formats

### 2026-05-12 — Use ReportLab for PDF generation
- **Why:** ReportLab is the Python standard for programmatic PDF generation — stronger portfolio signal than lighter alternatives. Considered fpdf2 (simpler API, sufficient for tables) and WeasyPrint (HTML-to-PDF, but requires Cairo/Pango system libraries which complicate Fly.io Docker). ReportLab is pure Python, no system deps, and gives enough layout control for the 856 validation report PDFs later (severity badges, dollar estimates, three-layer reports).
- **Scope:** src/export_pdf.py and any future PDF export modules
- **Do not:** Pull in WeasyPrint or add system-level rendering dependencies

---

## Writing & Voice

[Voice, style, terminology decisions specific to this project]

---

## Third-Party Integrations

### 2026-05-16 — Use business identity in all public-facing assets
- **Why:** Personal Gmail and "Shawn P." attribution undercuts professional positioning for prospect-facing tools. Consistent company identity builds credibility.
- **Scope:** All CTAs, footers, README attributions, and contact links across Lailara projects.
- **Do not:** Use personal email addresses in client-facing or prospect-facing tools.

### 2026-05-16 — Remove analytics until properly configured
- **Why:** A placeholder `GA_MEASUREMENT_ID` in page source signals "unfinished" to technical reviewers. No analytics is invisible; broken analytics is visible.
- **Scope:** Any third-party script integration (analytics, chat widgets, etc.)
- **Do not:** Ship script tags with placeholder IDs or "replace this" comments.

### 2026-05-22 — Lead generation handled outside edi-preflight
- **Why:** User decided to handle lead gen differently rather than embedding CTAs in the free tool.
- **Scope:** All edi-preflight UI and content.
- **Do not:** Re-add lead-gen CTAs, gating, or audit-service upsells to the tool without explicit decision to reverse this.

### 2026-07-30 — Neutralize untrusted EDI text before it enters generated artifacts
- **Why:** Pasted/uploaded EDI is untrusted. Raw field values reaching a ReportLab `Paragraph` are parsed as mini-HTML — an angle bracket raises ValueError and 500s the export. Raw values written to CSV are executed as formulas by Excel/Sheets when they start with `=`, `+`, `-`, or `@`. Both were live findings this session.
- **Scope:** Every document/export generator fed by user EDI — ReportLab PDFs (`export_pdf.py`, `export_validation_pdf.py`), CSV (`export_csv.py`), and any future exporter.
- **Do not:** Pass a user-derived string into a ReportLab `Paragraph` without `xml.sax.saxutils.escape`, or write a user-derived CSV cell without the formula-trigger guard. Server-controlled labels (e.g. retailer names) are exempt only when verifiably non-user-derived.

---

## Reversed / Superseded

When a decision is overturned:
1. Strike through the original entry above (don't delete)
2. Add a new entry below with the replacement decision
3. Note the link in both directions

This preserves the history of why something is the way it is.
