import csv
import io
from pathlib import Path

from src.envelope import parse_envelope
from src.export_csv import export_csv
from src.extract_850 import extract_850
from src.x12_tokenizer import tokenize

SAMPLES = Path(__file__).parent.parent / "samples" / "walmart"


def _load_and_extract(filename: str):
    raw = (SAMPLES / filename).read_text()
    tokens = tokenize(raw)
    envelope = parse_envelope(tokens)
    return extract_850(envelope)


class TestCSVExportBasicPO:
    def setup_method(self):
        self.po = _load_and_extract("850_basic.edi")
        self.csv_text = export_csv(self.po)
        reader = csv.reader(io.StringIO(self.csv_text))
        self.rows = list(reader)

    def test_header_row_present(self):
        assert self.rows[0][0] == "PO Number"
        assert self.rows[0][4] == "Line"
        assert self.rows[0][10] == "UPC"

    def test_one_row_per_line_item(self):
        assert len(self.rows) == 4  # header + 3 line items

    def test_po_number_denormalized(self):
        for row in self.rows[1:]:
            assert row[0] == "4500012345"

    def test_retailer_denormalized(self):
        for row in self.rows[1:]:
            assert row[2] == "walmart"

    def test_ship_to_denormalized(self):
        for row in self.rows[1:]:
            assert row[3] == "WALMART DC 6025"

    def test_date_formatted(self):
        assert self.rows[1][1] == "05/10/2026"

    def test_line_item_fields(self):
        row = self.rows[1]
        assert row[4] == "1"  # line number
        assert row[5] == "Artisanal Sea Salt Crackers 12ct"
        assert row[6] == "48"  # qty (integer, no .0)
        assert row[7] == "CS"  # UOM
        assert row[8] == "24.99"  # unit price
        assert row[9] == "1199.52"  # extended

    def test_product_ids(self):
        row = self.rows[1]
        assert row[10] == "012345678901"  # UPC
        assert row[11] == "0078742031234"  # buyer item
        assert row[12] == "CRK-SEA-12"  # vendor item

    def test_csv_parseable_by_csv_reader(self):
        reader = csv.DictReader(io.StringIO(self.csv_text))
        rows = list(reader)
        assert len(rows) == 3
        assert rows[0]["PO Number"] == "4500012345"


class TestCSVExportWithAllowances:
    def setup_method(self):
        self.po = _load_and_extract("850_with_allowances.edi")
        self.csv_text = export_csv(self.po)
        reader = csv.reader(io.StringIO(self.csv_text))
        self.rows = list(reader)

    def test_line_items_present(self):
        assert len(self.rows) > 1


class TestCSVExportCatchWeight:
    def setup_method(self):
        self.po = _load_and_extract("850_catch_weight.edi")
        self.csv_text = export_csv(self.po)
        reader = csv.reader(io.StringIO(self.csv_text))
        self.rows = list(reader)

    def test_catch_weight_line_items(self):
        assert len(self.rows) > 1
