"""PDF export for 856 ASN validation report.

Three-layer report with severity badges and chargeback-dollar estimates.
Uses same visual style as export_pdf.py (850 export).
"""

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
)

from src.validate_856 import Finding, Severity, ValidationResult

_STYLES = getSampleStyleSheet()

_HEADER_BG = colors.HexColor("#4a7c9e")
_LIGHT_GRAY = colors.HexColor("#f5f5f5")
_BORDER = colors.HexColor("#dddddd")

_SEVERITY_COLORS = {
    Severity.BLOCKS_TRANSMISSION: colors.HexColor("#c0392b"),
    Severity.WILL_CAUSE_CHARGEBACK: colors.HexColor("#e67e22"),
    Severity.MAY_CAUSE_CHARGEBACK: colors.HexColor("#f1c40f"),
    Severity.COSMETIC: colors.HexColor("#95a5a6"),
}

_SEVERITY_BG = {
    Severity.BLOCKS_TRANSMISSION: colors.HexColor("#f8d7da"),
    Severity.WILL_CAUSE_CHARGEBACK: colors.HexColor("#ffeeba"),
    Severity.MAY_CAUSE_CHARGEBACK: colors.HexColor("#fff3cd"),
    Severity.COSMETIC: colors.HexColor("#e2e6ea"),
}


def _format_date(value: str) -> str:
    if len(value) == 8 and value.isdigit():
        return f"{value[4:6]}/{value[6:8]}/{value[0:4]}"
    return value


def _currency(value: float) -> str:
    return f"${value:,.2f}"


def _build_header(result: ValidationResult, retailer_label: str) -> list:
    elements = []

    title_style = _STYLES["Title"].clone("val_title")
    title_style.fontSize = 16
    title_style.spaceAfter = 4
    elements.append(Paragraph(
        f"{retailer_label} — 856 ASN Validation Report",
        title_style,
    ))

    # BSN summary line
    bsn = result.bsn_data
    meta_parts = []
    if bsn.get("shipment_id"):
        meta_parts.append(f"<b>Shipment:</b> {bsn['shipment_id']}")
    if bsn.get("date"):
        meta_parts.append(f"<b>Ship Date:</b> {_format_date(bsn['date'])}")
    if bsn.get("purpose_code"):
        purpose_labels = {"00": "Original", "01": "Cancellation", "05": "Replace"}
        meta_parts.append(
            f"<b>Purpose:</b> {purpose_labels.get(bsn['purpose_code'], bsn['purpose_code'])}"
        )

    if meta_parts:
        body = _STYLES["Normal"].clone("val_meta")
        elements.append(Paragraph(" &nbsp;&nbsp;|&nbsp;&nbsp; ".join(meta_parts), body))

    elements.append(Spacer(1, 8))

    # Verdict line
    if result.is_valid:
        pass_style = _STYLES["Normal"].clone("pass_style")
        pass_style.textColor = colors.HexColor("#155724")
        pass_style.fontSize = 11
        elements.append(Paragraph(
            "<b>PASS</b> — No issues found across all validation layers.",
            pass_style,
        ))
    else:
        severity = result.worst_severity
        count = len(result.findings)
        verdict_style = _STYLES["Normal"].clone("verdict")
        verdict_style.textColor = _SEVERITY_COLORS.get(severity, colors.black)
        verdict_style.fontSize = 11

        fee_part = ""
        if result.total_fees > 0:
            fee_part = f" &nbsp;&nbsp;|&nbsp;&nbsp; Est. Chargebacks: <b>{_currency(result.total_fees)}</b>"

        elements.append(Paragraph(
            f"<b>{severity.label.upper()}</b> — {count} finding{'s' if count != 1 else ''} detected.{fee_part}",
            verdict_style,
        ))

    elements.append(Spacer(1, 12))
    return elements


