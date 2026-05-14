import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.extract_850 import PurchaseOrder

_STYLES = getSampleStyleSheet()

_HEADER_BG = colors.HexColor("#4a7c9e")
_ROW_ALT = colors.HexColor("#f9f9f9")
_BORDER = colors.HexColor("#dddddd")
_MUTED = colors.HexColor("#666666")


def _date(value: str) -> str:
    if len(value) == 8 and value.isdigit():
        return f"{value[4:6]}/{value[6:8]}/{value[0:4]}"
    return value


def _currency(value: float) -> str:
    return f"${value:,.2f}"


def _qty(value: float) -> str:
    return str(int(value)) if value == int(value) else f"{value:g}"


_COL_STYLE = ParagraphStyle("col", fontName="Helvetica", fontSize=8, leading=10)
_COL_STYLE_R = ParagraphStyle(
    "col_r", fontName="Helvetica", fontSize=8, leading=10, alignment=2
)
_HEADER_STYLE = ParagraphStyle(
    "th", fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=colors.white
)
_HEADER_STYLE_R = ParagraphStyle(
    "th_r",
    fontName="Helvetica-Bold",
    fontSize=8,
    leading=10,
    textColor=colors.white,
    alignment=2,
)


def _p(text: str, style: ParagraphStyle = _COL_STYLE) -> Paragraph:
    return Paragraph(str(text), style)


def _build_header_section(po: PurchaseOrder) -> list:
    elements = []

    title_style = ParagraphStyle(
        "title", fontName="Helvetica-Bold", fontSize=14, leading=18
    )
    elements.append(Paragraph(f"Purchase Order #{po.po_number}", title_style))
    elements.append(Spacer(1, 4))

    meta_parts = [f"Retailer: {po.retailer.value.title()}"]
    meta_parts.append(f"Date: {_date(po.po_date)}")
    if po.department:
        meta_parts.append(f"Dept: {po.department}")
    if po.terms:
        meta_parts.append(f"Terms: {po.terms}")

    meta_style = ParagraphStyle(
        "meta", fontName="Helvetica", fontSize=9, leading=12, textColor=_MUTED
    )
    elements.append(Paragraph("  |  ".join(meta_parts), meta_style))
    elements.append(Spacer(1, 12))

    return elements


def _build_dates_table(po: PurchaseOrder) -> list:
    if not po.dates:
        return []

    elements = []
    elements.append(Paragraph("Key Dates", _STYLES["Heading3"]))

    data = [
        [_p("Date Type", _HEADER_STYLE), _p("Date", _HEADER_STYLE)],
    ]
    for d in po.dates:
        data.append([_p(d.label), _p(_date(d.date))])

    t = Table(data, colWidths=[2.5 * inch, 2 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _ROW_ALT]),
        ("GRID", (0, 0), (-1, -1), 0.5, _BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 12))
    return elements


def _build_addresses(po: PurchaseOrder) -> list:
    if not po.addresses:
        return []

    elements = []
    elements.append(Paragraph("Addresses", _STYLES["Heading3"]))

    addr_style = ParagraphStyle("addr", fontName="Helvetica", fontSize=8, leading=11)
    addr_bold = ParagraphStyle(
        "addr_b", fontName="Helvetica-Bold", fontSize=8, leading=11
    )

    _entity_labels = {"ST": "Ship To", "BT": "Bill To", "VN": "Vendor", "SU": "Supplier"}

    for addr in po.addresses:
        label = _entity_labels.get(addr.entity_code, addr.entity_code)
        elements.append(Paragraph(f"<b>{label}:</b> {addr.entity_name}", addr_bold))
        if addr.street:
            elements.append(Paragraph(addr.street, addr_style))
        if addr.city:
            city_line = addr.city
            if addr.state:
                city_line += f", {addr.state}"
            city_line += f" {addr.zip_code}"
            elements.append(Paragraph(city_line, addr_style))
        elements.append(Spacer(1, 6))

    elements.append(Spacer(1, 6))
    return elements


