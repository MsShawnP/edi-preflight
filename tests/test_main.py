"""Endpoint tests for the FastAPI application."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)

SAMPLES = Path(__file__).parent.parent / "samples"


def _read_sample(retailer: str, filename: str) -> str:
    return (SAMPLES / retailer / filename).read_text()


class TestIndex:
    def test_returns_html(self):
        r = client.get("/")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]

    def test_contains_mode_tabs(self):
        r = client.get("/")
        assert "Inbound 850 Parser" in r.text
        assert "Outbound 856 Validator" in r.text


class TestSecurityHeaders:
    def test_csp_header_present(self):
        r = client.get("/")
        assert "Content-Security-Policy" in r.headers
        assert "default-src 'self'" in r.headers["Content-Security-Policy"]

    def test_nosniff_header(self):
        r = client.get("/")
        assert r.headers["X-Content-Type-Options"] == "nosniff"

    def test_frame_deny(self):
        r = client.get("/")
        assert r.headers["X-Frame-Options"] == "DENY"


class TestSampleEndpoint:
    def test_returns_850_sample(self):
        r = client.get("/sample/850")
        assert r.status_code == 200
        assert "ISA*" in r.text

    def test_returns_856_sample(self):
        r = client.get("/sample/856")
        assert r.status_code == 200
        assert "ISA*" in r.text

    def test_unknown_type_returns_404(self):
        r = client.get("/sample/999")
        assert r.status_code == 404


class TestParse850:
    def test_parse_valid_850(self):
        edi = _read_sample("walmart", "850_basic.edi")
        r = client.post("/parse", data={"edi_text": edi})
        assert r.status_code == 200
        assert "4500012345" in r.text

    def test_parse_empty_input(self):
        r = client.post("/parse", data={"edi_text": ""})
        assert r.status_code == 200
        assert "No input provided" in r.text

    def test_parse_invalid_edi(self):
        r = client.post("/parse", data={"edi_text": "not valid EDI"})
        assert r.status_code == 200
        assert "error" in r.text.lower()


class TestValidate856:
    def test_validate_clean_856(self):
        edi = _read_sample("walmart", "856_clean.edi")
        r = client.post("/validate", data={"edi_text": edi, "retailer": "auto"})
        assert r.status_code == 200

    def test_validate_856_with_issues(self):
        edi = _read_sample("walmart", "856_wrong_hl_order.edi")
        r = client.post("/validate", data={"edi_text": edi, "retailer": "walmart"})
        assert r.status_code == 200
        assert "finding" in r.text.lower() or "Finding" in r.text

    def test_validate_empty_input(self):
        r = client.post("/validate", data={"edi_text": "", "retailer": "auto"})
        assert r.status_code == 200
        assert "No input provided" in r.text

    def test_validate_invalid_edi(self):
        r = client.post("/validate", data={"edi_text": "garbage", "retailer": "auto"})
        assert r.status_code == 200
        assert "error" in r.text.lower()

    def test_validate_850_as_856_shows_warning(self):
        edi = _read_sample("walmart", "850_basic.edi")
        r = client.post("/validate", data={"edi_text": edi, "retailer": "auto"})
        assert r.status_code == 200
        assert "not an 856" in r.text


class TestExportCSV:
    def test_export_csv_returns_csv(self):
        edi = _read_sample("walmart", "850_basic.edi")
        r = client.post("/export/csv", data={"edi_text": edi})
        assert r.status_code == 200
        assert r.headers["content-type"] == "text/csv; charset=utf-8"
        assert "Content-Disposition" in r.headers

    def test_export_csv_invalid_input(self):
        r = client.post("/export/csv", data={"edi_text": "bad"})
        assert r.status_code == 400


class TestExportPDF:
    def test_export_pdf_returns_pdf(self):
        edi = _read_sample("walmart", "850_basic.edi")
        r = client.post("/export/pdf", data={"edi_text": edi})
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"

    def test_export_pdf_invalid_input(self):
        r = client.post("/export/pdf", data={"edi_text": "bad"})
        assert r.status_code == 400


class TestExportValidationPDF:
    def test_export_validation_pdf_returns_pdf(self):
        edi = _read_sample("walmart", "856_clean.edi")
        r = client.post("/export/validation-pdf", data={"edi_text": edi, "retailer": "walmart"})
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"

    def test_export_validation_pdf_invalid_input(self):
        r = client.post("/export/validation-pdf", data={"edi_text": "bad", "retailer": "auto"})
        assert r.status_code == 400


class TestMalformedButTokenizableInput:
    """Input that tokenizes and parses but trips the validators must return a
    friendly error/finding, never a 500."""

    def test_validate_non_numeric_se_count_does_not_500(self):
        edi = _read_sample("walmart", "856_clean.edi").replace("SE*35*", "SE*ABC*")
        r = client.post("/validate", data={"edi_text": edi, "retailer": "walmart"})
        assert r.status_code == 200
        # Surfaced as a finding, not a crash and not a generic error page.
        assert "not a number" in r.text

    def test_export_validation_pdf_non_numeric_se_count_does_not_500(self):
        edi = _read_sample("walmart", "856_clean.edi").replace("SE*35*", "SE*ABC*")
        r = client.post(
            "/export/validation-pdf", data={"edi_text": edi, "retailer": "walmart"}
        )
        # Either a valid PDF or a friendly 400 — never a 500.
        assert r.status_code in (200, 400)


class TestInputSizeLimit:
    def test_oversized_paste_rejected(self):
        huge = "ISA*" + "X" * (3 * 1024 * 1024)
        r = client.post("/parse", data={"edi_text": huge})
        assert r.status_code == 200
        assert "2 MB" in r.text
