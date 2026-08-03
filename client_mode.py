"""Client-mode CLI for the EDI pre-flight.

Wraps the existing X12 engine (tokenizer -> envelope -> extract_850 /
validate_856 + retailer rules) with the shared ``lailara_engagement`` scaffold so
a client's own EDI files can be checked locally: tolerant intake of one file or a
directory of 850/856 documents, a preflight that names anything that can't be read
(Data Readiness Report if nothing is usable), a partner-ID map from
``engagement.yml`` that steers retailer selection without editing code, and a
branded, provenance-footed, draft-watermarked report written to
``client-output/`` only.

Usage:
    python client_mode.py --config engagement.yml --input client-data/asns/ \
        --out client-output [--final]

The document itself is never transmitted, stored, or deployed — client mode runs
fully local and writes only to the gitignored ``client-output/`` directory.
"""

from __future__ import annotations

import argparse
import hashlib
import html
from dataclasses import dataclass
from pathlib import Path

from lailara_engagement import build_provenance, load_config, validation_status_label
from lailara_engagement import palette as P
from lailara_engagement.provenance import InputRef, Provenance

from src.envelope import (
    EnvelopeError,
    Retailer,
    TransactionType,
    parse_envelope,
)
from src.extract_850 import ExtractionError, PurchaseOrder, extract_850
from src.validate_856 import Severity, ValidationResult, validate_856
from src.validate_856_amazon import validate_856_amazon
from src.validate_856_costco import validate_856_costco
from src.validate_856_kehe import validate_856_kehe
from src.validate_856_unfi import validate_856_unfi
from src.validate_856_walmart import validate_856_walmart
from src.x12_tokenizer import TokenizeError, tokenize

TOOL = "edi-preflight"
TOOL_VERSION = "0.1"

_MAX_INPUT_BYTES = 2 * 1024 * 1024  # mirror the web app's 2 MB ceiling

_RETAILER_VALIDATORS = {
    Retailer.WALMART: validate_856_walmart,
    Retailer.AMAZON: validate_856_amazon,
    Retailer.UNFI: validate_856_unfi,
    Retailer.KEHE: validate_856_kehe,
    Retailer.COSTCO: validate_856_costco,
}

_RETAILER_KEYS = {
    "walmart": Retailer.WALMART,
    "amazon": Retailer.AMAZON,
    "unfi": Retailer.UNFI,
    "kehe": Retailer.KEHE,
    "costco": Retailer.COSTCO,
}

_RETAILER_LABELS = {
    Retailer.WALMART: "Walmart",
    Retailer.AMAZON: "Amazon",
    Retailer.UNFI: "UNFI",
    Retailer.KEHE: "KeHE",
    Retailer.COSTCO: "Costco",
    Retailer.UNKNOWN: "Unknown",
}

# EDI severity -> (fill, text, label) using the design-system palette.
_SEV_STYLE = {
    Severity.BLOCKS_TRANSMISSION: (P.LL_RED_SURFACE, P.LL_RED_DARK, "Blocks Transmission"),
    Severity.WILL_CAUSE_CHARGEBACK: (P.LL_SG_SURFACE, P.LL_SG_DARK, "Will Cause Chargeback"),
    Severity.MAY_CAUSE_CHARGEBACK: (P.LL_CHICAGO_SURFACE, P.LL_CHICAGO, "May Cause Chargeback"),
    Severity.COSMETIC: (P.LL_SURFACE, P.LL_TEXT_SEC, "Cosmetic"),
}


# --------------------------------------------------------------------------- #
# Intake + preflight
# --------------------------------------------------------------------------- #

@dataclass
class FileOutcome:
    filename: str
    sha256: str
    n_segments: int = 0
    n_transactions: int = 0
    doc_type: str = "unknown"          # "850" | "856" | "unknown"
    retailer: Retailer = Retailer.UNKNOWN
    retailer_source: str = "unresolved"  # "auto" | "partner-map" | "unresolved"
    status: str = "error"                # "ok" | "error"
    error: str = ""
    result: ValidationResult | None = None   # 856
    po: PurchaseOrder | None = None          # 850

    @property
    def input_ref(self) -> InputRef:
        # For EDI, "rows" = segment count and "cols" = transaction-set count.
        return InputRef(
            filename=self.filename,
            sha256=self.sha256,
            n_rows=self.n_segments,
            n_cols=self.n_transactions,
        )


def _iter_input_files(input_path: str) -> list[Path]:
    p = Path(input_path)
    if p.is_dir():
        return sorted(f for f in p.iterdir() if f.is_file())
    return [p]


