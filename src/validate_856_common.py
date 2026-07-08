"""Shared 856 ASN retailer validation logic.

Common checks used by all retailer-specific validators:
- HL loop hierarchy (X12 735: Shipment→Order→Tare→Pack→Item)
- SSCC-18 barcode validation (MAN at the Pack/Tare container levels)
- Required segments per HL level
- Catch-weight MEA*WT enforcement (SN1 item detail at the Item level)

Each retailer module provides its own fee schedule and retailer name,
then calls run_retailer_checks() to apply the common rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.validate_856 import (
    Finding,
    Severity,
    ValidationResult,
    collect_all_nodes,
)

# Standard HL parent→child mapping (most retailers use this).
# X12 element 735 nesting is Shipment(S)→Order(O)→Tare(T)→Pack(P)→Item(I).
# Tare is optional: an Order may nest Packs directly when there is no
# pallet/tare level, so both O→T→P and O→P are valid.
STANDARD_VALID_CHILDREN = {
    "S": {"O"},
    "O": {"T", "P"},
    "T": {"P"},
    "P": {"I"},
    "I": set(),
}


@dataclass
class RetailerConfig:
    """Configuration for a retailer's 856 validation rules."""
    name: str
    fees: dict[str, dict]
    valid_children: dict[str, set[str]] = field(default_factory=lambda: dict(STANDARD_VALID_CHILDREN))
    allowed_bsn_purpose_codes: set[str] = field(default_factory=lambda: {"00", "01", "05"})
    require_sscc18: bool = True
    require_td5: bool = True
    require_dtm_011: bool = True
    require_ship_to: bool = True
    require_prf: bool = True
    check_catch_weight: bool = True


def validate_sscc18(value: str) -> str | None:
    """Validate SSCC-18 format. Returns error message or None if valid."""
    digits = value.strip()
    if len(digits) != 18:
        return f"SSCC-18 '{digits}' is {len(digits)} digits — must be exactly 18."
    if not digits.isdigit():
        return f"SSCC-18 '{digits}' contains non-numeric characters."

    # Mod-10 check digit validation
    total = 0
    for i, ch in enumerate(digits[:17]):
        d = int(ch)
        if i % 2 == 0:
            total += d * 3
        else:
            total += d
    expected_check = (10 - (total % 10)) % 10
    actual_check = int(digits[17])
    if actual_check != expected_check:
        return f"SSCC-18 '{digits}' has invalid check digit: expected {expected_check}, got {actual_check}."
    return None


def _get_fee(config: RetailerConfig, rule_id: str) -> dict:
    return config.fees.get(rule_id, {"fee": 0.0, "per": "occurrence"})


def check_hl_hierarchy(result: ValidationResult, config: RetailerConfig) -> None:
    """Verify HL levels follow strict parent-child relationships."""
    all_nodes = collect_all_nodes(result.hl_tree)

    for node in all_nodes:
        if node.level_code not in config.valid_children:
            result.findings.append(Finding(
                rule_id="unknown_hl_level",
                severity=Severity.BLOCKS_TRANSMISSION,
                layer="retailer",
                message=f"HL loop {node.hl_id} has unknown level code '{node.level_code}' — {config.name} expects S, O, T, P, or I.",
                segment_id="HL",
                location=f"HL loop {node.hl_id}",
            ))
            continue

        allowed = config.valid_children[node.level_code]
        for child in node.children:
            if child.level_code not in allowed:
                fee_info = _get_fee(config, "wrong_hl_hierarchy")
                if allowed:
                    expected = ", ".join(sorted(allowed))
                    result.findings.append(Finding(
                        rule_id="wrong_hl_hierarchy",
                        severity=Severity.BLOCKS_TRANSMISSION,
                        layer="retailer",
                        message=f"HL loop {child.hl_id} (level '{child.level_code}') is a child of HL loop {node.hl_id} (level '{node.level_code}') — expected child level '{expected}' per {config.name} S→O→T→P→I hierarchy.",
                        segment_id="HL",
                        location=f"HL loop {child.hl_id}",
                        fee=fee_info["fee"],
                        fee_per=fee_info["per"],
                    ))
                else:
                    result.findings.append(Finding(
                        rule_id="wrong_hl_hierarchy",
                        severity=Severity.BLOCKS_TRANSMISSION,
                        layer="retailer",
                        message=f"HL loop {child.hl_id} (level '{child.level_code}') is a child of HL loop {node.hl_id} (level '{node.level_code}') — item level should not have children.",
                        segment_id="HL",
                        location=f"HL loop {child.hl_id}",
                        fee=fee_info["fee"],
                        fee_per=fee_info["per"],
                    ))