def _build_findings_section(
    findings: list[Finding],
    layer_title: str,
    layer_description: str,
) -> list:
    if not findings:
        return []

    elements = []
    section_title = _STYLES["Heading2"].clone(f"layer_{layer_title[:4]}")
    section_title.fontSize = 12
    elements.append(Paragraph(layer_title, section_title))

    desc_style = _STYLES["Normal"].clone("layer_desc")
    desc_style.fontSize = 8
    desc_style.textColor = colors.HexColor("#888888")
    elements.append(Paragraph(layer_description, desc_style))
    elements.append(Spacer(1, 6))

    header = ["Severity", "Segment", "Finding", "Fee"]
    data = [header]

    small = _STYLES["Normal"].clone("finding_cell")
    small.fontSize = 8
    small.leading = 10

    sorted_findings = sorted(findings, key=lambda f: f.severity.order)
    for f in sorted_findings:
        seg = f.segment_id
        if f.element_id:
            seg += f" > {f.element_id}"

        msg = f.message
        if f.location:
            msg += f" ({f.location})"

        fee = ""
        if f.has_fee:
            fee = f"{_currency(f.fee)}/{f.fee_per}"

        data.append([
            f.severity.label,
            seg,
            Paragraph(msg, small),
            fee,
        ])

    col_widths = [1.3 * inch, 0.8 * inch, 3.8 * inch, 0.9 * inch]
    table = Table(data, colWidths=col_widths, repeatRows=1)

    style_commands = [
        ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ALIGN", (3, 0), (3, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, _BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]

    # Color-code severity column by row
    for i, f in enumerate(sorted_findings, start=1):
        bg = _SEVERITY_BG.get(f.severity, _LIGHT_GRAY)
        style_commands.append(("BACKGROUND", (0, i), (0, i), bg))

    table.setStyle(TableStyle(style_commands))
    elements.append(table)
    elements.append(Spacer(1, 12))

    return elements


def _build_chargeback_table(result: ValidationResult) -> list:
    fee_findings = [f for f in result.sorted_findings() if f.has_fee]
    if not fee_findings:
        return []

    elements = []
    section_title = _STYLES["Heading2"].clone("cb_h")
    section_title.fontSize = 12
    elements.append(Paragraph("Chargeback Estimate", section_title))

    header = ["Rule", "Severity", "Fee", "Per"]
    data = [header]

    small = _STYLES["Normal"].clone("cb_cell")
    small.fontSize = 8
    small.leading = 10

    for f in fee_findings:
        msg = f.message
        if len(msg) > 80:
            msg = msg[:77] + "..."
        data.append([
            Paragraph(msg, small),
            f.severity.label,
            _currency(f.fee),
            f.fee_per,
        ])

    # Total row
    data.append([
        "Total Estimated Chargebacks",
        "",
        _currency(result.total_fees),
        "",
    ])

    col_widths = [3.2 * inch, 1.4 * inch, 0.9 * inch, 0.7 * inch]
    table = Table(data, colWidths=col_widths, repeatRows=1)

    style_commands = [
        ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, _BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        # Bold + gray background on total row
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), _LIGHT_GRAY),
    ]

    table.setStyle(TableStyle(style_commands))
    elements.append(table)
    elements.append(Spacer(1, 12))

    return elements


def export_validation_pdf(
    result: ValidationResult,
    retailer_label: str,
) -> bytes:
    """Generate a PDF validation report from an 856 ValidationResult."""
    buf = io.BytesIO()

    shipment_id = result.bsn_data.get("shipment_id", "")
    title = f"856 Validation — {shipment_id}" if shipment_id else "856 Validation Report"

    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
        title=title,
    )

    elements = []
    elements.extend(_build_header(result, retailer_label))

    # Layer 1: Structural
    elements.extend(_build_findings_section(
        result.structural_findings,
        "Layer 1: Structural",
        "Envelope completeness, segment ordering, control number matching.",
    ))

    # Layer 2: Field-Level
    elements.extend(_build_findings_section(
        result.field_findings,
        "Layer 2: Field-Level",
        "Required fields, date formats, qualifier codes, numeric validation.",
    ))

    # Layer 3: Retailer-Specific
    elements.extend(_build_findings_section(
        result.retailer_findings,
        f"Layer 3: {retailer_label}-Specific",
        "Retailer compliance rules, OTIF requirements, and chargeback triggers.",
    ))

    # Chargeback estimate table
    elements.extend(_build_chargeback_table(result))

    # Footer
    footer_style = _STYLES["Normal"].clone("footer")
    footer_style.fontSize = 7
    footer_style.textColor = colors.HexColor("#999999")
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Generated by EDI Pre-flight", footer_style))

    doc.build(elements)
    return buf.getvalue()
