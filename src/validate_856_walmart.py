"""Walmart-specific 856 ASN validation (layer 3).

Checks retailer-specific rules on top of structural and field-level validation:
- HL loop ordering (S→O→I→P strict hierarchy)
- SSCC-18 barcode format and check digit
- Catch-weight items must have MEA*WT segment
- Required segments at each HL level (TD5, DTM*011, N1*ST, PRF, MAN)
- Chargeback-dollar attribution per Walmart OTIF fee schedule
"""

from __future__ import annotations

from src.validate_856 import (
    Finding,
    HLNode,
    Severity,
    ValidationResult,
    _collect_all_nodes,
)


# --- Walmart chargeback fee schedule ---

_FEES = {
    "missing_asn": {"fee": 500.00, "per": "load"},
    "late_asn": {"fee": 500.00, "per": "load"},
    "missing_sscc18": {"fee": 100.00, "per": "case"},
    "invalid_sscc18_format": {"fee": 100.00, "per": "case"},
    "wrong_hl_hierarchy": {"fee": 0.00, "per": "document"},
    "missing_catch_weight": {"fee": 100.00, "per": "item"},
    "missing_po_reference": {"fee": 0.00, "per": "order"},
    "missing_ship_to": {"fee": 0.00, "per": "document"},
    "missing_ship_date": {"fee": 0.00, "per": "document"},
    "missing_carrier": {"fee": 0.00, "per": "document"},
}

# Expected HL level order: S must come before O, O before I, I before P
_HL_ORDER = {"S": 0, "O": 1, "I": 2, "P": 3}

# Walmart strict parent→child mapping
_VALID_CHILDREN = {
    "S": {"O"},
    "O": {"I"},
    "I": {"P"},
    "P": set(),
}


def _validate_sscc18(value: str) -> str | None:
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


def _check_hl_hierarchy(result: ValidationResult) -> None:
    """Verify HL levels follow strict S→O→I→P parent-child relationships."""
    all_nodes = _collect_all_nodes(result.hl_tree)

    for node in all_nodes:
        if node.level_code not in _VALID_CHILDREN:
            result.findings.append(Finding(
                rule_id="unknown_hl_level",
                severity=Severity.BLOCKS_TRANSMISSION,
                layer="retailer",
                message=f"HL loop {node.hl_id} has unknown level code '{node.level_code}' — Walmart expects S, O, I, or P.",
                segment_id="HL",
                location=f"HL loop {node.hl_id}",
            ))
            continue

        allowed = _VALID_CHILDREN[node.level_code]
        for child in node.children:
            if child.level_code not in allowed:
                fee_info = _FEES["wrong_hl_hierarchy"]
                if allowed:
                    expected = ", ".join(sorted(allowed))
                    result.findings.append(Finding(
                        rule_id="wrong_hl_hierarchy",
                        severity=Severity.BLOCKS_TRANSMISSION,
                        layer="retailer",
                        message=f"HL loop {child.hl_id} (level '{child.level_code}') is a child of HL loop {node.hl_id} (level '{node.level_code}') — expected child level '{expected}' per Walmart S→O→I→P hierarchy.",
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
                        message=f"HL loop {child.hl_id} (level '{child.level_code}') is a child of HL loop {node.hl_id} (level '{node.level_code}') — pack level should not have children.",
                        segment_id="HL",
                        location=f"HL loop {child.hl_id}",
                        fee=fee_info["fee"],
                        fee_per=fee_info["per"],
                    ))


def _check_shipment_level(result: ValidationResult) -> None:
    """Check required segments at shipment level (S)."""
    all_nodes = _collect_all_nodes(result.hl_tree)
    shipment_nodes = [n for n in all_nodes if n.level_code == "S"]

    for s_node in shipment_nodes:
        seg_ids = {seg.segment_id for seg in s_node.segments}

        # TD5 — carrier routing
        if "TD5" not in seg_ids:
            fee_info = _FEES["missing_carrier"]
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

        # DTM*011 — ship date
        dtm_segs = [seg for seg in s_node.segments if seg.segment_id == "DTM"]
        has_ship_date = any(seg.element(1).strip() == "011" for seg in dtm_segs)
        if not has_ship_date:
            fee_info = _FEES["missing_ship_date"]
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

        # N1*ST — ship-to party
        n1_segs = [seg for seg in s_node.segments if seg.segment_id == "N1"]
        has_ship_to = any(seg.element(1).strip() == "ST" for seg in n1_segs)
        if not has_ship_to:
            fee_info = _FEES["missing_ship_to"]
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