def check_shipment_level(result: ValidationResult, config: RetailerConfig) -> None:
    """Check required segments at shipment level (S)."""
    all_nodes = collect_all_nodes(result.hl_tree)
    shipment_nodes = [n for n in all_nodes if n.level_code == "S"]

    for s_node in shipment_nodes:
        seg_ids = {seg.segment_id for seg in s_node.segments}

        if config.require_td5 and "TD5" not in seg_ids:
            fee_info = _get_fee(config, "missing_carrier")
            result.findings.append(Finding(
                rule_id="missing_carrier",
                severity=Severity.MAY_CAUSE_CHARGEBACK,
                layer="retailer",
                message="No TD5 carrier routing segment at shipment level.",
                segment_id="TD5",
                location=f"HL loop {s_node.hl_id} (shipment)",
                fee=fee_info["fee"],
                fee_per=fee_info["per"],
            ))

        if config.require_dtm_011:
            dtm_segs = [seg for seg in s_node.segments if seg.segment_id == "DTM"]
            has_ship_date = any(seg.element(1).strip() == "011" for seg in dtm_segs)
            if not has_ship_date:
                fee_info = _get_fee(config, "missing_ship_date")
                result.findings.append(Finding(
                    rule_id="missing_ship_date",
                    severity=Severity.BLOCKS_TRANSMISSION,
                    layer="retailer",
                    message="No DTM*011 (shipped date) at shipment level.",
                    segment_id="DTM",
                    location=f"HL loop {s_node.hl_id} (shipment)",
                    fee=fee_info["fee"],
                    fee_per=fee_info["per"],
                ))

        if config.require_ship_to:
            n1_segs = [seg for seg in s_node.segments if seg.segment_id == "N1"]
            has_ship_to = any(seg.element(1).strip() == "ST" for seg in n1_segs)
            if not has_ship_to:
                fee_info = _get_fee(config, "missing_ship_to")
                result.findings.append(Finding(
                    rule_id="missing_ship_to",
                    severity=Severity.BLOCKS_TRANSMISSION,
                    layer="retailer",
                    message="No N1*ST (ship-to party) at shipment level.",
                    segment_id="N1",
                    location=f"HL loop {s_node.hl_id} (shipment)",
                    fee=fee_info["fee"],
                    fee_per=fee_info["per"],
                ))


def check_order_level(result: ValidationResult, config: RetailerConfig) -> None:
    """Check required segments at order level (O)."""
    if not config.require_prf:
        return

    all_nodes = collect_all_nodes(result.hl_tree)
    order_nodes = [n for n in all_nodes if n.level_code == "O"]

    for o_node in order_nodes:
        has_prf = any(seg.segment_id == "PRF" for seg in o_node.segments)
        if not has_prf:
            fee_info = _get_fee(config, "missing_po_reference")
            result.findings.append(Finding(
                rule_id="missing_po_reference",
                severity=Severity.BLOCKS_TRANSMISSION,
                layer="retailer",
                message=f"No PRF (Purchase Order Reference) at order-level HL loop {o_node.hl_id}.",
                segment_id="PRF",
                location=f"HL loop {o_node.hl_id} (order)",
                fee=fee_info["fee"],
                fee_per=fee_info["per"],
            ))


