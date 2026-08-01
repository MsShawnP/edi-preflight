"""Tests for Walmart-specific 856 validation rules (layer 3)."""

from pathlib import Path

from src.envelope import parse_envelope
from src.validate_856 import validate_856, Severity
from src.validate_856_walmart import validate_856_walmart, validate_sscc18
from src.x12_tokenizer import tokenize

SAMPLES = Path(__file__).parent.parent / "samples" / "walmart"


def _load_and_validate(filename: str):
    raw = (SAMPLES / filename).read_text()
    tokens = tokenize(raw)
    envelope = parse_envelope(tokens)
    result = validate_856(envelope)
    return validate_856_walmart(result)


# --- Clean document ---

class TestCleanDocumentWalmart:
    def setup_method(self):
        self.result = _load_and_validate("856_clean.edi")

    def test_no_retailer_findings(self):
        assert len(self.result.retailer_findings) == 0

    def test_is_valid(self):
        assert self.result.is_valid

    def test_total_fees_zero(self):
        assert self.result.total_fees == 0.0


# --- Wrong HL order ---

class TestWrongHLOrder:
    def setup_method(self):
        self.result = _load_and_validate("856_wrong_hl_order.edi")

    def test_finds_hierarchy_violation(self):
        hierarchy_findings = [
            f for f in self.result.findings if f.rule_id == "wrong_hl_hierarchy"
        ]
        assert len(hierarchy_findings) >= 1

    def test_severity_blocks_transmission(self):
        f = next(f for f in self.result.findings if f.rule_id == "wrong_hl_hierarchy")
        assert f.severity == Severity.BLOCKS_TRANSMISSION

    def test_layer_is_retailer(self):
        f = next(f for f in self.result.findings if f.rule_id == "wrong_hl_hierarchy")
        assert f.layer == "retailer"


# --- Missing MEA for catch-weight ---

class TestMissingCatchWeight:
    def setup_method(self):
        self.result = _load_and_validate("856_missing_mea.edi")

    def test_finds_missing_catch_weight(self):
        cw_findings = [
            f for f in self.result.findings if f.rule_id == "missing_catch_weight"
        ]
        assert len(cw_findings) == 2  # Two LB items without MEA

    def test_fee_per_item(self):
        # SQEP PO-accuracy per-case charge ($1); the $200 admin fee per defect
        # event is not modeled per-unit — see the fee-table comment.
        f = next(f for f in self.result.findings if f.rule_id == "missing_catch_weight")
        assert f.fee == 1.00
        assert f.fee_per == "item"

    def test_severity_will_cause_chargeback(self):
        f = next(f for f in self.result.findings if f.rule_id == "missing_catch_weight")
        assert f.severity == Severity.WILL_CAUSE_CHARGEBACK

    def test_total_catch_weight_fees_sum(self):
        cw_fees = sum(
            f.fee for f in self.result.findings if f.rule_id == "missing_catch_weight"
        )
        assert cw_fees == 2.00  # two flagged items x $1

    def test_non_catch_weight_item_not_flagged(self):
        # The third item (CS = cases) should not trigger catch-weight check
        cw_findings = [
            f for f in self.result.findings if f.rule_id == "missing_catch_weight"
        ]
        for f in cw_findings:
            assert "CS" not in f.message


# --- Missing required segments ---

class TestMissingSegments:
    def setup_method(self):
        self.result = _load_and_validate("856_missing_segment.edi")

    def test_finds_missing_ship_to(self):
        st_findings = [
            f for f in self.result.findings if f.rule_id == "missing_ship_to"
        ]
        assert len(st_findings) == 1

    def test_finds_missing_po_reference(self):
        po_findings = [
            f for f in self.result.findings if f.rule_id == "missing_po_reference"
        ]
        assert len(po_findings) == 1

    def test_missing_ship_to_blocks_transmission(self):
        f = next(f for f in self.result.findings if f.rule_id == "missing_ship_to")
        assert f.severity == Severity.BLOCKS_TRANSMISSION

    def test_missing_po_blocks_transmission(self):
        f = next(f for f in self.result.findings if f.rule_id == "missing_po_reference")
        assert f.severity == Severity.BLOCKS_TRANSMISSION