def _check_order_level(result: ValidationResult) -> None:
    """Check required segments at order level (O)."""
    all_nodes = _collect_all_nodes(result.hl_tree)
    order_nodes = [n for n in all_nodes if n.level_code == "O"]

    for o_node in order_nodes:
        # PRF — purchase order reference
        has_prf = any(seg.segment_id == "PRF" for seg in o_node.segments)
        if not has_prf:
            fee_info = _FEES["missing_po_reference"]
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


def _check_tare_level(result: ValidationResult) -> None:
    """Check required segments at tare/container level (I)."""
    all_nodes = _collect_all_nodes(result.hl_tree)
    tare_nodes = [n for n in all_nodes if n.level_code == "I"]

    for i_node in tare_nodes:
        # MAN — marks and numbers (SSCC-18)
        man_segs = [seg for seg in i_node.segments if seg.segment_id == "MAN"]
        if not man_segs:
            fee_info = _FEES["missing_sscc18"]
            result.findings.append(Finding(
                rule_id="missing_sscc18",
                severity=Severity.WILL_CAUSE_CHARGEBACK,
                layer="retailer",
                message=f"No MAN segment (SSCC-18 barcode) at tare-level HL loop {i_node.hl_id}.",
                segment_id="MAN",
                location=f"HL loop {i_node.hl_id} (tare)",
                fee=fee_info["fee"],
                fee_per=fee_info["per"],
            ))
        else:
            for man in man_segs:
                barcode = man.element(2).strip()
                if barcode:
                    error = _validate_sscc18(barcode)
                    if error:
                        fee_info = _FEES["invalid_sscc18_format"]
                        result.findings.append(Finding(
                            rule_id="invalid_sscc18_format",
                            severity=Severity.WILL_CAUSE_CHARGEBACK,
                            layer="retailer",
                            message=error,
                            segment_id="MAN",
                            element_id="MAN02",
                            location=f"HL loop {i_node.hl_id} (tare)",
                            fee=fee_info["fee"],
                            fee_per=fee_info["per"],
                        ))


def _check_pack_level(result: ValidationResult) -> None:
    """Check catch-weight items have MEA*WT at pack level (P)."""
    all_nodes = _collect_all_nodes(result.hl_tree)
    pack_nodes = [n for n in all_nodes if n.level_code == "P"]

    for p_node in pack_nodes:
        # Check if this is a catch-weight item (shipped by weight UOM)
        sn1_segs = [seg for seg in p_node.segments if seg.segment_id == "SN1"]
        if not sn1_segs:
            continue

        sn1 = sn1_segs[0]
        uom = sn1.element(3).strip()
        if uom in ("LB", "KG", "OZ"):
            # This is a catch-weight item — check for MEA*WT
            mea_segs = [seg for seg in p_node.segments if seg.segment_id == "MEA"]
            has_weight_mea = any(
                seg.element(1).strip() == "WT" for seg in mea_segs
            )
            if not has_weight_mea:
                fee_info = _FEES["missing_catch_weight"]
                line_num = sn1.element(1).strip() or "?"
                result.findings.append(Finding(
                    rule_id="missing_catch_weight",
                    severity=Severity.WILL_CAUSE_CHARGEBACK,
                    layer="retailer",
                    message=f"Catch-weight item (line {line_num}, UOM={uom}) shipped without MEA*WT segment.",
                    segment_id="MEA",
                    location=f"HL loop {p_node.hl_id} (pack)",
                    fee=fee_info["fee"],
                    fee_per=fee_info["per"],
                ))


def validate_856_walmart(result: ValidationResult) -> ValidationResult:
    """Add Walmart-specific validation findings to an existing ValidationResult.

    Call this after validate_856() has run structural and field-level checks.
    """
    if not result.hl_tree:
        # No HL tree to validate — structural issues already flagged
        return result

    _check_hl_hierarchy(result)
    _check_shipment_level(result)
    _check_order_level(result)
    _check_tare_level(result)
    _check_pack_level(result)

    return result
