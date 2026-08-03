# INPUT-SPEC — edi-preflight (client mode)

What to hand the EDI pre-flight in a client engagement, and the partner-ID
configuration that steers retailer-specific validation. Written so a client's EDI
or IT person can produce the files without a call. **Derived from the engine
code** (`src/x12_tokenizer.py`, `src/envelope.py`, `src/extract_850.py`,
`src/validate_856*.py`), not from marketing copy.

## The files

- **Raw X12 EDI documents** — one transaction per file is simplest, but a file
  may carry a full interchange. Extension is not checked; `.edi`, `.txt`, or
  `.x12` are all fine. Point client mode at a single file **or a directory** of
  files.
- **Encoding:** UTF-8 preferred; Latin-1 is accepted as a fallback. Files up to
  2 MB. (Real 850/856 documents are typically well under 100 KB.)
- **Delimiters are auto-detected from the ISA line**, not assumed. The tokenizer
  reads the element separator from the character after `ISA`, the sub-element
  separator from ISA16 (byte 105), the segment terminator from byte 106, and the
  repetition separator from ISA11. Any consistent delimiter set works, as long as
  the element, sub-element, and segment characters are all different.
- Line breaks after segment terminators (for human readability) are stripped
  before parsing. Content before the first `ISA` is ignored.

The tool consumes two X12 transaction sets:

| Set | Direction | What the engine does |
|---|---|---|
| **850** Purchase Order | inbound (retailer → you) | Parses into structured PO data (header, lines, allowances, addresses, dates, totals) for CSV/PDF/ERP. |
| **856** Advance Ship Notice | outbound (you → retailer) | Validates structure, fields, and retailer-specific rules; attributes chargeback dollars. |

## Envelope — required in every file

A document must carry a complete, closed interchange or it is reported as not
ready (never silently half-parsed):

| Segment | Fields the engine reads | Rule |
|---|---|---|
| `ISA` | sender qual/ID (ISA05/06), receiver qual/ID (ISA07/08), control # (ISA13), version (ISA12) | Must be present; fixed 106-char header. |
| `IEA` | control # (IEA02) | Must be present and **match ISA13**. |
| `GS`  | functional ID (GS01: `PO`=850, `SH`=856), sender (GS02), receiver (GS03), control # (GS06) | GS01 must match the transaction. |
| `GE`  | control # (GE02) | Must **match GS06**. |
| `ST`/`SE` | ST01 (`850`/`856`), control # (ST02), SE01 segment count | SE01 should equal the true segment count. |

## 850 Purchase Order — fields extracted

| Segment | Canonical field(s) | Notes |
|---|---|---|
| `BEG` | purpose code (BEG01), PO type (BEG02), **PO number (BEG03)**, PO date (BEG05) | Core PO identity. |
| `REF*DP` | department | Optional. |
| `DTM` (header) | date references | Labeled by qualifier (002 requested-delivery, 010 requested-ship, 037/038 ship windows, etc.). |
| `ITD` | payment terms | From ITD12 or ITD09. |
| `SAC` | allowances / charges | Indicator A/C, code, **amount (SAC05, N2 — two implied decimals)**, percent (SAC07), handling (SAC12). Header- and line-level. |
| `N1`/`N3`/`N4` | addresses | Entity code (ST ship-to, BT bill-to, …), name, street, city/state/ZIP/country. |
| `PO1` | line: number, qty (PO102), UOM (PO103), unit price (PO104) | Product IDs from PO106+ pairs: `IN` buyer item, `UP`/`EN` UPC, `VN` vendor item, `UK` GTIN-14, `SK` SKU. UOM in LB/KG/OZ/CW ⇒ catch-weight. |
| `PID` | line description | |
| `PO4` | pack qty / size / UOM | |
| `MEA*WT` | line weight | Sets catch-weight. |
| `CTT` | total line items (CTT01), total qty (CTT02) | |
| `AMT*35` | total amount | |

Identifiers (UPC, GTIN-14, SSCC-18, PO number) are handled as **text** — leading
zeros are never dropped.

## 856 Advance Ship Notice — validated fields

Three layers run in order (structural → field → retailer-specific):

- **Envelope / structural:** transaction is an 856 (ST01=856, GS01=SH); `BSN`
  present; at least one shipment-level `HL`; control numbers foot; SE count foots;
  HL parents resolve (no orphaned loops).
- **Field-level:** `BSN01` purpose ∈ {00 Original, 01 Cancellation, 05 Replace};
  `BSN02` shipment ID present; `BSN03` date `CCYYMMDD`; `BSN04` time `HHMM`; every
  `DTM` date `CCYYMMDD`; `TD503` transport ∈ {M,R,S,A,LT}; `MAN01` ∈ {GM,CP};
  `SN102` quantity numeric and > 0; `SN103` UOM present.
- **HL hierarchy:** `S`hipment → `O`rder → `T`are → `P`ack → `I`tem (Tare
  optional, so O→P is valid). Per level:
  - Shipment (S): `TD5` carrier, **`DTM*011` shipped date**, **`N1*ST` ship-to**.
  - Order (O): **`PRF` PO reference**.
  - Container (T/P): **`MAN` SSCC-18** — 18 digits, valid mod-10 check digit.
  - Item (I): catch-weight `SN1` (UOM LB/KG/OZ) requires **`MEA*WT`**.

Findings are tagged Blocks-Transmission / Will-Cause-Chargeback /
May-Cause-Chargeback / Cosmetic, with the retailer's fee where one applies. Fees
are reported **per unit basis** ($/PO, $/case, $/item) and are never summed across
bases into one figure.

## Partner-ID configuration (engagement.yml)

The engine auto-detects the retailer from the interchange to pick the right 856
ruleset: it inspects ISA06, ISA08, GS02, and GS03 against known retailer EDI/DUNS
IDs and name patterns (Walmart, Amazon, UNFI, KeHE, Costco). For an inbound 850
the retailer is the **sender**; for an outbound 856 it is the **receiver**.

When a client's trading-partner IDs are not ones the engine already knows, map
them in `engagement.yml` — never by editing code:

```yaml
client:
  name: "Meridian Farms"
engagement:
  id: "MER-2026-08"
as_of_date: "2026-05-10"        # required; never defaulted to today
partners:                        # trading-partner ID -> retailer ruleset
  "0078742099999": walmart       # exact ISA/GS ID match
  "MERIDIAN-WMT":  walmart       # case-insensitive substring match also works
  "SUPERVALU":     unfi
```

Resolution order per file: (1) the engine's built-in detection; (2) if that
returns *unknown*, the `partners` map (exact ID, then case-insensitive
substring). If the retailer still cannot be resolved for an 856, the document is
validated with **structural + field-level rules only** and the deliverable
discloses that the retailer-specific layer was skipped. Supported retailer keys:
`walmart`, `amazon`, `unfi`, `kehe`, `costco`.

## Run

```bash
# with lailara_engagement installed: pip install -e ../engagement-template/lib
python client_mode.py --config engagement.yml --input client-data/asns/ \
    --out client-output [--final]
```

`--input` accepts a single EDI file or a directory (all files in it are
processed). Outputs to `client-output/` (gitignored):

- `edi-preflight-report.html` — branded, provenance-footed (each input's
  SHA-256, segment/transaction counts, `as_of_date`, config hash, validation
  status), DRAFT-watermarked until `--final`.
- `edi-preflight-report.txt` — plain-text companion.
- If no file yields a usable 850/856, a **Data Readiness Report** naming what is
  wrong per file is produced instead of results.