def _build_line_items_table(po: PurchaseOrder) -> list:
    elements = []
    elements.append(
        Paragraph(f"Line Items ({len(po.line_items)})", _STYLES["Heading3"])
    )

    data = [
        [
            _p("Line", _HEADER_STYLE),
            _p("Description", _HEADER_STYLE),
            _p("Qty", _HEADER_STYLE_R),
            _p("UOM", _HEADER_STYLE),
            _p("Unit Price", _HEADER_STYLE_R),
            _p("Extended", _HEADER_STYLE_R),
            _p("UPC", _HEADER_STYLE),
            _p("Item #", _HEADER_STYLE),
        ],
    ]

    for item in po.line_items:
        extended = item.quantity * item.unit_price
        item_num = item.buyers_item_number or item.vendor_item_number
        data.append([
            _p(item.line_number),
            _p(item.description),
            _p(_qty(item.quantity), _COL_STYLE_R),
            _p(item.unit_of_measure),
            _p(_currency(item.unit_price), _COL_STYLE_R),
            _p(_currency(extended), _COL_STYLE_R),
            _p(item.upc),
            _p(item_num),
        ])

    col_widths = [0.4 * inch, 2.0 * inch, 0.5 * inch, 0.4 * inch,
                  0.8 * inch, 0.8 * inch, 1.1 * inch, 1.0 * inch]
    t = Table(data, colWidths=col_widths)

    style_commands = [
        ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _ROW_ALT]),
        ("GRID", (0, 0), (-1, -1), 0.5, _BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    t.setStyle(TableStyle(style_commands))
    elements.append(t)
    elements.append(Spacer(1, 12))
    return elements


def _build_allowances_table(po: PurchaseOrder) -> list:
    if not po.header_allowances:
        return []

    elements = []
    elements.append(Paragraph("Header Allowances & Charges", _STYLES["Heading3"]))

    data = [
        [
            _p("Type", _HEADER_STYLE),
            _p("Code", _HEADER_STYLE),
            _p("Description", _HEADER_STYLE),
            _p("Amount", _HEADER_STYLE_R),
            _p("Percent", _HEADER_STYLE_R),
        ],
    ]

    for alw in po.header_allowances:
        data.append([
            _p("Allowance" if alw.is_allowance else "Charge"),
            _p(alw.code),
            _p(alw.description),
            _p(_currency(alw.amount) if alw.amount else "", _COL_STYLE_R),
            _p(f"{alw.percent}%" if alw.percent else "", _COL_STYLE_R),
        ])

    t = Table(data, colWidths=[0.9 * inch, 0.7 * inch, 2.5 * inch, 1.2 * inch, 0.9 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _ROW_ALT]),
        ("GRID", (0, 0), (-1, -1), 0.5, _BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 12))
    return elements


def _build_totals(po: PurchaseOrder) -> list:
    if not po.total_amount and not po.total_quantity:
        return []

    elements = []
    elements.append(Paragraph("Totals", _STYLES["Heading3"]))

    total_style = ParagraphStyle(
        "total", fontName="Helvetica", fontSize=9, leading=12
    )
    parts = []
    if po.total_line_items:
        parts.append(f"Line Items: {po.total_line_items}")
    if po.total_quantity:
        parts.append(f"Total Quantity: {_qty(po.total_quantity)}")
    if po.total_amount:
        parts.append(f"Total Amount: {_currency(po.total_amount)}")

    elements.append(Paragraph("  |  ".join(parts), total_style))
    return elements


def export_pdf(po: PurchaseOrder) -> bytes:
    """Export a PurchaseOrder as a formatted PDF report."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=0.5 * inch,
        rightMargin=0.5 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
    )

    story = []
    story.extend(_build_header_section(po))
    story.extend(_build_dates_table(po))
    story.extend(_build_addresses(po))
    story.extend(_build_line_items_table(po))
    story.extend(_build_allowances_table(po))
    story.extend(_build_totals(po))

    doc.build(story)
    return buf.getvalue()
