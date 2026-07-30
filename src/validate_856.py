"""856 ASN validation — structural + field-level checks.

Structural validation (layer 1): envelope completeness, segment ordering,
control number matching, required envelope segments present.

Field-level validation (layer 2): required fields present, date formats,
qualifier code values, numeric fields.

Retailer-specific validation (layer 3) is added by validate_856_walmart.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from src.envelope import Envelope, TransactionType, EnvelopeError
from src.x12_tokenizer import Segment


class Severity(Enum):
    BLOCKS_TRANSMISSION = "blocks-transmission"
    WILL_CAUSE_CHARGEBACK = "will-cause-chargeback"
    MAY_CAUSE_CHARGEBACK = "may-cause-chargeback"
    COSMETIC = "cosmetic"

    @property
    def order(self) -> int:
        return {
            "blocks-transmission": 1,
            "will-cause-chargeback": 2,
            "may-cause-chargeback": 3,
            "cosmetic": 4,
        }[self.value]

    @property
    def label(self) -> str:
        return {
            "blocks-transmission": "Blocks Transmission",
            "will-cause-chargeback": "Will Cause Chargeback",
            "may-cause-chargeback": "May Cause Chargeback",
            "cosmetic": "Cosmetic",
        }[self.value]


@dataclass
class Finding:
    """A single validation finding."""
    rule_id: str
    severity: Severity
    layer: str  # "structural", "field", "retailer"
    message: str
    segment_id: str = ""
    element_id: str = ""
    location: str = ""  # e.g. "HL loop 3 (tare)"
    fee: float = 0.0
    fee_per: str = ""  # "load", "case", "item", "document", "occurrence"

    @property
    def has_fee(self) -> bool:
        return self.fee > 0.0


@dataclass
class HLNode:
    """A parsed HL loop node."""
    hl_id: str
    parent_id: str
    level_code: str  # S=Shipment, O=Order, T=Tare, P=Pack, I=Item
    segments: list[Segment] = field(default_factory=list)
    children: list[HLNode] = field(default_factory=list)


@dataclass
class ValidationResult:
    """Complete validation result for an 856 document."""
    findings: list[Finding] = field(default_factory=list)
    hl_tree: list[HLNode] = field(default_factory=list)
    bsn_data: dict[str, str] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        return len(self.findings) == 0

    @property
    def structural_findings(self) -> list[Finding]:
        return [f for f in self.findings if f.layer == "structural"]

    @property
    def field_findings(self) -> list[Finding]:
        return [f for f in self.findings if f.layer == "field"]

    @property
    def retailer_findings(self) -> list[Finding]:
        return [f for f in self.findings if f.layer == "retailer"]

    @property
    def worst_severity(self) -> Severity | None:
        if not self.findings:
            return None
        return min(self.findings, key=lambda f: f.severity.order).severity

    @property
    def total_fees(self) -> float:
        """Raw sum of every fee. NOTE: fees are per differing unit bases
        ($/load, $/case, $/item) and are not additive into one meaningful
        figure — this is an internal aggregate; present fee_breakdown to
        users instead."""
        return sum(f.fee for f in self.findings)

    @property
    def fee_breakdown(self) -> list[dict]:
        """Chargeback exposure grouped by fee unit basis.

        A $500/load fine and a $100/case fine are dimensionally different and
        cannot be summed into a single dollar figure. Each finding represents
        one affected unit of its basis, so we report the affected-unit count
        and a per-basis subtotal (fee x affected units) rather than a single
        cross-basis total.
        """
        groups: dict[str, dict] = {}
        for f in self.findings:
            if f.fee <= 0.0:
                continue
            basis = f.fee_per or "occurrence"
            group = groups.setdefault(
                basis, {"fee_per": basis, "count": 0, "subtotal": 0.0}
            )
            group["count"] += 1
            group["subtotal"] += f.fee
        return [groups[basis] for basis in sorted(groups)]

    def sorted_findings(self) -> list[Finding]:
        return sorted(self.findings, key=lambda f: f.severity.order)


# --- Date format validation ---

_CCYYMMDD = re.compile(r"^\d{8}$")
_HHMM = re.compile(r"^\d{4}$")


def _is_valid_ccyymmdd(value: str) -> bool:
    """Check if value matches CCYYMMDD format with valid month/day ranges."""
    if not _CCYYMMDD.match(value):
        return False
    month = int(value[4:6])
    day = int(value[6:8])
    return 1 <= month <= 12 and 1 <= day <= 31


def _is_valid_hhmm(value: str) -> bool:
    """Check if value matches HHMM format with valid hour/minute ranges."""
    if not _HHMM.match(value):
        return False
    hour = int(value[:2])
    minute = int(value[2:4])
    return 0 <= hour <= 23 and 0 <= minute <= 59


# --- HL tree parsing ---

def _parse_hl_tree(segments: list[Segment]) -> list[HLNode]:
    """Parse HL segments into a tree of nodes with their child segments."""
    nodes: dict[str, HLNode] = {}
    current_node: HLNode | None = None
    roots: list[HLNode] = []

    for seg in segments:
        if seg.segment_id == "HL":
            hl_id = seg.element(1).strip()
            parent_id = seg.element(2).strip()
            level_code = seg.element(3).strip()
            node = HLNode(
                hl_id=hl_id,
                parent_id=parent_id,
                level_code=level_code,
            )
            nodes[hl_id] = node
            current_node = node
            if not parent_id:
                roots.append(node)
            elif parent_id in nodes:
                nodes[parent_id].children.append(node)
        elif current_node is not None:
            current_node.segments.append(seg)

    return roots


def collect_all_nodes(roots: list[HLNode]) -> list[HLNode]:
    """Flatten HL tree into a list in document order."""
    result: list[HLNode] = []

    def _walk(node: HLNode) -> None:
        result.append(node)
        for child in node.children:
            _walk(child)

    for root in roots:
        _walk(root)
    return result


# --- Layer 1: Structural validation ---

def _validate_structural(envelope: Envelope, result: ValidationResult) -> None:
    """Check envelope completeness, segment ordering, control numbers."""

    # Check transaction type
    if not envelope.transactions:
        result.findings.append(Finding(
            rule_id="no_transaction_set",
            severity=Severity.BLOCKS_TRANSMISSION,
            layer="structural",
            message="No transaction set found — expected at least one ST/SE pair.",
        ))
        return

    tx = envelope.transactions[0]
    if tx.transaction_type != TransactionType.ASN_856:
        result.findings.append(Finding(
            rule_id="wrong_transaction_type",
            severity=Severity.BLOCKS_TRANSMISSION,
            layer="structural",
            message=f"Expected an 856 ASN but found transaction type '{tx.transaction_type.value}'.",
            segment_id="ST",
        ))
        return

    # Check GS functional ID
    if envelope.groups:
        gs = envelope.groups[0]
        if gs.functional_id != "SH":
            result.findings.append(Finding(
                rule_id="wrong_gs_functional_id",
                severity=Severity.BLOCKS_TRANSMISSION,
                layer="structural",
                message=f"GS01 functional identifier is '{gs.functional_id}' — expected 'SH' for ASN.",
                segment_id="GS",
                element_id="GS01",
            ))

    segments = tx.segments

    # Check for BSN segment
    bsn_segments = [s for s in segments if s.segment_id == "BSN"]
    if not bsn_segments:
        result.findings.append(Finding(
            rule_id="missing_bsn",
            severity=Severity.BLOCKS_TRANSMISSION,
            layer="structural",
            message="No BSN (Beginning Segment for Ship Notice) found.",
            segment_id="BSN",
        ))
    else:
        bsn = bsn_segments[0]
        result.bsn_data = {
            "purpose_code": bsn.element(1).strip(),
            "shipment_id": bsn.element(2).strip(),
            "date": bsn.element(3).strip(),
            "time": bsn.element(4).strip(),
        }

    # Check for HL segments
    hl_segments = [s for s in segments if s.segment_id == "HL"]
    if not hl_segments:
        result.findings.append(Finding(
            rule_id="no_hl_loops",
            severity=Severity.BLOCKS_TRANSMISSION,
            layer="structural",
            message="No HL (Hierarchical Level) segments found — 856 requires at least a shipment-level HL.",
            segment_id="HL",
        ))
        return

    # Parse the HL tree
    result.hl_tree = _parse_hl_tree(segments)

    # Check for shipment-level HL
    all_nodes = collect_all_nodes(result.hl_tree)

    # Detect HL nodes unreachable from any root — their parent reference points
    # to an HL that is missing or appears later in document order. Without this
    # check they (and their MAN/SN1 segments) are dropped from validation, so a
    # broken ASN could report FEWER findings and lower chargeback exposure than
    # a correct one. That is the opposite of what this tool must do.
    reachable_ids = {n.hl_id for n in all_nodes}
    orphan_ids = list(dict.fromkeys(
        seg_id for s in hl_segments
        if (seg_id := s.element(1).strip()) and seg_id not in reachable_ids
    ))
    if orphan_ids:
        result.findings.append(Finding(
            rule_id="hl_parent_not_found",
            severity=Severity.BLOCKS_TRANSMISSION,
            layer="structural",
            message=(
                "HL segment(s) reference a parent that is missing or appears "
                "out of document order, so their contents cannot be validated: "
                + ", ".join(f"HL {i}" for i in orphan_ids)
                + "."
            ),
            segment_id="HL",
        ))

    shipment_nodes = [n for n in all_nodes if n.level_code == "S"]
    if not shipment_nodes:
        result.findings.append(Finding(
            rule_id="no_shipment_hl",
            severity=Severity.BLOCKS_TRANSMISSION,
            layer="structural",
            message="No shipment-level HL (code 'S') found — every 856 must have a shipment level.",
            segment_id="HL",
        ))

    # Check control number matching (ISA/IEA, GS/GE)
    isa_control = envelope.interchange.control_number
    all_segs = envelope.all_segments
    iea_segs = [s for s in all_segs if s.segment_id == "IEA"]
    if iea_segs:
        iea_control = iea_segs[0].element(2).strip()
        if isa_control != iea_control:
            result.findings.append(Finding(
                rule_id="isa_iea_mismatch",
                severity=Severity.BLOCKS_TRANSMISSION,
                layer="structural",
                message=f"ISA control number '{isa_control}' does not match IEA control number '{iea_control}'.",
                segment_id="IEA",
            ))

    if envelope.groups:
        gs_control = envelope.groups[0].control_number
        ge_segs = [s for s in all_segs if s.segment_id == "GE"]
        if ge_segs:
            ge_control = ge_segs[0].element(2).strip()
            if gs_control != ge_control:
                result.findings.append(Finding(
                    rule_id="gs_ge_mismatch",
                    severity=Severity.BLOCKS_TRANSMISSION,
                    layer="structural",
                    message=f"GS control number '{gs_control}' does not match GE control number '{ge_control}'.",
                    segment_id="GE",
                ))

    # Check ST/SE segment count
    se_segs = [s for s in all_segs if s.segment_id == "SE"]
    if se_segs:
        se_count_str = se_segs[0].element(1).strip()
        if se_count_str and not se_count_str.isdigit():
            result.findings.append(Finding(
                rule_id="se_count_nonnumeric",
                severity=Severity.BLOCKS_TRANSMISSION,
                layer="structural",
                message=f"SE01 segment count '{se_count_str}' is not a number.",
                segment_id="SE",
                element_id="SE01",
            ))
        elif se_count_str:
            se_count = int(se_count_str)
            # SE count includes ST and SE themselves
            actual_count = len(segments) + 2  # +2 for ST and SE
            if se_count != actual_count:
                result.findings.append(Finding(
                    rule_id="se_count_mismatch",
                    severity=Severity.MAY_CAUSE_CHARGEBACK,
                    layer="structural",
                    message=f"SE01 segment count is {se_count} but actual count is {actual_count}.",
                    segment_id="SE",
                    element_id="SE01",
                ))


# --- Layer 2: Field-level validation ---

def _validate_fields(envelope: Envelope, result: ValidationResult) -> None:
    """Check required fields present, date formats, qualifier codes."""
    if not envelope.transactions:
        return

    tx = envelope.transactions[0]
    if tx.transaction_type != TransactionType.ASN_856:
        return

    segments = tx.segments

    # BSN field validation
    bsn_segments = [s for s in segments if s.segment_id == "BSN"]
    if bsn_segments:
        bsn = bsn_segments[0]
        purpose = bsn.element(1).strip()
        if purpose and purpose not in ("00", "01", "05"):
            result.findings.append(Finding(
                rule_id="invalid_bsn_purpose",
                severity=Severity.BLOCKS_TRANSMISSION,
                layer="field",
                message=f"BSN01 purpose code '{purpose}' is not valid — expected 00 (Original), 01 (Cancellation), or 05 (Replace).",
                segment_id="BSN",
                element_id="BSN01",
            ))

        shipment_id = bsn.element(2).strip()
        if not shipment_id:
            result.findings.append(Finding(
                rule_id="missing_bsn_shipment_id",
                severity=Severity.BLOCKS_TRANSMISSION,
                layer="field",
                message="BSN02 shipment identification number is missing.",
                segment_id="BSN",
                element_id="BSN02",
            ))

        bsn_date = bsn.element(3).strip()
        if bsn_date and not _is_valid_ccyymmdd(bsn_date):
            result.findings.append(Finding(
                rule_id="invalid_bsn_date",
                severity=Severity.MAY_CAUSE_CHARGEBACK,
                layer="field",
                message=f"BSN03 date '{bsn_date}' is not in CCYYMMDD format.",
                segment_id="BSN",
                element_id="BSN03",
            ))

        bsn_time = bsn.element(4).strip()
        if bsn_time and not _is_valid_hhmm(bsn_time):
            result.findings.append(Finding(
                rule_id="invalid_bsn_time",
                severity=Severity.MAY_CAUSE_CHARGEBACK,
                layer="field",
                message=f"BSN04 time '{bsn_time}' is not in HHMM format.",
                segment_id="BSN",
                element_id="BSN04",
            ))

    # DTM date format validation
    for seg in segments:
        if seg.segment_id == "DTM":
            qualifier = seg.element(1).strip()
            date_val = seg.element(2).strip()
            if date_val and not _is_valid_ccyymmdd(date_val):
                result.findings.append(Finding(
                    rule_id="invalid_dtm_date",
                    severity=Severity.MAY_CAUSE_CHARGEBACK,
                    layer="field",
                    message=f"DTM*{qualifier} date '{date_val}' is not in CCYYMMDD format.",
                    segment_id="DTM",
                    element_id="DTM02",
                ))

    # TD5 transport method validation
    for seg in segments:
        if seg.segment_id == "TD5":
            transport = seg.element(4).strip()
            if transport and transport not in ("M", "R", "S", "A", "LT"):
                result.findings.append(Finding(
                    rule_id="invalid_transport_method",
                    severity=Severity.COSMETIC,
                    layer="field",
                    message=f"TD503 transport method '{transport}' is not a standard code (M=Motor, R=Rail, S=Ocean, A=Air, LT=LTL).",
                    segment_id="TD5",
                    element_id="TD503",
                ))

    # MAN qualifier validation
    for seg in segments:
        if seg.segment_id == "MAN":
            qualifier = seg.element(1).strip()
            if qualifier and qualifier not in ("GM", "CP"):
                result.findings.append(Finding(
                    rule_id="invalid_man_qualifier",
                    severity=Severity.MAY_CAUSE_CHARGEBACK,
                    layer="field",
                    message=f"MAN01 qualifier '{qualifier}' is not valid — expected GM (SSCC-18) or CP.",
                    segment_id="MAN",
                    element_id="MAN01",
                ))

    # SN1 quantity validation (must be numeric and positive)
    for seg in segments:
        if seg.segment_id == "SN1":
            qty_str = seg.element(2).strip()
            if qty_str:
                try:
                    qty = float(qty_str)
                    if qty <= 0:
                        result.findings.append(Finding(
                            rule_id="invalid_sn1_quantity",
                            severity=Severity.BLOCKS_TRANSMISSION,
                            layer="field",
                            message=f"SN102 shipped quantity '{qty_str}' must be greater than zero.",
                            segment_id="SN1",
                            element_id="SN102",
                        ))
                except ValueError:
                    result.findings.append(Finding(
                        rule_id="invalid_sn1_quantity",
                        severity=Severity.BLOCKS_TRANSMISSION,
                        layer="field",
                        message=f"SN102 shipped quantity '{qty_str}' is not a valid number.",
                        segment_id="SN1",
                        element_id="SN102",
                    ))
            uom = seg.element(3).strip()
            if not uom:
                result.findings.append(Finding(
                    rule_id="missing_sn1_uom",
                    severity=Severity.BLOCKS_TRANSMISSION,
                    layer="field",
                    message="SN103 unit of measure is missing.",
                    segment_id="SN1",
                    element_id="SN103",
                ))


# --- Public API ---

def validate_856(envelope: Envelope) -> ValidationResult:
    """Run structural and field-level validation on an 856 ASN.

    Returns a ValidationResult with findings from both layers.
    Retailer-specific validation should be added by calling the
    appropriate retailer module (e.g., validate_856_walmart) afterward.
    """
    result = ValidationResult()
    _validate_structural(envelope, result)
    _validate_fields(envelope, result)
    return result