# --- SSCC-18 validation ---

class TestSSCC18Validation:
    def test_valid_sscc18_passes(self):
        # 00100786420312340001 — need to compute actual valid one
        # Using a known good SSCC-18: 00614141000012345
        # Let's compute: digits 0-16 are 0061414100001234
        # weights: 3,1,3,1,3,1,3,1,3,1,3,1,3,1,3,1,3
        # 0*3+0*1+6*3+1*1+4*3+1*1+4*3+1*1+0*3+0*1+0*3+0*1+1*3+2*1+3*3+4*1+5*3
        # = 0+0+18+1+12+1+12+1+0+0+0+0+3+2+9+4+15 = 78
        # check = (10 - 78%10) % 10 = (10-8)%10 = 2
        assert validate_sscc18("006141410000123452") is None

    def test_wrong_length_rejected(self):
        error = validate_sscc18("1234567890")
        assert error is not None
        assert "10 digits" in error

    def test_non_numeric_rejected(self):
        error = validate_sscc18("00614141ABCD123452")
        assert error is not None
        assert "non-numeric" in error

    def test_bad_check_digit_rejected(self):
        error = validate_sscc18("006141410000123459")  # wrong last digit
        assert error is not None
        assert "check digit" in error

    def test_18_digit_all_zeros_valid_check(self):
        # 000000000000000000 — check digit computation
        # all zeros, sum = 0, check = 0
        assert validate_sscc18("000000000000000000") is None


# --- Inline edge cases ---

class TestShipmentLevelMissingDTM011:
    def test_flags_missing_ship_date(self):
        raw = (
            "ISA*00*          *00*          *ZZ*CINDERHAVEN    *ZZ*WALMART        "
            "*260510*1430*U*00501*000000001*0*P*>~"
            "GS*SH*CINDERHAVEN*WALMART*20260510*143000*1*X*005010~"
            "ST*856*0001~"
            "BSN*00*SHP001*20260510*1430~"
            "HL*1**S~"
            "TD5*B*2*UPSN*M~"
            "DTM*017*20260514~"
            "N1*ST*WALMART DC 6025*92*0006025~"
            "N3*123 MAIN ST~"
            "N4*BENTONVILLE*AR*72712*US~"
            "HL*2*1*O~"
            "PRF*PO123~"
            "HL*3*2*P~"
            "MAN*GM*000000000000000000~"
            "SE*14*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        result = validate_856(parse_envelope(tokenize(raw)))
        result = validate_856_walmart(result)
        dtm_findings = [f for f in result.findings if f.rule_id == "missing_ship_date"]
        assert len(dtm_findings) == 1


class TestMissingCarrier:
    def test_flags_missing_td5(self):
        raw = (
            "ISA*00*          *00*          *ZZ*CINDERHAVEN    *ZZ*WALMART        "
            "*260510*1430*U*00501*000000001*0*P*>~"
            "GS*SH*CINDERHAVEN*WALMART*20260510*143000*1*X*005010~"
            "ST*856*0001~"
            "BSN*00*SHP001*20260510*1430~"
            "HL*1**S~"
            "DTM*011*20260510~"
            "N1*ST*WALMART DC 6025*92*0006025~"
            "N3*123 MAIN ST~"
            "N4*BENTONVILLE*AR*72712*US~"
            "HL*2*1*O~"
            "PRF*PO123~"
            "HL*3*2*P~"
            "MAN*GM*000000000000000000~"
            "SE*13*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        result = validate_856(parse_envelope(tokenize(raw)))
        result = validate_856_walmart(result)
        carrier_findings = [f for f in result.findings if f.rule_id == "missing_carrier"]
        assert len(carrier_findings) == 1
        assert carrier_findings[0].severity == Severity.MAY_CAUSE_CHARGEBACK
