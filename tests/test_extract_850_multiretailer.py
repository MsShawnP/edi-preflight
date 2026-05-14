from pathlib import Path

import pytest

from src.envelope import Retailer, parse_envelope
from src.extract_850 import extract_850
from src.x12_tokenizer import tokenize

SAMPLES = Path(__file__).parent.parent / "samples"


def _load_and_extract(retailer: str, filename: str):
    raw = (SAMPLES / retailer / filename).read_text()
    tokens = tokenize(raw)
    envelope = parse_envelope(tokens)
    return extract_850(envelope)


# --- Amazon ---


class TestAmazonBasicPO:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.po = _load_and_extract("amazon", "850_basic.edi")

    def test_retailer_detected(self):
        assert self.po.retailer == Retailer.AMAZON

    def test_po_number(self):
        assert self.po.po_number == "G7984251"

    def test_po_type_new_order(self):
        assert self.po.po_type == "NE"

    def test_dates_use_amazon_qualifiers(self):
        labels = {d.qualifier: d.label for d in self.po.dates}
        assert labels["063"] == "Do Not Deliver After"
        assert labels["064"] == "Do Not Deliver Before"

    def test_ship_to_code_only(self):
        st = self.po.ship_to
        assert st is not None
        assert st.id_code == "RNO1"
        assert st.street == ""

    def test_line_item_count(self):
        assert len(self.po.line_items) == 3

    def test_no_descriptions(self):
        for item in self.po.line_items:
            assert item.description == ""

    def test_total_line_items(self):
        assert self.po.total_line_items == 3
        assert self.po.total_quantity == 400

    def test_no_amount(self):
        assert self.po.total_amount == 0.0


class TestAmazonConsignedPO:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.po = _load_and_extract("amazon", "850_consigned.edi")

    def test_po_type_consigned(self):
        assert self.po.po_type == "CN"

    def test_ship_to_san_code(self):
        st = self.po.ship_to
        assert st is not None
        assert st.id_code == "1553992"

    def test_buyers_item_number_from_bp(self):
        item2 = self.po.line_items[1]
        assert item2.buyers_item_number == "AMZ-9920145"

    def test_upc_from_up(self):
        item1 = self.po.line_items[0]
        assert item1.upc == "012345678901"


# --- UNFI ---


class TestUNFIBasicPO:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.po = _load_and_extract("unfi", "850_basic.edi")

    def test_retailer_detected(self):
        assert self.po.retailer == Retailer.UNFI

    def test_po_number(self):
        assert self.po.po_number == "8831042"

    def test_po_type_new_order(self):
        assert self.po.po_type == "NE"

    def test_vendor_number_from_ref_ia(self):
        assert self.po.vendor_number == "V220198"

    def test_pickup_date(self):
        labels = {d.qualifier: d.label for d in self.po.dates}
        assert labels["118"] == "Requested Pickup"

    def test_terms(self):
        assert self.po.terms == "NET 30"

    def test_ship_to(self):
        st = self.po.ship_to
        assert st is not None
        assert "UNFI" in st.entity_name
        assert st.city == "CHAMPAIGN"

    def test_gtin14_from_uk(self):
        item1 = self.po.line_items[0]
        assert item1.gtin_14 == "10012345678901"

    def test_buyers_item_from_pi(self):
        item3 = self.po.line_items[2]
        assert item3.buyers_item_number == "UNF-440291"

    def test_total_amount_from_tt(self):
        assert self.po.total_amount == 2227.80

    def test_line_items(self):
        assert len(self.po.line_items) == 3


class TestUNFIDropshipPO:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.po = _load_and_extract("unfi", "850_dropship.edi")

    def test_po_type_dropship(self):
        assert self.po.po_type == "DS"

    def test_ship_from_address(self):
        sf = None
        for addr in self.po.addresses:
            if addr.entity_code == "SF":
                sf = addr
        assert sf is not None
        assert "CINDERHAVEN" in sf.entity_name

    def test_ship_to_is_retailer(self):
        st = self.po.ship_to
        assert st is not None
        assert "NATURAL GROCERS" in st.entity_name


# --- KeHE ---


