from dataclasses import dataclass, field
from enum import Enum

from src.x12_tokenizer import Segment, TokenizeResult


class Retailer(Enum):
    WALMART = "walmart"
    AMAZON = "amazon"
    UNFI = "unfi"
    KEHE = "kehe"
    COSTCO = "costco"
    UNKNOWN = "unknown"


class TransactionType(Enum):
    PURCHASE_ORDER_850 = "850"
    ASN_856 = "856"
    UNKNOWN = "unknown"


# GS01 functional identifier → transaction type
_GS01_MAP = {
    "PO": TransactionType.PURCHASE_ORDER_850,
    "SH": TransactionType.ASN_856,
}

# Patterns to match against ISA06/ISA08/GS02/GS03 (case-insensitive substring)
_RETAILER_PATTERNS: list[tuple[str, Retailer]] = [
    ("walmart", Retailer.WALMART),
    ("wal-mart", Retailer.WALMART),
    ("wmt", Retailer.WALMART),
    ("amazon", Retailer.AMAZON),
    ("amzn", Retailer.AMAZON),
    ("unfi", Retailer.UNFI),
    ("kehe", Retailer.KEHE),
    ("costco", Retailer.COSTCO),
]

# Known DUNS/EDI IDs for retailers (exact match after stripping whitespace)
_RETAILER_IDS: dict[str, Retailer] = {
    "0078742000000": Retailer.WALMART,
    "0078742052892": Retailer.WALMART,
    "0569813430000": Retailer.KEHE,
    "0054370330000": Retailer.KEHE,
    "4253138601CH": Retailer.COSTCO,
}


@dataclass
class InterchangeEnvelope:
    sender_qualifier: str
    sender_id: str
    receiver_qualifier: str
    receiver_id: str
    date: str
    time: str
    control_number: str
    version: str
    test_indicator: str


@dataclass
class FunctionalGroup:
    functional_id: str
    sender_code: str
    receiver_code: str
    date: str
    time: str
    control_number: str
    version: str
    transaction_type: TransactionType


@dataclass
class TransactionSet:
    transaction_type: TransactionType
    control_number: str
    segments: list[Segment] = field(default_factory=list)


@dataclass
class Envelope:
    interchange: InterchangeEnvelope
    groups: list[FunctionalGroup] = field(default_factory=list)
    transactions: list[TransactionSet] = field(default_factory=list)
    retailer: Retailer = Retailer.UNKNOWN
    all_segments: list[Segment] = field(default_factory=list)


class EnvelopeError(Exception):
    def __init__(self, message: str, hint: str = ""):
        self.hint = hint
        super().__init__(message)


def _detect_retailer_from_id(value: str) -> Retailer:
    stripped = value.strip()
    if stripped in _RETAILER_IDS:
        return _RETAILER_IDS[stripped]
    lower = stripped.lower()
    for pattern, retailer in _RETAILER_PATTERNS:
        if pattern in lower:
            return retailer
    return Retailer.UNKNOWN


def detect_retailer(result: TokenizeResult) -> Retailer:
    """Detect retailer from ISA and GS segments.

    For inbound 850s: retailer is the sender (ISA06, GS02).
    For outbound 856s: retailer is the receiver (ISA08, GS03).
    Checks both directions and returns the first match."""
    candidates: list[str] = []
    for seg in result.segments:
        if seg.segment_id == "ISA":
            candidates.append(seg.element(6))   # sender ID
            candidates.append(seg.element(8))   # receiver ID
        elif seg.segment_id == "GS":
            candidates.append(seg.element(2))   # sender code
            candidates.append(seg.element(3))   # receiver code

    for candidate in candidates:
        retailer = _detect_retailer_from_id(candidate)
        if retailer != Retailer.UNKNOWN:
            return retailer
    return Retailer.UNKNOWN


def _parse_interchange(isa: Segment) -> InterchangeEnvelope:
    return InterchangeEnvelope(
        sender_qualifier=isa.element(5).strip(),
        sender_id=isa.element(6).strip(),
        receiver_qualifier=isa.element(7).strip(),
        receiver_id=isa.element(8).strip(),
        date=isa.element(9).strip(),
        time=isa.element(10).strip(),
        control_number=isa.element(13).strip(),
        version=isa.element(12).strip(),
        test_indicator=isa.element(15).strip(),
    )


def _parse_functional_group(gs: Segment) -> FunctionalGroup:
    func_id = gs.element(1).strip()
    return FunctionalGroup(
        functional_id=func_id,
        sender_code=gs.element(2).strip(),
        receiver_code=gs.element(3).strip(),
        date=gs.element(4).strip(),
        time=gs.element(5).strip(),
        control_number=gs.element(6).strip(),
        version=gs.element(8).strip(),
        transaction_type=_GS01_MAP.get(func_id, TransactionType.UNKNOWN),
    )


def parse_envelope(result: TokenizeResult) -> Envelope:
    """Parse tokenized segments into an envelope structure."""
    segments = result.segments
    if not segments:
        raise EnvelopeError("No segments to parse.")

    isa_segments = [s for s in segments if s.segment_id == "ISA"]
    if not isa_segments:
        raise EnvelopeError(
            "No ISA segment found in tokenized output.",
            hint="The document may be missing its interchange header.",
        )

    iea_segments = [s for s in segments if s.segment_id == "IEA"]
    if not iea_segments:
        raise EnvelopeError(
            "No IEA segment found — the interchange envelope is not closed.",
            hint="The document may be truncated. Check that the complete "
            "document was pasted.",
        )

    interchange = _parse_interchange(isa_segments[0])

    groups: list[FunctionalGroup] = []
    for seg in segments:
        if seg.segment_id == "GS":
            groups.append(_parse_functional_group(seg))

    transactions: list[TransactionSet] = []
    current_tx: TransactionSet | None = None
    for seg in segments:
        if seg.segment_id == "ST":
            tx_type_code = seg.element(1).strip()
            tx_type = TransactionType.PURCHASE_ORDER_850 if tx_type_code == "850" else (
                TransactionType.ASN_856 if tx_type_code == "856" else TransactionType.UNKNOWN
            )
            current_tx = TransactionSet(
                transaction_type=tx_type,
                control_number=seg.element(2).strip(),
            )
        elif seg.segment_id == "SE":
            if current_tx is not None:
                transactions.append(current_tx)
                current_tx = None
        elif current_tx is not None:
            current_tx.segments.append(seg)

    retailer = detect_retailer(result)

    return Envelope(
        interchange=interchange,
        groups=groups,
        transactions=transactions,
        retailer=retailer,
        all_segments=segments,
    )
