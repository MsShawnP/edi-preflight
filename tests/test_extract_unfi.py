from pathlib import Path

from src.envelope import Retailer, parse_envelope
from src.extract_850 import extract_850
from src.x12_tokenizer import tokenize

SAMPLES = Path(__file__).parent.parent / "samples" / "unfi"


def _load_and_extract(filename: str):
    raw = (SAMPLES / filename).read_text()
    tokens = tokenize(raw)
    envelope = parse_envelope(tokens)
    return extract_850(envelope)


class TestUnfiBasicPO:
    def setup_method(self):
        self.po = _load_and_extract("850_basic.edi")

    def test_retailer_detected_as_unfi(self):
        assert self.po.retailer == Retailer.UNFI

    def test_po_number(self):
        assert self.po.po_number == "80012345"

    def test_po_type(self):
        assert self.po.po_type == "NE"

    def test_ship_to_is_unfi_dc(self):
        st = self.po.ship_to
        assert st is not None
        assert "UNFI" in st.entity_name
        assert "PROVIDENCE" in st.entity_name

    def test_line_item_count(self):
        assert len(self.po.line_items) == 2

    def test_unfi_item_number_extracted(self):
        assert self.po.line_items[0].buyers_item_number == "501234"

    def test_upc_extracted(self):
        assert self.po.line_items[0].upc == "012345678901"

    def test_total_amount(self):
        assert self.po.total_amount == 1619.40


class TestUnfiWithAllowances:
    def setup_method(self):
        self.po = _load_and_extract("850_with_allowances.edi")

    def test_header_allowance(self):
        assert len(self.po.header_allowances) == 1

    def test_line_level_allowances(self):
        total = sum(len(li.allowances) for li in self.po.line_items)
        assert total == 2

    def test_ship_to_is_different_dc(self):
        st = self.po.ship_to
        assert st is not None
        assert "LANCASTER" in st.entity_name

    def test_terms_extracted(self):
        assert self.po.terms == "Net 30"

    def test_three_line_items(self):
        assert len(self.po.line_items) == 3
