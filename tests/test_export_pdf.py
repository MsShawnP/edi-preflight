from pathlib import Path

from src.envelope import parse_envelope
from src.export_pdf import export_pdf
from src.extract_850 import extract_850
from src.x12_tokenizer import tokenize

SAMPLES = Path(__file__).parent.parent / "samples" / "walmart"


def _load_and_extract(filename: str):
    raw = (SAMPLES / filename).read_text()
    tokens = tokenize(raw)
    envelope = parse_envelope(tokens)
    return extract_850(envelope)


class TestPDFExportBasicPO:
    def setup_method(self):
        self.po = _load_and_extract("850_basic.edi")
        self.pdf_bytes = export_pdf(self.po)

    def test_returns_bytes(self):
        assert isinstance(self.pdf_bytes, bytes)

    def test_starts_with_pdf_header(self):
        assert self.pdf_bytes[:5] == b"%PDF-"

    def test_ends_with_eof_marker(self):
        assert self.pdf_bytes.rstrip().endswith(b"%%EOF")

    def test_has_substantial_content(self):
        assert len(self.pdf_bytes) > 1000


class TestPDFExportWithAllowances:
    def setup_method(self):
        self.po = _load_and_extract("850_with_allowances.edi")
        self.pdf_bytes = export_pdf(self.po)

    def test_produces_valid_pdf(self):
        assert self.pdf_bytes[:5] == b"%PDF-"

    def test_larger_than_basic_po(self):
        basic_pdf = export_pdf(_load_and_extract("850_basic.edi"))
        assert len(self.pdf_bytes) > len(basic_pdf)


class TestPDFExportCatchWeight:
    def setup_method(self):
        self.po = _load_and_extract("850_catch_weight.edi")
        self.pdf_bytes = export_pdf(self.po)

    def test_produces_valid_pdf(self):
        assert self.pdf_bytes[:5] == b"%PDF-"

    def test_has_substantial_content(self):
        assert len(self.pdf_bytes) > 1000