def _decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def _resolve_retailer(envelope, partners: dict) -> tuple[Retailer, str]:
    """Resolve the retailer: built-in detection first, then the partner-ID map.

    The engine already inspects ISA/GS ids for the known majors. When it comes
    back UNKNOWN we consult the client's ``partners`` map (exact id, then
    case-insensitive substring) so client-specific trading-partner ids steer the
    ruleset without any code edit. Returns (retailer, source)."""
    if envelope.retailer is not Retailer.UNKNOWN:
        return envelope.retailer, "auto"
    if not partners:
        return Retailer.UNKNOWN, "unresolved"

    candidates = [envelope.interchange.sender_id, envelope.interchange.receiver_id]
    for g in envelope.groups:
        candidates.extend([g.sender_code, g.receiver_code])
    candidates = [str(c).strip().casefold() for c in candidates if str(c).strip()]

    norm = {str(k).strip().casefold(): str(v).lower() for k, v in partners.items()}
    # exact match
    for cand in candidates:
        if cand in norm:
            return _RETAILER_KEYS.get(norm[cand], Retailer.UNKNOWN), "partner-map"
    # substring match
    for cand in candidates:
        for pat, ret in norm.items():
            if pat and pat in cand:
                return _RETAILER_KEYS.get(ret, Retailer.UNKNOWN), "partner-map"
    return Retailer.UNKNOWN, "unresolved"


def _process_file(path: Path, partners: dict) -> FileOutcome:
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    outcome = FileOutcome(filename=path.name, sha256=sha)

    if len(raw) > _MAX_INPUT_BYTES:
        outcome.error = f"file exceeds the 2 MB limit ({len(raw):,} bytes)"
        return outcome
    if not raw.strip():
        outcome.error = "file is empty"
        return outcome

    content = _decode(raw)
    try:
        tokens = tokenize(content)
        envelope = parse_envelope(tokens)
    except (TokenizeError, EnvelopeError) as exc:
        outcome.error = str(exc)
        return outcome

    outcome.n_segments = len(tokens.segments)
    outcome.n_transactions = len(envelope.transactions)

    if not envelope.transactions:
        outcome.error = "no transaction set (ST/SE) found"
        return outcome

    tx_type = envelope.transactions[0].transaction_type
    retailer, source = _resolve_retailer(envelope, partners)
    outcome.retailer = retailer
    outcome.retailer_source = source

    if tx_type == TransactionType.PURCHASE_ORDER_850:
        outcome.doc_type = "850"
        try:
            outcome.po = extract_850(envelope)
        except ExtractionError as exc:
            outcome.error = str(exc)
            return outcome
        outcome.status = "ok"
    elif tx_type == TransactionType.ASN_856:
        outcome.doc_type = "856"
        result = validate_856(envelope)
        validator = _RETAILER_VALIDATORS.get(retailer)
        if validator:
            result = validator(result)
        outcome.result = result
        outcome.status = "ok"
    else:
        outcome.error = "document is neither an 850 nor an 856 transaction"

    return outcome


# --------------------------------------------------------------------------- #
# Branded report
# --------------------------------------------------------------------------- #

def _po_summary_rows(po: PurchaseOrder) -> str:
    esc = html.escape
    rows = [
        ("PO number", esc(po.po_number or "—")),
        ("Line items", f"{len(po.line_items):,}"),
        ("Total quantity", f"{po.total_quantity:,.0f}"),
        ("Total amount", f"${po.total_amount:,.2f}"),
        ("Allowances / charges", f"{len(po.all_allowances):,}"),
        ("Addresses", ", ".join(esc(a.entity_code) for a in po.addresses) or "—"),
    ]
    return "".join(f"<tr><td>{k}</td><td class=num>{v}</td></tr>" for k, v in rows)


def _findings_table(result: ValidationResult) -> str:
    esc = html.escape
    if not result.findings:
        return "<p class=ll-clean-note>No findings. This ASN passes all checks.</p>"
    body = ""
    for f in result.sorted_findings():
        fill, text, label = _SEV_STYLE[f.severity]
        fee = f"${f.fee:,.2f}/{esc(f.fee_per)}" if f.has_fee else "—"
        body += (
            f"<tr><td><span class=ll-badge style=\"background:{fill};color:{text}\">"
            f"{esc(label)}</span></td>"
            f"<td>{esc(f.layer)}</td>"
            f"<td>{esc(f.message)}</td>"
            f"<td class=num>{fee}</td></tr>"
        )
    return (
        "<table class=ll-table><thead><tr><th>Severity</th><th>Layer</th>"
        "<th>Finding</th><th>Fee</th></tr></thead><tbody>"
        f"{body}</tbody></table>"
    )