class TestKeHEBasicPO:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.po = _load_and_extract("kehe", "850_basic.edi")

    def test_retailer_detected(self):
        assert self.po.retailer == Retailer.KEHE

    def test_po_number(self):
        assert self.po.po_number == "3667599"

    def test_po_type_standalone(self):
        assert self.po.po_type == "SA"

    def test_vendor_number_from_ref_ia(self):
        assert self.po.vendor_number == "44001758"

    def test_pickup_date_not_present(self):
        qualifiers = [d.qualifier for d in self.po.dates]
        assert "002" in qualifiers

    def test_terms(self):
        assert self.po.terms == "NET 30"

    def test_header_allowances(self):
        assert len(self.po.header_allowances) == 2
        codes = [a.code for a in self.po.header_allowances]
        assert "B720" in codes
        assert "G860" in codes

    def test_marketing_allowance(self):
        alw = [a for a in self.po.header_allowances if a.code == "B720"][0]
        assert alw.description == "MARKETING ALLOWANCE"
        assert alw.percent == 0.7

    def test_line_item_allowance(self):
        item1 = self.po.line_items[0]
        assert len(item1.allowances) == 1
        assert item1.allowances[0].code == "C310"

    def test_total_weight_from_ctt(self):
        assert self.po.total_weight == 1842.50
        assert self.po.total_weight_unit == "LB"

    def test_total_amount_from_tt(self):
        assert self.po.total_amount == 773.70

    def test_upc_is_primary_id(self):
        item1 = self.po.line_items[0]
        assert item1.upc == "012345678901"

    def test_gtin14_present(self):
        item1 = self.po.line_items[0]
        assert item1.gtin_14 == "00012345678901"

    def test_kehe_item_number_via_in(self):
        item2 = self.po.line_items[1]
        assert item2.buyers_item_number == "44019922"


class TestKeHEDropshipPO:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.po = _load_and_extract("kehe", "850_dropship.edi")

    def test_po_type_dropship(self):
        assert self.po.po_type == "DS"

    def test_retailer_from_alternate_duns(self):
        assert self.po.retailer == Retailer.KEHE

    def test_buying_party_address(self):
        by = None
        for addr in self.po.addresses:
            if addr.entity_code == "BY":
                by = addr
        assert by is not None
        assert "KEHE" in by.entity_name

    def test_ship_to_is_retailer_store(self):
        st = self.po.ship_to
        assert st is not None
        assert "WHOLE FOODS" in st.entity_name

    def test_total_weight(self):
        assert self.po.total_weight == 568.40


# --- Costco ---


class TestCostcoBasicPO:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.po = _load_and_extract("costco", "850_basic.edi")

    def test_retailer_detected(self):
        assert self.po.retailer == Retailer.COSTCO

    def test_po_number(self):
        assert self.po.po_number == "1120510001"

    def test_po_type_standalone(self):
        assert self.po.po_type == "SA"

    def test_vendor_number_from_ref_vr(self):
        assert self.po.vendor_number == "V891204"

    def test_cancel_date(self):
        labels = {d.qualifier: d.label for d in self.po.dates}
        assert labels["175"] == "Cancel If Not Shipped By"

    def test_ship_date(self):
        labels = {d.qualifier: d.date for d in self.po.dates}
        assert labels["010"] == "20260519"

    def test_ship_to_warehouse(self):
        st = self.po.ship_to
        assert st is not None
        assert "ISSAQUAH" in st.entity_name
        assert st.id_code == "1033918430001"

    def test_line_items(self):
        assert len(self.po.line_items) == 3

    def test_costco_item_number_via_in(self):
        item1 = self.po.line_items[0]
        assert item1.buyers_item_number == "1234567"

    def test_upc_from_up(self):
        item1 = self.po.line_items[0]
        assert item1.upc == "012345678901"

    def test_upc_from_ua(self):
        item2 = self.po.line_items[1]
        assert item2.upc == "012345678902"

    def test_line_level_allowance_zzzz(self):
        item1 = self.po.line_items[0]
        assert len(item1.allowances) == 1
        assert item1.allowances[0].code == "ZZZZ"
        assert item1.allowances[0].description == "NEW ITEM ALLOWANCE"

    def test_no_total_amount(self):
        assert self.po.total_amount == 0.0


class TestCostcoConsignmentPO:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.po = _load_and_extract("costco", "850_consignment.edi")

    def test_po_type_consignment(self):
        assert self.po.po_type == "ZZ"

    def test_cancel_date(self):
        dates = {d.qualifier: d.date for d in self.po.dates}
        assert dates["175"] == "20260526"

    def test_header_charge(self):
        assert len(self.po.header_allowances) == 1
        charge = self.po.header_allowances[0]
        assert charge.is_charge
        assert charge.description == "PALLET HANDLING CHARGE"

    def test_ship_to_san_diego(self):
        st = self.po.ship_to
        assert st is not None
        assert "SAN DIEGO" in st.entity_name
