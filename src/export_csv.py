import csv
import io

from src.extract_850 import PurchaseOrder


def _format_date(value: str) -> str:
    if len(value) == 8 and value.isdigit():
        return f"{value[4:6]}/{value[6:8]}/{value[0:4]}"
    return value


def export_csv(po: PurchaseOrder) -> str:
    """Export a PurchaseOrder as CSV with one row per line item.

    Header fields are denormalized into each row so the CSV is
    self-contained and importable into Excel or an ERP system.
    """
    buf = io.StringIO()
    writer = csv.writer(buf)

    writer.writerow([
        "PO Number",
        "PO Date",
        "Retailer",
        "Ship To",
        "Line",
        "Description",
        "Qty",
        "UOM",
        "Unit Price",
        "Extended",
        "UPC",
        "Buyer Item #",
        "Vendor Item #",
        "GTIN-14",
        "SKU",
    ])

    ship_to = po.ship_to
    ship_to_name = ship_to.entity_name if ship_to else ""

    for item in po.line_items:
        writer.writerow([
            po.po_number,
            _format_date(po.po_date),
            po.retailer.value,
            ship_to_name,
            item.line_number,
            item.description,
            item.quantity if item.quantity != int(item.quantity) else int(item.quantity),
            item.unit_of_measure,
            f"{item.unit_price:.2f}",
            f"{item.quantity * item.unit_price:.2f}",
            item.upc,
            item.buyers_item_number,
            item.vendor_item_number,
            item.gtin_14,
            item.sku,
        ])

    return buf.getvalue()
