import csv
import io
from pathlib import Path

from src.envelope import Retailer, parse_envelope
from src.export_csv import export_850_csv
from src.extract_850 import extract_850
from src.x12_tokenizer import tokenize

SAMPLES = Path(__file__).parent.parent / "samples" / "walmart"


def _load_and_extract(filename: str):
    raw = (SAMPLES / filename).read_text()
    tokens = tokenize(raw)
    envelope = parse_envelope(tokens)
    return extract_850(envelope)


class TestCsvExportBasicPO:
    def setup_method(self):
        self.po = _load_and_extract("850_basic.edi")
        self.csv_text = export_850_csv(self.po)
        reader = csv.reader(io.StringIO(self.csv_text))
        self.rows = list(reader)

    def test_header_row_present(self):
        assert self.rows[0][0] == "PO Number"
        assert "UPC" in self.rows[0]

    def test_one_row_per_line_item(self):
        assert len(self.rows) == 1 + len(self.po.line_items)

    def test_po_number_in_every_row(self):
        for row in self.rows[1:]:
            assert row[0] == self.po.po_number

    def test_retailer_in_every_row(self):
        for row in self.rows[1:]:
            assert row[1] == self.po.retailer.value

    def test_extended_price_calculated(self):
        first_data = self.rows[1]
        qty = float(first_data[5])
        price = float(first_data[7])
        extended = float(first_data[8])
        assert extended == round(qty * price, 2)

    def test_ship_to_populated(self):
        first_data = self.rows[1]
        ship_to_name = first_data[18]
        assert ship_to_name == "WALMART DC 6025"

    def test_output_is_valid_csv(self):
        reader = csv.reader(io.StringIO(self.csv_text))
        rows = list(reader)
        col_count = len(rows[0])
        for row in rows:
            assert len(row) == col_count


class TestCsvExportCatchWeight:
    def setup_method(self):
        self.po = _load_and_extract("850_catch_weight.edi")
        self.csv_text = export_850_csv(self.po)
        reader = csv.reader(io.StringIO(self.csv_text))
        self.rows = list(reader)

    def test_catch_weight_flag_set(self):
        catch_weight_col = self.rows[0].index("Catch Weight")
        cw_values = [row[catch_weight_col] for row in self.rows[1:]]
        assert "Y" in cw_values

    def test_weight_populated_for_catch_weight_items(self):
        weight_col = self.rows[0].index("Weight")
        catch_weight_col = self.rows[0].index("Catch Weight")
        for row in self.rows[1:]:
            if row[catch_weight_col] == "Y":
                assert row[weight_col] != ""


class TestCsvExportEmptyPO:
    def test_csv_with_no_line_items_has_only_header(self):
        from src.extract_850 import PurchaseOrder
        po = PurchaseOrder(po_number="TEST", po_type="NE", po_date="20260101")
        csv_text = export_850_csv(po)
        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)
        assert len(rows) == 1
