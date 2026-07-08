"""Tests for UNFI-specific 856 ASN validation."""

from pathlib import Path

from src.envelope import parse_envelope
from src.validate_856 import validate_856
from src.validate_856_unfi import validate_856_unfi
from src.x12_tokenizer import tokenize

SAMPLES = Path(__file__).parent.parent / "samples" / "unfi"


def _load_and_validate(filename: str):
    raw = (SAMPLES / filename).read_text()
    tokens = tokenize(raw)
    envelope = parse_envelope(tokens)
    result = validate_856(envelope)
    return validate_856_unfi(result)


class TestCleanDocumentUNFI:
    def setup_method(self):
        self.result = _load_and_validate("856_clean.edi")

    def test_clean_document_passes(self):
        retailer_findings = [f for f in self.result.findings if f.layer == "retailer"]
        assert len(retailer_findings) == 0

    def test_is_valid(self):
        assert self.result.is_valid

    def test_no_fees(self):
        assert self.result.total_fees == 0.0


class TestBsnPurposeUNFI:
    """UNFI accepts only BSN01=00 (Original); the generic field check does
    not, so a UNFI cancellation ASN (BSN01=01) must be caught at the
    retailer layer instead of false-passing."""

    def _validate_inline(self, purpose_code: str):
        raw = (
            "ISA*00*          *00*          *ZZ*CINDERHAVEN    *ZZ*UNFI           "
            "*260510*1530*U*00501*000000001*0*P*>~"
            "GS*SH*CINDERHAVEN*UNFI*20260510*153000*1*X*005010~"
            "ST*856*0001~"
            f"BSN*{purpose_code}*SHP001*20260510*1530~"
            "HL*1**S~"
            "TD5*B*2*ODFL*M~"
            "DTM*011*20260510~"
            "N1*ST*UNFI DC RIDGEFIELD*92*UNFI-RGF~"
            "N3*4750 S PIONEER BLVD~"
            "N4*RIDGEFIELD*WA*98642*US~"
            "HL*2*1*O~"
            "PRF*8001234567~"
            "HL*3*2*P~"
            "MAN*GM*000543703300010013~"
            "SE*13*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        result = validate_856(parse_envelope(tokenize(raw)))
        return validate_856_unfi(result)

    def test_cancellation_purpose_rejected(self):
        result = self._validate_inline("01")
        findings = [
            f for f in result.findings
            if f.rule_id == "retailer_bsn_purpose_not_accepted"
        ]
        assert len(findings) == 1
        assert "01" in findings[0].message

    def test_original_purpose_accepted(self):
        result = self._validate_inline("00")
        findings = [
            f for f in result.findings
            if f.rule_id == "retailer_bsn_purpose_not_accepted"
        ]
        assert findings == []


class TestMissingCatchWeightUNFI:
    def setup_method(self):
        self.result = _load_and_validate("856_missing_catch_weight.edi")

    def test_flags_catch_weight_violations(self):
        cw_findings = [f for f in self.result.findings if f.rule_id == "missing_catch_weight"]
        assert len(cw_findings) == 2  # Two items with LB and KG UOM

    def test_catch_weight_fee_is_unfi_rate(self):
        cw_findings = [f for f in self.result.findings if f.rule_id == "missing_catch_weight"]
        for f in cw_findings:
            assert f.fee == 50.00

    def test_total_catch_weight_fees(self):
        cw_findings = [f for f in self.result.findings if f.rule_id == "missing_catch_weight"]
        total = sum(f.fee for f in cw_findings)
        assert total == 100.00

    def test_not_valid_with_catch_weight_violations(self):
        assert not self.result.is_valid
