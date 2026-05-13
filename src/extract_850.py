from dataclasses import dataclass, field

from src.envelope import Envelope, Retailer, TransactionType, EnvelopeError
from src.x12_tokenizer import Segment


@dataclass
class Address:
    entity_code: str
    entity_name: str
    id_qualifier: str = ""
    id_code: str = ""
    street: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    country: str = ""


@dataclass
class Allowance:
    indicator: str
    code: str
    description: str = ""
    amount: float = 0.0
    percent: float = 0.0
    handling_code: str = ""
    reference: str = ""
    level: str = "header"

    @property
    def is_allowance(self) -> bool:
        return self.indicator == "A"

    @property
    def is_charge(self) -> bool:
        return self.indicator == "C"


@dataclass
class LineItem:
    line_number: str
    quantity: float
    unit_of_measure: str
    unit_price: float
    price_basis: str = ""
    buyers_item_number: str = ""
    upc: str = ""
    vendor_item_number: str = ""
    gtin_14: str = ""
    sku: str = ""
    description: str = ""
    pack_quantity: str = ""
    pack_size: str = ""
    pack_uom: str = ""
    weight: float = 0.0
    weight_unit: str = ""
    is_catch_weight: bool = False
    allowances: list[Allowance] = field(default_factory=list)
    all_product_ids: dict[str, str] = field(default_factory=dict)


@dataclass
class DateReference:
    qualifier: str
    date: str
    label: str = ""


_DTM_LABELS = {
    "002": "Requested Delivery",
    "004": "Purchase Order Date",
    "010": "Requested Ship",
    "037": "Ship Not Before",
    "038": "Ship Not After",
    "063": "Do Not Deliver After",
    "064": "Do Not Deliver Before",
    "118": "Requested Pick-up",
    "175": "Cancel If Not Shipped By",
}

_PRODUCT_ID_FIELDS = {
    "IN": "buyers_item_number",
    "UP": "upc",
    "VN": "vendor_item_number",
    "UK": "gtin_14",
    "SK": "sku",
    "EN": "upc",
    "BP": "buyers_item_number",
}


@dataclass
class PurchaseOrder:
    po_number: str
    po_type: str
    po_date: str
    purpose_code: str = ""
    department: str = ""
    retailer: Retailer = Retailer.UNKNOWN
    dates: list[DateReference] = field(default_factory=list)
    addresses: list[Address] = field(default_factory=list)
    header_allowances: list[Allowance] = field(default_factory=list)
    line_items: list[LineItem] = field(default_factory=list)
    total_line_items: int = 0
    total_quantity: float = 0.0
    total_amount: float = 0.0
    terms: str = ""

    @property
    def ship_to(self) -> Address | None:
        for addr in self.addresses:
            if addr.entity_code == "ST":
                return addr
        return None

    @property
    def bill_to(self) -> Address | None:
        for addr in self.addresses:
            if addr.entity_code == "BT":
                return addr
        return None

    @property
    def all_allowances(self) -> list[Allowance]:
        result = list(self.header_allowances)
        for item in self.line_items:
            result.extend(item.allowances)
        return result


class ExtractionError(Exception):
    def __init__(self, message: str, hint: str = ""):
        self.hint = hint
        super().__init__(message)


def _parse_float(value: str) -> float:
    try:
        return float(value) if value else 0.0
    except ValueError:
        return 0.0


def _extract_product_ids(po1: Segment) -> dict[str, str]:
    """Extract qualifier/value pairs from PO106+ (pairs at positions 6/7, 8/9, etc.)."""
    ids: dict[str, str] = {}
    i = 6
    while i + 1 <= len(po1.elements):
        qualifier = po1.element(i).strip()
        value = po1.element(i + 1).strip()
        if qualifier and value:
            ids[qualifier] = value
        i += 2
    return ids


def _parse_allowance(sac: Segment, level: str = "header") -> Allowance:
    return Allowance(
        indicator=sac.element(1).strip(),
        code=sac.element(2).strip(),
        amount=_parse_float(sac.element(5)),
        percent=_parse_float(sac.element(7)),
        handling_code=sac.element(12).strip(),
        description=sac.element(15).strip(),
        reference=sac.element(14).strip() or sac.element(13).strip(),
        level=level,
    )