def _fee_breakdown_note(result: ValidationResult) -> str:
    esc = html.escape
    breakdown = result.fee_breakdown
    if not breakdown:
        return ""
    parts = [
        f"${b['subtotal']:,.2f} across {b['count']} finding(s) @ per-{esc(b['fee_per'])}"
        for b in breakdown
    ]
    return (
        "<p class=ll-basis><strong>Chargeback exposure (per basis, never summed "
        "across bases):</strong> " + "; ".join(parts) + ".</p>"
    )


def _file_section(o: FileOutcome) -> str:
    esc = html.escape
    retailer_label = _RETAILER_LABELS.get(o.retailer, "Unknown")
    src = {"auto": "auto-detected", "partner-map": "via partner-ID map",
           "unresolved": "unresolved"}[o.retailer_source]
    meta = (f"<div class=ll-file-meta><span class=ll-k>Type</span> {esc(o.doc_type)} "
            f"&middot; <span class=ll-k>Retailer</span> {esc(retailer_label)} ({src}) "
            f"&middot; <span class=ll-k>Segments</span> {o.n_segments:,}</div>")

    if o.status != "ok":
        body = f"<p class=ll-file-error>Not processed — {esc(o.error)}</p>"
    elif o.doc_type == "850":
        body = f"<table class=ll-table>{_po_summary_rows(o.po)}</table>"
    else:  # 856
        body = _findings_table(o.result) + _fee_breakdown_note(o.result)
        if o.retailer_source == "unresolved":
            body += ("<p class=ll-basis>Retailer-specific layer skipped — no "
                     "retailer resolved for this ASN; structural and field-level "
                     "rules only. Add the trading-partner id to <code>partners</code> "
                     "in engagement.yml.</p>")

    return (f"<section class=ll-section><h2 class=ll-h2>{esc(o.filename)}</h2>"
            f"{meta}{body}</section>")


def _data_limitations(outcomes: list[FileOutcome]) -> list[str]:
    items: list[str] = []
    for o in outcomes:
        if o.status != "ok":
            items.append(f"{o.filename}: not processed — {o.error}")
        elif o.doc_type == "856" and o.retailer_source == "unresolved":
            items.append(f"{o.filename}: retailer unresolved — retailer-specific "
                         "rules skipped (structural + field-level only)")
    return items


def _report_html(config, outcomes: list[FileOutcome], provenance: Provenance,
                 *, draft: bool, blocked: bool) -> str:
    esc = html.escape
    draft_class = "ll-draft" if draft else ""
    title = "EDI Data Readiness Report" if blocked else "EDI Pre-flight Report"

    n_ok = sum(1 for o in outcomes if o.status == "ok")
    if blocked:
        fill, text, label = P.LL_RED_SURFACE, P.LL_RED_DARK, "Blocked — data not ready"
    elif any(o.status != "ok" for o in outcomes) or any(
        o.doc_type == "856" and o.retailer_source == "unresolved" for o in outcomes
    ):
        fill, text, label = P.LL_SG_SURFACE, P.LL_SG_DARK, "Proceeded with warnings"
    else:
        fill, text, label = P.LL_HK_SURFACE, P.LL_HK_DARK, "Clean"

    sections = "".join(_file_section(o) for o in outcomes)

    limitations = _data_limitations(outcomes)
    if limitations:
        lim = "".join(f"<li>{esc(x)}</li>" for x in limitations)
        limitations_html = (f"<section class=ll-section><h2 class=ll-h2>Data "
                            f"limitations</h2><ul class=ll-limitations>{lim}</ul></section>")
    else:
        limitations_html = ""

    return f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width, initial-scale=1">
<title>{esc(title)} — {esc(config.client_name)}</title>
<style>{_css(draft)}</style></head>
<body class="{draft_class}"><main class=ll-page>
<header class=ll-header>
  <div class=ll-eyebrow>Lailara LLC &middot; EDI Pre-flight</div>
  <h1 class=ll-title>{esc(title)}</h1>
  <div class=ll-client>
    <div><span class=ll-k>Client</span> {esc(config.client_name)}</div>
    <div><span class=ll-k>Engagement</span> {esc(config.engagement_id)}</div>
    <div><span class=ll-k>As of</span> {esc(config.as_of_date.isoformat())}</div>
    <div><span class=ll-k>Prepared by</span> {esc(config.prepared_by)}</div>
  </div>
