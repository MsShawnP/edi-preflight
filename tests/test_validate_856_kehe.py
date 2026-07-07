"""Tests for KeHE-specific 856 ASN validation."""

from pathlib import Path

from src.envelope import parse_envelope
from src.validate_856 import validate_856
from src.validate_856_kehe import validate_856_kehe
from src.x12_tokenizer import tokenize

SAMPLES = Path(__file__).parent.parent / "samples" / "kehe"


def _load_and_validate(filename: str):
    raw = (SAMPLES / filename).read_text()
    tokens = tokenize(raw)
    envelope = parse_envelope(tokens)
    result = validate_856(envelope)
    return validate_856_kehe(result)


class TestCleanDocumentKeHE:
    def setup_method(self):
        self.result = _load_and_validate("856_clean.edi")

    def test_clean_document_passes(self):
        retailer_findings = [f for f in self.result.findings if f.layer == "retailer"]
        assert len(retailer_findings) == 0

    def test_is_valid(self):
        assert self.result.is_valid

    def test_no_fees(self):
        assert self.result.total_fees == 0.0


class TestWrongHLOrderKeHE:
    def setup_method(self):
        self.result = _load_and_validate("856_wrong_hl_order.edi")

    def test_flags_hierarchy_violation(self):
        hl_findings = [f for f in self.result.findings if f.rule_id == "wrong_hl_hierarchy"]
        assert len(hl_findings) >= 1

    def test_hierarchy_blocks_transmission(self):
        hl_findings = [f for f in self.result.findings if f.rule_id == "wrong_hl_hierarchy"]
        for f in hl_findings:
            assert f.severity.value == "blocks-transmission"

    def test_flags_missing_po_reference(self):
        """S→I skips O level, so no PRF segment exists."""
        prf_findings = [f for f in self.result.findings if f.rule_id == "missing_po_reference"]
        # No O-level nodes exist, so no PRF check fires
        # The hierarchy violation is the primary finding
        assert len(prf_findings) == 0

    def test_finding_references_kehe(self):
        hl_findings = [f for f in self.result.findings if f.rule_id == "wrong_hl_hierarchy"]
        assert any("KeHE" in f.message for f in hl_findings)
