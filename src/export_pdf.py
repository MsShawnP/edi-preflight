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

from src.extract_850 import PurchaseOrder
from src.formatting import format_currency, format_edi_date, format_quantity

_STYLES = getSampleStyleSheet()

_HEADER_BG = colors.HexColor("#1f2e7a")
_LIGHT_GRAY = colors.HexColor("#f2f2f2")
_BORDER = colors.HexColor("#d9d9d9")


def _build_header_section(po: PurchaseOrder) -> list:
    elements = []

    title_style = _STYLES["Title"].clone("po_title")
    title_style.fontSize = 16
    title_style.spaceAfter = 4

    elements.append(Paragraph(
        f"{po.retailer.value.title()} — PO #{po.po_number}",
        title_style,
    ))

    meta_parts = [
        f"<b>Date:</b> {format_edi_date(po.po_date)}",
        f"<b>Type:</b> {po.po_type}",
    ]
    if po.department:
        meta_parts.append(f"<b>Dept:</b> {po.department}")
    if po.terms:
        meta_parts.append(f"<b>Terms:</b> {po.terms}")

    body = _STYLES["Normal"].clone("meta")
    meta = Paragraph(" &nbsp;&nbsp;|&nbsp;&nbsp; ".join(meta_parts), body)
    elements.append(meta)
    elements.append(Spacer(1, 12))

    if po.dates:
        for d in po.dates:
            elements.append(Paragraph(
                f"<b>{d.label}:</b> {format_edi_date(d.date)}",
                _STYLES["Normal"],
            ))
        elements.append(Spacer(1, 8))

    ship_to = po.ship_to
    if ship_to:
        elements.append(Paragraph("<b>Ship To:</b>", _STYLES["Normal"]))
        addr_parts = [ship_to.entity_name]
        if ship_to.street:
            addr_parts.append(ship_to.street)
        city_line = ""
        if ship_to.city:
            city_line = ship_to.city
            if ship_to.state:
                city_line += f", {ship_to.state}"
            city_line += f" {ship_to.zip_code}"
        if city_line:
            addr_parts.append(city_line)
        elements.append(Paragraph("<br/>".join(addr_parts), _STYLES["Normal"]))
        elements.append(Spacer(1, 12))

    return elements


def _build_line_items_table(po: PurchaseOrder) -> list:
    elements = []

    section_title = _STYLES["Heading2"].clone("section_h")
    section_title.fontSize = 12
    elements.append(Paragraph(f"Line Items ({len(po.line_items)})", section_title))

    header = ["Line", "Description", "Qty", "UOM", "Unit Price", "Extended", "UPC"]
    data = [header]

    small = _STYLES["Normal"].clone("cell")
    small.fontSize = 8
    small.leading = 10

    for item in po.line_items:
        desc = item.description
        if item.is_catch_weight:
            desc += " [CW]"
        data.append([
            item.line_number,
            Paragraph(desc, small),
            format_quantity(item.quantity),
            item.unit_of_measure,
            format_currency(item.unit_price),
            format_currency(item.quantity * item.unit_price),
            item.upc,
        ])

    col_widths = [0.4 * inch, 2.2 * inch, 0.6 * inch, 0.5 * inch,
                  0.8 * inch, 0.8 * inch, 1.1 * inch]

    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ALIGN", (2, 0), (5, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _LIGHT_GRAY]),
        ("GRID", (0, 0), (-1, -1), 0.5, _BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 12))

    return elements


def _build_allowances_section(po: PurchaseOrder) -> list:
    if not po.header_allowances:
        return []

    elements = []
    section_title = _STYLES["Heading2"].clone("alw_h")
    section_title.fontSize = 12
    elements.append(Paragraph("Header Allowances & Charges", section_title))

    header = ["Type", "Code", "Description", "Amount", "Percent"]
    data = [header]

    for alw in po.header_allowances:
        data.append([
            "Allowance" if alw.is_allowance else "Charge",
            alw.code,
            alw.description,
            format_currency(alw.amount) if alw.amount else "",
            f"{alw.percent}%" if alw.percent else "",
        ])

    col_widths = [0.8 * inch, 0.7 * inch, 2.5 * inch, 0.9 * inch, 0.7 * inch]
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (3, 0), (4, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _LIGHT_GRAY]),
        ("GRID", (0, 0), (-1, -1), 0.5, _BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 12))

    return elements


def _build_totals_section(po: PurchaseOrder) -> list:
    if not po.total_amount and not po.total_quantity:
        return []

    elements = []
    section_title = _STYLES["Heading2"].clone("tot_h")
    section_title.fontSize = 12
    elements.append(Paragraph("Totals", section_title))

    parts = []
    if po.total_line_items:
        parts.append(f"<b>Line Items:</b> {po.total_line_items}")
    if po.total_quantity:
        parts.append(f"<b>Total Quantity:</b> {format_quantity(po.total_quantity)}")
    if po.total_amount:
        parts.append(f"<b>Total Amount:</b> {format_currency(po.total_amount)}")

    elements.append(Paragraph(" &nbsp;&nbsp;|&nbsp;&nbsp; ".join(parts), _STYLES["Normal"]))

    return elements


def export_850_pdf(po: PurchaseOrder) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
        title=f"PO {po.po_number}",
    )

    elements = []
    elements.extend(_build_header_section(po))
    elements.extend(_build_line_items_table(po))
    elements.extend(_build_allowances_section(po))
    elements.extend(_build_totals_section(po))

    footer_style = _STYLES["Normal"].clone("footer")
    footer_style.fontSize = 7
    footer_style.textColor = colors.HexColor("#666666")
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Generated by EDI Pre-flight", footer_style))

    doc.build(elements)
    return buf.getvalue()