</header>
<section class=ll-banner style="background:{fill};color:{text}">
  <div class=ll-banner-status>{esc(label)}</div>
  <div class=ll-banner-counts>{n_ok} of {len(outcomes)} file(s) processed</div>
</section>
{sections}
{limitations_html}
{provenance.to_html()}
</main></body></html>"""


def _report_text(config, outcomes: list[FileOutcome], provenance: Provenance) -> str:
    lines = ["LAILARA LLC — EDI PRE-FLIGHT REPORT",
             f"Client: {config.client_name} ({config.engagement_id})",
             f"As of:  {config.as_of_date.isoformat()}", "-" * 60]
    for o in outcomes:
        rl = _RETAILER_LABELS.get(o.retailer, "Unknown")
        if o.status != "ok":
            lines.append(f"{o.filename}: NOT PROCESSED — {o.error}")
        elif o.doc_type == "850":
            lines.append(f"{o.filename}: 850 PO {o.po.po_number} — "
                         f"{len(o.po.line_items)} line(s), ${o.po.total_amount:,.2f}")
        else:
            lines.append(f"{o.filename}: 856 ASN ({rl}) — "
                         f"{len(o.result.findings)} finding(s)")
    lines.append("-" * 60)
    lines.append(provenance.to_text())
    return "\n".join(lines)


def _css(draft: bool) -> str:
    draft_css = (
        ".ll-draft::before{content:'DRAFT';position:fixed;top:50%;left:50%;"
        "transform:translate(-50%,-50%) rotate(-32deg);font-family:var(--s);"
        "font-size:22vw;font-weight:700;color:rgba(204,16,10,.06);z-index:0;"
        "pointer-events:none;white-space:nowrap}" if draft else ""
    )
    return f"""
:root{{--s:{P.LL_SERIF};--f:{P.LL_SANS}}}
*{{box-sizing:border-box}}
body{{margin:0;background:{P.LL_CANVAS};color:{P.LL_TEXT};font-family:var(--f);line-height:1.6}}
.ll-page{{position:relative;z-index:1;max-width:{P.LL_MAX_WIDTH};margin:0 auto;padding:48px 24px}}
.ll-header{{border-bottom:1px solid {P.LL_GRIDLINE};padding-bottom:24px;margin-bottom:24px}}
.ll-eyebrow{{font-size:12px;letter-spacing:.04em;text-transform:uppercase;color:{P.LL_RED};font-weight:600}}
.ll-title{{font-family:var(--s);font-weight:700;color:{P.LL_INK};font-size:34px;margin:8px 0 16px}}
.ll-client{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:8px 24px;font-size:14px}}
.ll-k{{color:{P.LL_TEXT_SEC};font-size:11px;text-transform:uppercase;letter-spacing:.04em}}
.ll-client .ll-k{{display:block}}
.ll-banner{{border-radius:{P.LL_RADIUS};padding:16px 20px;margin-bottom:32px;display:flex;
 justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:8px}}
.ll-banner-status{{font-family:var(--s);font-weight:700;font-size:22px}}
.ll-section{{margin:0 0 32px}}
.ll-h2{{font-family:var(--s);font-weight:700;color:{P.LL_INK};font-size:22px;margin:0 0 8px;
 padding-bottom:6px;border-bottom:1px solid {P.LL_GRIDLINE};word-break:break-all}}
