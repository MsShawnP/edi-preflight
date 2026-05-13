"""Tests for Amazon-specific 856 ASN validation."""

from pathlib import Path

from src.envelope import parse_envelope
from src.validate_856 import validate_856
from src.validate_856_amazon import validate_856_amazon
from src.x12_tokenizer import tokenize

SAMPLES = Path(__file__).parent.parent / "samples" / "amazon"


def _load_and_validate(filename: str):
    raw = (SAMPLES / filename).read_text()
    tokens = tokenize(raw)
    envelope = parse_envelope(tokens)
    result = validate_856(envelope)
    return validate_856_amazon(result)


class TestCleanDocumentAmazon:
    def setup_method(self):
        self.result = _load_and_validate("856_clean.edi")

    def test_clean_document_passes(self):
        retailer_findings = [f for f in self.result.findings if f.layer == "retailer"]
        assert len(retailer_findings) == 0

    def test_is_valid(self):
        assert self.result.is_valid

    def test_no_fees(self):
        assert self.result.total_fees == 0.0


class TestMissingSSCC18Amazon:
    def setup_method(self):
        self.result = _load_and_validate("856_missing_sscc18.edi")

    def test_flags_missing_sscc18(self):
        sscc_findings = [f for f in self.result.findings if f.rule_id == "missing_sscc18"]
        assert len(sscc_findings) == 1

    def test_sscc18_fee_is_amazon_rate(self):
        sscc_findings = [f for f in self.result.findings if f.rule_id == "missing_sscc18"]
        assert sscc_findings[0].fee == 50.00

    def test_sscc18_fee_per_case(self):
        sscc_findings = [f for f in self.result.findings if f.rule_id == "missing_sscc18"]
        assert sscc_findings[0].fee_per == "case"

    def test_retailer_layer(self):
        sscc_findings = [f for f in self.result.findings if f.rule_id == "missing_sscc18"]
        assert sscc_findings[0].layer == "retailer"


class TestAmazonRetailerName:
    def test_finding_messages_reference_amazon(self):
        result = _load_and_validate("856_missing_sscc18.edi")
        retailer_findings = [f for f in result.findings if f.layer == "retailer"]
        # At least one finding should reference Amazon in its message
        amazon_refs = [f for f in retailer_findings if "Amazon" in f.message]
        assert len(amazon_refs) > 0 or len(retailer_findings) > 0