def extract_850(envelope: Envelope) -> PurchaseOrder:
    """Extract structured purchase order data from a parsed 850 envelope."""
    if not envelope.transactions:
        raise ExtractionError(
            "No transaction sets found in this document.",
            hint="Expected at least one ST/SE pair containing an 850.",
        )

    tx = envelope.transactions[0]
    if tx.transaction_type != TransactionType.PURCHASE_ORDER_850:
        raise ExtractionError(
            f"Expected an 850 Purchase Order but found transaction type "
            f"'{tx.transaction_type.value}'.",
            hint="This document appears to be a different EDI transaction type.",
        )

    segments = tx.segments
    po = PurchaseOrder(
        po_number="",
        po_type="",
        po_date="",
        retailer=envelope.retailer,
    )

    current_line: LineItem | None = None
    current_address: Address | None = None
    in_n1_loop = False

    for seg in segments:
        sid = seg.segment_id

        if sid == "BEG":
            po.purpose_code = seg.element(1).strip()
            po.po_type = seg.element(2).strip()
            po.po_number = seg.element(3).strip()
            po.po_date = seg.element(5).strip()

        elif sid == "REF":
            qualifier = seg.element(1).strip()
            if qualifier == "DP":
                po.department = seg.element(2).strip()

        elif sid == "DTM" and current_line is None:
            qualifier = seg.element(1).strip()
            po.dates.append(DateReference(
                qualifier=qualifier,
                date=seg.element(2).strip(),
                label=_DTM_LABELS.get(qualifier, qualifier),
            ))

        elif sid == "ITD":
            desc = seg.element(12).strip() if len(seg.elements) >= 12 else ""
            if not desc:
                desc = seg.element(9).strip() if len(seg.elements) >= 9 else ""
            po.terms = desc

        elif sid == "SAC" and current_line is None:
            po.header_allowances.append(_parse_allowance(seg, level="header"))

        elif sid == "N1":
            if current_line is not None:
                continue
            in_n1_loop = True
            current_address = Address(
                entity_code=seg.element(1).strip(),
                entity_name=seg.element(2).strip(),
                id_qualifier=seg.element(3).strip(),
                id_code=seg.element(4).strip(),
            )

        elif sid == "N3" and in_n1_loop and current_address is not None:
            parts = [seg.element(1).strip()]
            line2 = seg.element(2).strip()
            if line2:
                parts.append(line2)
            current_address.street = ", ".join(parts)

        elif sid == "N4" and in_n1_loop and current_address is not None:
            current_address.city = seg.element(1).strip()
            current_address.state = seg.element(2).strip()
            current_address.zip_code = seg.element(3).strip()
            current_address.country = seg.element(4).strip()
            po.addresses.append(current_address)
            current_address = None
            in_n1_loop = False

        elif sid == "PO1":
            if current_address is not None and in_n1_loop:
                po.addresses.append(current_address)
                current_address = None
                in_n1_loop = False

            product_ids = _extract_product_ids(seg)
            current_line = LineItem(
                line_number=seg.element(1).strip(),
                quantity=_parse_float(seg.element(2)),
                unit_of_measure=seg.element(3).strip(),
                unit_price=_parse_float(seg.element(4)),
                price_basis=seg.element(5).strip(),
                all_product_ids=product_ids,
            )
            for qualifier, field_name in _PRODUCT_ID_FIELDS.items():
                if qualifier in product_ids:
                    setattr(current_line, field_name, product_ids[qualifier])

            if current_line.unit_of_measure in ("LB", "KG", "OZ", "CW"):
                current_line.is_catch_weight = True

            po.line_items.append(current_line)

        elif sid == "PID" and current_line is not None:
            current_line.description = seg.element(5).strip()

        elif sid == "PO4" and current_line is not None:
            current_line.pack_quantity = seg.element(1).strip()
            current_line.pack_size = seg.element(2).strip()
            current_line.pack_uom = seg.element(3).strip()

        elif sid == "MEA" and current_line is not None:
            qualifier = seg.element(1).strip()
            if qualifier == "WT":
                current_line.weight = _parse_float(seg.element(3))
                current_line.weight_unit = seg.element(2).strip()
                current_line.is_catch_weight = True

        elif sid == "SAC" and current_line is not None:
            current_line.allowances.append(_parse_allowance(seg, level="line_item"))

        elif sid == "CTT":
            po.total_line_items = int(_parse_float(seg.element(1)))
            po.total_quantity = _parse_float(seg.element(2))

        elif sid == "AMT":
            qualifier = seg.element(1).strip()
            if qualifier == "35":
                po.total_amount = _parse_float(seg.element(2))

    return po