def check_container_level(result: ValidationResult, config: RetailerConfig) -> None:
    """Check SSCC-18 barcodes (MAN) at the container levels — Tare (T) and Pack (P).

    In X12 856 the SSCC-18 identifies a physical shipping unit, so it
    belongs on the tare (pallet) and/or pack (carton) HL loops, not on the
    item-detail level.
    """
    if not config.require_sscc18:
        return

    all_nodes = collect_all_nodes(result.hl_tree)
    container_nodes = [n for n in all_nodes if n.level_code in ("T", "P")]

    for node in container_nodes:
        level_name = "tare" if node.level_code == "T" else "pack"
        man_segs = [seg for seg in node.segments if seg.segment_id == "MAN"]
        if not man_segs:
            fee_info = _get_fee(config, "missing_sscc18")
            result.findings.append(Finding(
                rule_id="missing_sscc18",
                severity=Severity.WILL_CAUSE_CHARGEBACK,
                layer="retailer",
                message=f"No MAN segment (SSCC-18 barcode) at {level_name}-level HL loop {node.hl_id}.",
                segment_id="MAN",
                location=f"HL loop {node.hl_id} ({level_name})",
                fee=fee_info["fee"],
                fee_per=fee_info["per"],
            ))
        else:
            for man in man_segs:
                barcode = man.element(2).strip()
                if barcode:
                    error = validate_sscc18(barcode)
                    if error:
                        fee_info = _get_fee(config, "invalid_sscc18_format")
                        result.findings.append(Finding(
                            rule_id="invalid_sscc18_format",
                            severity=Severity.WILL_CAUSE_CHARGEBACK,
                            layer="retailer",
                            message=error,
                            segment_id="MAN",
                            element_id="MAN02",
                            location=f"HL loop {node.hl_id} ({level_name})",
                            fee=fee_info["fee"],
                            fee_per=fee_info["per"],
                        ))


def check_item_level(result: ValidationResult, config: RetailerConfig) -> None:
    """Check catch-weight items have MEA*WT at the item level (I).

    SN1 item detail lives on the item-level HL loop, so the catch-weight
    weight (MEA*WT) is required there for LB/KG/OZ units of measure.
    """
    if not config.check_catch_weight:
        return

    all_nodes = collect_all_nodes(result.hl_tree)
    item_nodes = [n for n in all_nodes if n.level_code == "I"]

    for i_node in item_nodes:
        sn1_segs = [seg for seg in i_node.segments if seg.segment_id == "SN1"]
        if not sn1_segs:
            continue

        sn1 = sn1_segs[0]
        uom = sn1.element(3).strip()
        if uom in ("LB", "KG", "OZ"):
            mea_segs = [seg for seg in i_node.segments if seg.segment_id == "MEA"]
            has_weight_mea = any(
                seg.element(1).strip() == "WT" for seg in mea_segs
            )
            if not has_weight_mea:
                fee_info = _get_fee(config, "missing_catch_weight")
                line_num = sn1.element(1).strip() or "?"
                result.findings.append(Finding(
                    rule_id="missing_catch_weight",
                    severity=Severity.WILL_CAUSE_CHARGEBACK,
                    layer="retailer",
                    message=f"Catch-weight item (line {line_num}, UOM={uom}) shipped without MEA*WT segment.",
                    segment_id="MEA",
                    location=f"HL loop {i_node.hl_id} (item)",
                    fee=fee_info["fee"],
                    fee_per=fee_info["per"],
                ))


def check_bsn_purpose(result: ValidationResult, config: RetailerConfig) -> None:
    """Check BSN01 purpose code against the retailer's accepted set.

    The layer-2 field check accepts any X12-valid purpose code (00/01/05);
    individual retailers accept a narrower set (e.g. UNFI takes 00 only), so
    this catches retailer-specific rejections that the generic check misses.
    """
    purpose = result.bsn_data.get("purpose_code", "").strip()
    if purpose and purpose not in config.allowed_bsn_purpose_codes:
        allowed = ", ".join(sorted(config.allowed_bsn_purpose_codes))
        result.findings.append(Finding(
            rule_id="retailer_bsn_purpose_not_accepted",
            severity=Severity.BLOCKS_TRANSMISSION,
            layer="retailer",
            message=f"BSN01 purpose code '{purpose}' is not accepted by {config.name} — allowed: {allowed}.",
            segment_id="BSN",
            element_id="BSN01",
        ))


def run_retailer_checks(result: ValidationResult, config: RetailerConfig) -> ValidationResult:
    """Run all standard retailer checks using the given configuration."""
    if not result.hl_tree:
        return result

    check_bsn_purpose(result, config)
    check_hl_hierarchy(result, config)
    check_shipment_level(result, config)
    check_order_level(result, config)
    check_container_level(result, config)
    check_item_level(result, config)

    return result
