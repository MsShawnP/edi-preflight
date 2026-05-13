from pathlib import Path

from src.envelope import Retailer, parse_envelope
from src.extract_850 import extract_850
from src.x12_tokenizer import tokenize

SAMPLES = Path(__file__).parent.parent / "samples" / "amazon"


def _load_and_extract(filename: str):
    raw = (SAMPLES / filename).read_text()
    tokens = tokenize(raw)
    envelope = parse_envelope(tokens)
    return extract_850(envelope)


class TestAmazonBasicPO:
    def setup_method(self):
        self.po = _load_and_extract("850_basic.edi")

    def test_retailer_detected_as_amazon(self):
        assert self.po.retailer == Retailer.AMAZON

    def test_po_number(self):
        assert self.po.po_number == "2ABCD12345"

    def test_po_type_is_new_order(self):
        assert self.po.po_type == "NE"

    def test_ship_to_is_amazon_fc(self):
        st = self.po.ship_to
        assert st is not None
        assert "AMAZON" in st.entity_name
        assert "BFI4" in st.entity_name

    def test_line_item_count(self):
        assert len(self.po.line_items) == 3

    def test_unit_of_measure_is_each(self):
        assert self.po.line_items[0].unit_of_measure == "EA"

    def test_buyers_item_number_is_amazon_id(self):
        assert self.po.line_items[0].buyers_item_number == "B00ABC1234"

    def test_upc_extracted(self):
        assert self.po.line_items[0].upc == "012345678901"

    def test_delivery_window_dates(self):
        qualifiers = {d.qualifier for d in self.po.dates}
        assert "037" in qualifiers  # ship not before
        assert "063" in qualifiers  # do not deliver after

    def test_total_amount(self):
        assert self.po.total_amount == 2147.40


class TestAmazonWithAllowances:
    def setup_method(self):
        self.po = _load_and_extract("850_with_allowances.edi")

    def test_retailer_detected_from_amzn_abbreviation(self):
        assert self.po.retailer == Retailer.AMAZON

    def test_header_allowances(self):
        assert len(self.po.header_allowances) == 2

    def test_line_level_allowances(self):
        total_line_alw = sum(len(li.allowances) for li in self.po.line_items)
        assert total_line_alw == 3

    def test_terms_extracted(self):
        assert self.po.terms == "Net 30"

    def test_ship_to_is_different_fc(self):
        st = self.po.ship_to
        assert st is not None
        assert "PHX6" in st.entity_name
