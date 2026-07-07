"""Tests for 856 validation report PDF export."""

from pathlib import Path

from src.envelope import parse_envelope
from src.export_validation_pdf import export_validation_pdf
from src.validate_856 import validate_856
from src.validate_856_walmart import validate_856_walmart
from src.x12_tokenizer import tokenize

SAMPLES = Path(__file__).parent.parent / "samples" / "walmart"


def _load_validate_export(filename: str, retailer_label: str = "Walmart"):
    raw = (SAMPLES / filename).read_text()
    tokens = tokenize(raw)
    envelope = parse_envelope(tokens)
    result = validate_856(envelope)
    result = validate_856_walmart(result)
    return export_validation_pdf(result, retailer_label)


class TestValidationPdfClean:
    def setup_method(self):
        self.pdf = _load_validate_export("856_clean.edi")

    def test_returns_bytes(self):
        assert isinstance(self.pdf, bytes)

    def test_starts_with_pdf_header(self):
        assert self.pdf[:5] == b"%PDF-"

    def test_non_empty(self):
        assert len(self.pdf) > 1000

    def test_contains_shipment_id(self):
        # ReportLab embeds the title in PDF metadata
        assert b"SHP20260510001" in self.pdf


class TestValidationPdfWithFindings:
    def setup_method(self):
        self.clean_pdf = _load_validate_export("856_clean.edi")
        self.findings_pdf = _load_validate_export("856_missing_mea.edi")

    def test_findings_pdf_larger_than_clean(self):
        # PDF with findings should be larger than clean (has findings table + chargeback table)
        assert len(self.findings_pdf) > len(self.clean_pdf)

    def test_valid_pdf(self):
        assert self.findings_pdf[:5] == b"%PDF-"


class TestValidationPdfBadDtm:
    def setup_method(self):
        self.pdf = _load_validate_export("856_bad_dtm.edi")

    def test_valid_pdf(self):
        assert self.pdf[:5] == b"%PDF-"

    def test_non_empty(self):
        assert len(self.pdf) > 1000


class TestValidationPdfWrongHLOrder:
    def setup_method(self):
        self.pdf = _load_validate_export("856_wrong_hl_order.edi")

    def test_valid_pdf(self):
        assert self.pdf[:5] == b"%PDF-"


class TestValidationPdfMissingSegment:
    def setup_method(self):
        self.pdf = _load_validate_export("856_missing_segment.edi")

    def test_valid_pdf(self):
        assert self.pdf[:5] == b"%PDF-"

    def test_larger_than_clean(self):
        clean = _load_validate_export("856_clean.edi")
        assert len(self.pdf) > len(clean)
