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