.ll-file-meta{{font-size:13px;color:{P.LL_TEXT_SEC};margin-bottom:12px}}
.ll-file-error{{color:{P.LL_RED_DARK};background:{P.LL_RED_SURFACE};padding:10px 14px;border-radius:{P.LL_RADIUS}}}
.ll-basis{{font-size:13px;color:{P.LL_TEXT_SEC};margin-top:10px}}
.ll-clean-note{{background:{P.LL_HK_SURFACE};border-left:3px solid {P.LL_HK_DARK};padding:12px 16px;border-radius:{P.LL_RADIUS}}}
.ll-table{{width:100%;border-collapse:collapse;font-size:14px}}
.ll-table th{{text-align:left;background:{P.LL_CHICAGO};color:#fff;padding:8px 12px}}
.ll-table td{{padding:8px 12px;border-bottom:1px solid {P.LL_GRIDLINE};vertical-align:top}}
.ll-badge{{display:inline-block;font-size:11px;font-weight:600;text-transform:uppercase;
 letter-spacing:.03em;padding:2px 8px;border-radius:{P.LL_RADIUS};white-space:nowrap}}
.num{{text-align:right;font-variant-numeric:tabular-nums}}
.ll-limitations{{margin:0;padding-left:20px}}
.ll-limitations li{{margin-bottom:6px}}
.ll-provenance{{margin-top:40px;background:{P.LL_CARD_BG};color:{P.LL_CARD_TEXT};padding:20px 24px;
 border-radius:{P.LL_RADIUS};font-size:13px}}
.ll-prov-title{{font-family:var(--s);font-weight:700;font-size:16px;margin-bottom:8px}}
.ll-provenance div{{margin-bottom:4px;color:{P.LL_CARD_SUBTITLE}}}
.ll-provenance strong{{color:{P.LL_CARD_TEXT}}}
.ll-prov-inputs{{width:100%;border-collapse:collapse;margin-top:8px}}
.ll-prov-inputs th{{text-align:left;border-bottom:1px solid rgba(255,255,255,.12);padding:4px 8px;color:{P.LL_CARD_MUTED}}}
.ll-prov-inputs td{{padding:4px 8px;border-bottom:1px solid rgba(255,255,255,.08);color:{P.LL_CARD_SUBTITLE}}}
.ll-prov-brand{{margin-top:12px;font-family:var(--s);color:{P.LL_CARD_MUTED}}}
.mono{{font-family:ui-monospace,Consolas,monospace;font-size:12px;word-break:break-all}}
{draft_css}
@media print{{body{{background:#fff}}}}
"""


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #

def _partner_map(config) -> dict:
    partners = config.raw.get("partners") or config.basis.get("partners") or {}
    return partners if isinstance(partners, dict) else {}


def run(config_path: str, input_path: str, out_dir: str, *, final: bool = False) -> dict:
    config = load_config(config_path)
    partners = _partner_map(config)

    files = _iter_input_files(input_path)
    if not files:
        raise SystemExit(f"no input files found at {input_path}")

    outcomes = [_process_file(p, partners) for p in files]
    n_ok = sum(1 for o in outcomes if o.status == "ok")
    blocked = n_ok == 0

    # Status: nothing usable -> failed; any error/unresolved -> warnings; else clean.
    n_warn = sum(
        1 for o in outcomes
        if o.status != "ok" or (o.doc_type == "856" and o.retailer_source == "unresolved")
    )
    if blocked:
        status = "failed"
    elif n_warn:
        status = "warnings"
    else:
        status = "clean"

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Fold the partner map into provenance so a non-empty map is captured and
    # reproducible even though it lives outside the lib's config_hash payload.
    extra = {}
    if partners:
        blob = repr(sorted((str(k), str(v)) for k, v in partners.items())).encode()
        extra["partner_map"] = hashlib.sha256(blob).hexdigest()[:12]

    provenance = build_provenance(
        tool=TOOL, tool_version=TOOL_VERSION,
        inputs=[o.input_ref for o in outcomes], config=config,
        validation_status=validation_status_label(status, n_warn),
        extra=extra,
    )

    html_path = out / "edi-preflight-report.html"
    html_path.write_text(
        _report_html(config, outcomes, provenance, draft=not final, blocked=blocked),
        encoding="utf-8",
    )
    txt_path = out / "edi-preflight-report.txt"
    txt_path.write_text(_report_text(config, outcomes, provenance), encoding="utf-8")

    total_findings = sum(len(o.result.findings) for o in outcomes if o.result)
    result = {
        "status": "blocked" if blocked else "ok",
        "report": str(html_path),
        "txt": str(txt_path),
        "n_files": len(outcomes),
        "n_ok": n_ok,
        "total_findings": total_findings,
        "files": [
            {"filename": o.filename, "doc_type": o.doc_type, "status": o.status,
             "retailer": _RETAILER_LABELS.get(o.retailer, "Unknown"),
             "retailer_source": o.retailer_source}
            for o in outcomes
        ],
    }
    if blocked:
        result["readiness_report"] = str(html_path)
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="edi client mode",
        description="Pre-flight a client's EDI file(s) in engagement mode.",
    )
    ap.add_argument("--config", required=True)
    ap.add_argument("--input", required=True, help="an EDI file or a directory of them")
    ap.add_argument("--out", default="client-output")
    ap.add_argument("--final", action="store_true")
    args = ap.parse_args(argv)

    result = run(args.config, args.input, args.out, final=args.final)
    if result["status"] == "blocked":
        print(f"BLOCKED — no usable EDI. See {result['readiness_report']}")
        return 3
    print(f"processed {result['n_ok']}/{result['n_files']} file(s); "
          f"{result['total_findings']} ASN finding(s)")
    print(f"report -> {result['report']}\ntext   -> {result['txt']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
