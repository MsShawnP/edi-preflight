"""Tests for Costco-specific 856 ASN validation."""

from pathlib import Path

from src.envelope import parse_envelope
from src.validate_856 import validate_856
from src.validate_856_costco import validate_856_costco
from src.x12_tokenizer import tokenize

SAMPLES = Path(__file__).parent.parent / "samples" / "costco"


def _load_and_validate(filename: str):
    raw = (SAMPLES / filename).read_text()
    tokens = tokenize(raw)
    envelope = parse_envelope(tokens)
    result = validate_856(envelope)
    return validate_856_costco(result)


class TestCleanDocumentCostco:
    def setup_method(self):
        self.result = _load_and_validate("856_clean.edi")

    def test_clean_document_passes(self):
        retailer_findings = [f for f in self.result.findings if f.layer == "retailer"]
        assert len(retailer_findings) == 0

    def test_is_valid(self):
        assert self.result.is_valid

    def test_no_fees(self):
        assert self.result.total_fees == 0.0


class TestMissingSegmentsCostco:
    def setup_method(self):
        self.result = _load_and_validate("856_missing_segments.edi")

    def test_flags_missing_ship_to(self):
        findings = [f for f in self.result.findings if f.rule_id == "missing_ship_to"]
        assert len(findings) == 1

    def test_flags_missing_po_reference(self):
        findings = [f for f in self.result.findings if f.rule_id == "missing_po_reference"]
        assert len(findings) == 1

    def test_flags_missing_catch_weight(self):
        """Item with UOM=LB but no MEA*WT."""
        findings = [f for f in self.result.findings if f.rule_id == "missing_catch_weight"]
        assert len(findings) == 1

    def test_catch_weight_fee_is_costco_rate(self):
        findings = [f for f in self.result.findings if f.rule_id == "missing_catch_weight"]
        assert findings[0].fee == 150.00

    def test_total_fees(self):
        # missing_ship_to ($0) + missing_po_reference ($0) + missing_catch_weight ($150)
        assert self.result.total_fees == 150.00

    def test_findings_are_retailer_layer(self):
        retailer_findings = [f for f in self.result.findings if f.layer == "retailer"]
        assert len(retailer_findings) >= 3  # ship_to, po_reference, catch_weight
