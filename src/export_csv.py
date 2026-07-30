import csv
import io

from src.extract_850 import PurchaseOrder

# Leading characters a spreadsheet treats as the start of a formula. A cell of
# untrusted EDI text beginning with one of these could execute when the CSV is
# opened in Excel/Sheets (CSV injection), so we defuse it.
_FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


def _neutralize(value):
    """Prefix a formula-triggering string cell with an apostrophe so the
    spreadsheet renders it as literal text. Non-string cells pass through."""
    if isinstance(value, str) and value and value[0] in _FORMULA_TRIGGERS:
        return "'" + value
    return value


def export_850_csv(po: PurchaseOrder) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)

    writer.writerow([
        "PO Number",
        "Retailer",
        "PO Date",
        "Line #",
        "Description",
        "Qty",
        "UOM",
        "Unit Price",
        "Extended Price",
        "UPC",
        "Buyer Item #",
        "Vendor Item #",
        "Catch Weight",
        "Weight",
        "Weight Unit",
        "Pack Qty",
        "Pack Size",
        "Pack UOM",
        "Ship To Name",
        "Ship To Address",
        "Ship To City",
        "Ship To State",
        "Ship To Zip",
    ])

    ship_to = po.ship_to

    for item in po.line_items:
        writer.writerow([_neutralize(cell) for cell in [
            po.po_number,
            po.retailer.value,
            po.po_date,
            item.line_number,
            item.description,
            item.quantity,
            item.unit_of_measure,
            item.unit_price,
            round(item.quantity * item.unit_price, 2),
            item.upc,
            item.buyers_item_number,
            item.vendor_item_number,
            "Y" if item.is_catch_weight else "",
            item.weight if item.weight else "",
            item.weight_unit if item.weight else "",
            item.pack_quantity,
            item.pack_size,
            item.pack_uom,
            ship_to.entity_name if ship_to else "",
            ship_to.street if ship_to else "",
            ship_to.city if ship_to else "",
            ship_to.state if ship_to else "",
            ship_to.zip_code if ship_to else "",
        ]])

    return buf.getvalue()
