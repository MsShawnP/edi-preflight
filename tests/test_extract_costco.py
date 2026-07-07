from pathlib import Path

from src.envelope import Retailer, parse_envelope
from src.extract_850 import extract_850
from src.x12_tokenizer import tokenize

SAMPLES = Path(__file__).parent.parent / "samples" / "costco"


def _load_and_extract(filename: str):
    raw = (SAMPLES / filename).read_text()
    tokens = tokenize(raw)
    envelope = parse_envelope(tokens)
    return extract_850(envelope)


class TestCostcoBasicPO:
    def setup_method(self):
        self.po = _load_and_extract("850_basic.edi")

    def test_retailer_detected_as_costco(self):
        assert self.po.retailer == Retailer.COSTCO

    def test_retailer_detected_from_phone_id(self):
        # Costco uses phone-style ID "4253138601CH" in ISA06
        assert self.po.retailer == Retailer.COSTCO

    def test_po_number(self):
        assert self.po.po_number == "7012345678"

    def test_ship_to_is_costco_depot(self):
        st = self.po.ship_to
        assert st is not None
        assert "COSTCO" in st.entity_name
        assert "MIRA LOMA" in st.entity_name

    def test_line_item_count(self):
        assert len(self.po.line_items) == 3

    def test_costco_item_number_extracted(self):
        assert self.po.line_items[0].buyers_item_number == "1234567"

    def test_large_order_quantities(self):
        # Costco orders tend to be large
        assert self.po.line_items[0].quantity == 120

    def test_total_amount(self):
        assert self.po.total_amount == 6957.00


class TestCostcoCatchWeight:
    def setup_method(self):
        self.po = _load_and_extract("850_catch_weight.edi")

    def test_retailer_detected_from_name(self):
        # This sample uses "COSTCO" in ISA06 instead of phone ID
        assert self.po.retailer == Retailer.COSTCO

    def test_catch_weight_items_detected(self):
        cw_items = [li for li in self.po.line_items if li.is_catch_weight]
        assert len(cw_items) == 2

    def test_weight_extracted(self):
        first_cw = next(li for li in self.po.line_items if li.is_catch_weight)
        assert first_cw.weight == 500
        assert first_cw.weight_unit == "LB"

    def test_mixed_catch_weight_and_regular(self):
        regular = [li for li in self.po.line_items if not li.is_catch_weight]
        assert len(regular) == 1
        assert regular[0].unit_of_measure == "CS"

    def test_ship_not_before_date(self):
        qualifiers = {d.qualifier for d in self.po.dates}
        assert "037" in qualifiers
