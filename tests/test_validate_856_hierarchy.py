"""Tests for the corrected 856 HL hierarchy model (S→O→T→P→I).

The validator previously modelled Item as the parent of Pack and checked
the SSCC-18 (MAN) at the item level and the SN1 item detail at the pack
level — the inverse of the X12 element-735 nesting. These tests pin the
corrected behaviour: a correctly-built ASN passes (including an optional
Tare level), and an inverted ASN that the old model wrongly accepted now
fails.
"""

from pathlib import Path

from src.envelope import parse_envelope
from src.validate_856 import Severity, collect_all_nodes, validate_856
from src.validate_856_common import STANDARD_VALID_CHILDREN
from src.validate_856_walmart import validate_856_walmart
from src.x12_tokenizer import tokenize

SAMPLES = Path(__file__).parent.parent / "samples" / "walmart"


def _load_and_validate(filename: str):
    raw = (SAMPLES / filename).read_text()
    result = validate_856(parse_envelope(tokenize(raw)))
    return validate_856_walmart(result)


class TestModelDefinition:
    def test_nesting_is_shipment_order_tare_pack_item(self):
        assert STANDARD_VALID_CHILDREN["S"] == {"O"}
        assert STANDARD_VALID_CHILDREN["O"] == {"T", "P"}  # tare optional
        assert STANDARD_VALID_CHILDREN["T"] == {"P"}
        assert STANDARD_VALID_CHILDREN["P"] == {"I"}
        assert STANDARD_VALID_CHILDREN["I"] == set()


class TestCorrectlyBuiltAsnPasses:
    def setup_method(self):
        self.result = _load_and_validate("856_correct_hierarchy.edi")

    def test_is_valid(self):
        assert self.result.is_valid, [f.message for f in self.result.findings]

    def test_no_findings(self):
        assert len(self.result.findings) == 0

    def test_no_fees(self):
        assert self.result.total_fees == 0.0

    def test_tare_level_is_accepted(self):
        levels = {n.level_code for n in collect_all_nodes(self.result.hl_tree)}
        assert "T" in levels  # the fixture exercises an optional Tare level
        assert not any(f.rule_id == "unknown_hl_level" for f in self.result.findings)


class TestInvertedAsnFails:
    def setup_method(self):
        self.result = _load_and_validate("856_inverted_hierarchy.edi")

    def test_not_valid(self):
        assert not self.result.is_valid

    def test_blocks_transmission(self):
        assert self.result.worst_severity == Severity.BLOCKS_TRANSMISSION

    def test_flags_wrong_hierarchy(self):
        hier = [f for f in self.result.findings if f.rule_id == "wrong_hl_hierarchy"]
        assert len(hier) >= 1

    def test_flags_missing_sscc_at_pack(self):
        # SSCC-18 was placed on the item level; the pack carries no MAN.
        sscc = [f for f in self.result.findings if f.rule_id == "missing_sscc18"]
        assert len(sscc) == 1
        assert "pack" in sscc[0].location


class TestSSCCCheckedAtContainerLevel:
    def test_valid_sscc_at_pack_produces_no_finding(self):
        result = _load_and_validate("856_correct_hierarchy.edi")
        sscc = [
            f for f in result.findings
            if f.rule_id in ("missing_sscc18", "invalid_sscc18_format")
        ]
        assert sscc == []


class TestCatchWeightCheckedAtItemLevel:
    def test_catch_weight_item_without_mea_is_flagged(self):
        # SN1 with a weight UOM (LB) at the item level and no MEA*WT.
        raw = (
            "ISA*00*          *00*          *ZZ*CINDERHAVEN    *ZZ*WALMART        "
            "*260510*1430*U*00501*000000001*0*P*>~"
            "GS*SH*CINDERHAVEN*WALMART*20260510*143000*1*X*005010~"
            "ST*856*0001~"
            "BSN*00*SHP001*20260510*1430~"
            "HL*1**S~"
            "TD5*B*2*UPSN*M~"
            "DTM*011*20260510~"
            "N1*ST*WALMART DC 6025*92*0006025~"
            "N3*123 MAIN ST~"
            "N4*BENTONVILLE*AR*72712*US~"
            "HL*2*1*O~"
            "PRF*PO123~"
            "HL*3*2*P~"
            "MAN*GM*000000000000000000~"
            "HL*4*3*I~"
            "SN1*1*150*LB~"
            "SE*15*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        result = validate_856(parse_envelope(tokenize(raw)))
        result = validate_856_walmart(result)
        cw = [f for f in result.findings if f.rule_id == "missing_catch_weight"]
        assert len(cw) == 1
        assert "item" in cw[0].location
