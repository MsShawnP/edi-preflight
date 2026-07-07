from pathlib import Path

from src.envelope import Retailer, parse_envelope
from src.extract_850 import extract_850
from src.x12_tokenizer import tokenize

SAMPLES = Path(__file__).parent.parent / "samples" / "kehe"


def _load_and_extract(filename: str):
    raw = (SAMPLES / filename).read_text()
    tokens = tokenize(raw)
    envelope = parse_envelope(tokens)
    return extract_850(envelope)


class TestKeheBasicPO:
    def setup_method(self):
        self.po = _load_and_extract("850_basic.edi")

    def test_retailer_detected_as_kehe(self):
        assert self.po.retailer == Retailer.KEHE

    def test_retailer_detected_from_duns_id(self):
        # KeHE uses DUNS ID 0569813430000 in ISA06
        assert self.po.retailer == Retailer.KEHE

    def test_po_number(self):
        assert self.po.po_number == "KH9012345"

    def test_ship_to_is_kehe_dc(self):
        st = self.po.ship_to
        assert st is not None
        assert "KEHE" in st.entity_name

    def test_line_item_count(self):
        assert len(self.po.line_items) == 3

    def test_kehe_item_number_extracted(self):
        assert self.po.line_items[0].buyers_item_number == "601234"

    def test_total_amount(self):
        assert self.po.total_amount == 2964.48


class TestKeheWithAllowances:
    def setup_method(self):
        self.po = _load_and_extract("850_with_allowances.edi")

    def test_slotting_allowance_in_header(self):
        assert len(self.po.header_allowances) == 1
        assert self.po.header_allowances[0].code == "G960"

    def test_line_level_allowance(self):
        total = sum(len(li.allowances) for li in self.po.line_items)
        assert total == 1

    def test_ship_to_is_dallas_dc(self):
        st = self.po.ship_to
        assert st is not None
        assert "DALLAS" in st.entity_name

    def test_terms_extracted(self):
        assert self.po.terms == "Net 30"
