from pathlib import Path

import pytest

from src.envelope import Retailer, parse_envelope
from src.extract_850 import ExtractionError, extract_850
from src.x12_tokenizer import tokenize

SAMPLES = Path(__file__).parent.parent / "samples" / "walmart"


def _load_and_extract(filename: str):
    raw = (SAMPLES / filename).read_text()
    tokens = tokenize(raw)
    envelope = parse_envelope(tokens)
    return extract_850(envelope)


class TestBasicPO:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.po = _load_and_extract("850_basic.edi")

    def test_po_number(self):
        assert self.po.po_number == "4500012345"

    def test_po_type(self):
        assert self.po.po_type == "DS"

    def test_po_date(self):
        assert self.po.po_date == "20260510"

    def test_department(self):
        assert self.po.department == "92"

    def test_retailer_detected(self):
        assert self.po.retailer == Retailer.WALMART

    def test_dates(self):
        labels = {d.qualifier: d.date for d in self.po.dates}
        assert labels["010"] == "20260517"
        assert labels["002"] == "20260524"

    def test_ship_to(self):
        st = self.po.ship_to
        assert st is not None
        assert st.entity_name == "WALMART DC 6025"
        assert st.id_code == "0006025"
        assert st.city == "BENTONVILLE"
        assert st.state == "AR"

    def test_bill_to(self):
        bt = self.po.bill_to
        assert bt is not None
        assert bt.entity_name == "WALMART ACCOUNTS PAYABLE"

    def test_line_item_count(self):
        assert len(self.po.line_items) == 3

    def test_first_line_item(self):
        item = self.po.line_items[0]
        assert item.line_number == "1"
        assert item.quantity == 48.0
        assert item.unit_of_measure == "CS"
        assert item.unit_price == 24.99
        assert item.buyers_item_number == "0078742031234"
        assert item.upc == "012345678901"
        assert item.vendor_item_number == "CRK-SEA-12"
        assert item.description == "Artisanal Sea Salt Crackers 12ct"

    def test_all_product_ids(self):
        item = self.po.line_items[0]
        assert item.all_product_ids["IN"] == "0078742031234"
        assert item.all_product_ids["UP"] == "012345678901"
        assert item.all_product_ids["VN"] == "CRK-SEA-12"

    def test_third_line_item(self):
        item = self.po.line_items[2]
        assert item.quantity == 36.0
        assert item.unit_price == 26.99
        assert item.vendor_item_number == "CRK-PPR-12"

    def test_totals(self):
        assert self.po.total_line_items == 3
        assert self.po.total_quantity == 156.0
        assert self.po.total_amount == 3815.64

    def test_no_allowances(self):
        assert len(self.po.header_allowances) == 0
        assert len(self.po.all_allowances) == 0

    def test_no_catch_weight(self):
        for item in self.po.line_items:
            assert item.is_catch_weight is False


class TestAllowancesPO:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.po = _load_and_extract("850_with_allowances.edi")

    def test_po_number(self):
        assert self.po.po_number == "4500012400"

    def test_po_type_standalone(self):
        assert self.po.po_type == "SA"

    def test_header_allowances(self):
        assert len(self.po.header_allowances) == 2

    def test_header_promo_allowance(self):
        promo = self.po.header_allowances[0]
        assert promo.is_allowance
        assert promo.code == "F800"
        assert promo.percent == 2.5
        assert promo.handling_code == "06"
        assert promo.level == "header"

    def test_header_freight_charge(self):
        freight = self.po.header_allowances[1]
        assert freight.is_charge
        assert freight.code == "D240"
        assert freight.amount == 125.0

    def test_line_item_allowances(self):
        item1 = self.po.line_items[0]
        assert len(item1.allowances) == 1
        assert item1.allowances[0].code == "F810"
        assert item1.allowances[0].amount == 149.94
        assert item1.allowances[0].level == "line_item"

    def test_third_item_has_two_allowances(self):
        item3 = self.po.line_items[2]
        assert len(item3.allowances) == 2
        codes = [a.code for a in item3.allowances]
        assert "F810" in codes
        assert "A260" in codes

    def test_coop_ad_allowance(self):
        item3 = self.po.line_items[2]
        coop = [a for a in item3.allowances if a.code == "A260"][0]
        assert coop.amount == 50.0

    def test_all_allowances_total(self):
        all_a = self.po.all_allowances
        assert len(all_a) == 6

    def test_dates_include_do_not_deliver_after(self):
        qualifiers = {d.qualifier for d in self.po.dates}
        assert "063" in qualifiers

    def test_pack_details(self):
        item = self.po.line_items[0]
        assert item.pack_quantity == "12"
        assert item.pack_size == "6"
        assert item.pack_uom == "OZ"

    def test_terms(self):
        assert "Net 30" in self.po.terms


class TestCatchWeightPO:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.po = _load_and_extract("850_catch_weight.edi")

    def test_department_is_meat(self):
        assert self.po.department == "93"

    def test_catch_weight_item_detected(self):
        cheese = self.po.line_items[0]
        assert cheese.is_catch_weight is True

    def test_catch_weight_from_uom(self):
        cheese = self.po.line_items[0]
        assert cheese.unit_of_measure == "LB"
        assert cheese.quantity == 200.0

    def test_mea_weight_extracted(self):
        cheese = self.po.line_items[0]
        assert cheese.weight == 200.0
        assert cheese.weight_unit == "LB"

    def test_second_catch_weight_item(self):
        gouda = self.po.line_items[1]
        assert gouda.is_catch_weight is True
        assert gouda.weight == 150.0
        assert gouda.unit_price == 12.99

    def test_non_catch_weight_item_in_same_po(self):
        crackers = self.po.line_items[2]
        assert crackers.is_catch_weight is False
        assert crackers.unit_of_measure == "CS"
        assert crackers.pack_quantity == "12"

    def test_ship_not_before_date(self):
        qualifiers = {d.qualifier: d.date for d in self.po.dates}
        assert qualifiers["037"] == "20260514"

    def test_three_items_total(self):
        assert len(self.po.line_items) == 3
        assert self.po.total_line_items == 3


class TestExtractionErrors:
    def test_non_850_raises(self):
        edi = (
            "ISA*00*          *00*          *ZZ*WALMART        *ZZ*SUPPLIER       "
            "*260512*0900*U*00501*000000001*0*P*>~"
            "GS*SH*WALMART*SUPPLIER*20260512*0900*1*X*005010~"
            "ST*856*0001~"
            "BSN*00*SHIP001*20260512*0900~"
            "SE*3*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        tokens = tokenize(edi)
        envelope = parse_envelope(tokens)
        with pytest.raises(ExtractionError, match="Expected an 850"):
            extract_850(envelope)
