from pathlib import Path

from src.envelope import parse_envelope
from src.export_pdf import export_850_pdf
from src.extract_850 import PurchaseOrder, extract_850
from src.x12_tokenizer import tokenize

SAMPLES = Path(__file__).parent.parent / "samples" / "walmart"


def _load_and_extract(filename: str):
    raw = (SAMPLES / filename).read_text()
    tokens = tokenize(raw)
    envelope = parse_envelope(tokens)
    return extract_850(envelope)


class TestPdfExportBasicPO:
    def setup_method(self):
        self.po = _load_and_extract("850_basic.edi")
        self.pdf_bytes = export_850_pdf(self.po)

    def test_returns_bytes(self):
        assert isinstance(self.pdf_bytes, bytes)

    def test_starts_with_pdf_header(self):
        assert self.pdf_bytes[:5] == b"%PDF-"

    def test_non_empty_output(self):
        assert len(self.pdf_bytes) > 500

    def test_contains_po_number(self):
        assert b"4500012345" in self.pdf_bytes


class TestPdfExportCatchWeight:
    def setup_method(self):
        self.po = _load_and_extract("850_catch_weight.edi")
        self.pdf_bytes = export_850_pdf(self.po)

    def test_valid_pdf(self):
        assert self.pdf_bytes[:5] == b"%PDF-"

    def test_contains_catch_weight_marker(self):
        assert b"CW" in self.pdf_bytes


class TestPdfExportAllowances:
    def setup_method(self):
        self.po = _load_and_extract("850_with_allowances.edi")
        self.pdf_bytes = export_850_pdf(self.po)

    def test_valid_pdf(self):
        assert self.pdf_bytes[:5] == b"%PDF-"

    def test_larger_than_basic_po(self):
        basic_po = _load_and_extract("850_basic.edi")
        basic_pdf = export_850_pdf(basic_po)
        assert len(self.pdf_bytes) > len(basic_pdf)


class TestPdfExportEmptyPO:
    def test_pdf_with_no_line_items(self):
        po = PurchaseOrder(po_number="EMPTY", po_type="NE", po_date="20260101")
        pdf_bytes = export_850_pdf(po)
        assert pdf_bytes[:5] == b"%PDF-"
        assert b"EMPTY" in pdf_bytes
