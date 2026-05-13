# edi-preflight — Failure Log

What was attempted that didn't work, why it didn't work, and what was
tried next.

Lower bar than DECISIONS.md — capture failures even when they didn't
produce a durable rule. The whole point: future-you (or future-Claude)
shouldn't re-attempt dead ends because the lesson got lost.

---

## Format

### YYYY-MM-DD — [One-line failure description]

**Attempted:** [What was tried]

**Why it didn't work:** [Concrete reason, not "it broke." If the
failure mode was technical, name the specific issue. If the failure
mode was scope or approach, name that.]

**What we tried instead:** [The next attempt, which may also have
failed and may have its own entry below]

**Status:** Resolved / open / abandoned

**Tags:** [keywords for future text-search — e.g., "rendering, pandoc,
quarto" or "scope, scrollytelling, decoration"]

---

## Entries

### 2026-05-12 — Hand-written .edi samples had ISA padding off by one

**Attempted:** Wrote synthetic Walmart 850 samples with "CINDERHAVEN" (11 chars) as receiver ID, padded to 15 chars for ISA08.

**Why it didn't work:** Added 5 trailing spaces instead of 4, making ISA08 = 16 chars. ISA is fixed-length (106 chars total). Off-by-one padding shifted all downstream delimiter positions — sub-element separator and segment terminator were read from wrong byte offsets, triggering a "delimiter conflict" error.

**What we tried instead:** Corrected to 4 trailing spaces (11 + 4 = 15). All three sample files had the same issue and were fixed together.

**Status:** Resolved

**Tags:** edi, isa, padding, delimiter, sample-data

### 2026-05-12 — SAC segment samples had element values at wrong positions

**Attempted:** Wrote SAC (allowance/charge) segments in synthetic 850 samples. Placed amount and percent values immediately after the code field.

**Why it didn't work:** EDI's positional format requires every empty field to be represented as an empty element (consecutive delimiters). SAC04 (agency service code) was omitted, shifting SAC05 (amount), SAC06 (percent qualifier), SAC07 (percent), and SAC12 (handling code) all off by one. Parser read correct positions but got wrong values.

**What we tried instead:** Added explicit empty fields at SAC04 and between SAC07–SAC12. Verified by counting elements: SAC has 15 defined positions and every gap must be delimited.

**Status:** Resolved

**Tags:** edi, sac, allowance, positional-format, sample-data
