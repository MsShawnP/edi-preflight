"""Client-mode tests for edi-preflight: intake, preflight, provenance report.

Adversarial fixtures per checklist §6: unreadable/non-EDI input (blocked path),
a clean ASN, a Latin-1-encoded file, partner-ID-map resolution of a retailer the
engine can't auto-detect, and directory intake. Skipped if lailara_engagement
isn't installed (as in the repo's default CI environment).
"""

from pathlib import Path

import pytest

pytest.importorskip("lailara_engagement")

import client_mode  # noqa: E402

_SAMPLES = Path(__file__).resolve().parent.parent / "samples"

_CONFIG = """
client: {name: Meridian Farms}
engagement: {id: MER-2026-08}
as_of_date: 2026-05-10
demo: true
partners:
  PARTNERX: walmart
"""


@pytest.fixture
def cfg(tmp_path):
    p = tmp_path / "engagement.demo.yml"
    p.write_text(_CONFIG, encoding="utf-8")
    return str(p)


def _clean_856() -> str:
    return (_SAMPLES / "walmart" / "856_clean.edi").read_text()


def test_clean_856_reports_and_is_branded(cfg, tmp_path):
    src = tmp_path / "asn.edi"
    src.write_text(_clean_856(), encoding="utf-8")
    out = str(tmp_path / "client-output")
    result = client_mode.run(cfg, str(src), out)

    assert result["status"] == "ok"
    assert result["total_findings"] == 0          # 856_clean passes all checks
    assert result["files"][0]["doc_type"] == "856"
    assert result["files"][0]["retailer"] == "Walmart"
    assert result["files"][0]["retailer_source"] == "auto"

    html = Path(result["report"]).read_text(encoding="utf-8")
    assert "Meridian Farms" in html               # client header
    assert "#f5f3ee" in html                       # branded warm canvas
    assert "SHA-256" in html                       # provenance footer
    assert "DRAFT" in html                         # draft watermark


def test_non_edi_input_is_blocked(cfg, tmp_path):
    src = tmp_path / "notes.txt"
    src.write_text("this is not an EDI document\n", encoding="utf-8")
    out = str(tmp_path / "out")
    result = client_mode.run(cfg, str(src), out)

    assert result["status"] == "blocked"
    html = Path(result["readiness_report"]).read_text(encoding="utf-8")
    assert "Data Readiness" in html                # blocked -> readiness report
    assert "notes.txt" in html                     # the offending file is named


def test_latin1_encoded_file_is_read(cfg, tmp_path):
    # A Latin-1 byte (the é in "Café") must not break intake — the reader falls
    # back from UTF-8 to Latin-1 exactly as the web app does.
    text = _clean_856().replace("Artisanal Sea Salt Crackers 12ct", "Café Crackers")
    src = tmp_path / "latin1.edi"
    src.write_bytes(text.encode("latin-1"))
    out = str(tmp_path / "out")
    result = client_mode.run(cfg, str(src), out)

    assert result["status"] == "ok"
    assert result["files"][0]["doc_type"] == "856"


def test_partner_map_resolves_unknown_retailer(cfg, tmp_path):
    # Swap the receiver id (ISA08 + GS03) to one the engine can't auto-detect;
    # the partner map must still resolve it to the Walmart ruleset.
    text = (_clean_856()
            .replace("WALMART        ", "PARTNERX       ")   # ISA08 (15-wide field)
            .replace("*WALMART*", "*PARTNERX*"))             # GS03
    src = tmp_path / "asn.edi"
    src.write_text(text, encoding="utf-8")
    out = str(tmp_path / "out")
    result = client_mode.run(cfg, str(src), out)

    f = result["files"][0]
    assert result["status"] == "ok"
    assert f["retailer"] == "Walmart"
    assert f["retailer_source"] == "partner-map"


def test_unknown_retailer_without_map_falls_back_to_generic(tmp_path):
    # Same swapped file, but a config with NO partner map: the retailer is
    # unresolved and the retailer-specific layer is skipped (still processed).
    cfg_no_partners = tmp_path / "cfg.yml"
    cfg_no_partners.write_text(
        "client: {name: X}\nengagement: {id: E1}\nas_of_date: 2026-05-10\ndemo: true\n",
        encoding="utf-8",
    )
    text = (_clean_856()
            .replace("WALMART        ", "PARTNERX       ")
            .replace("*WALMART*", "*PARTNERX*"))
    src = tmp_path / "asn.edi"
    src.write_text(text, encoding="utf-8")
    out = str(tmp_path / "out")
    result = client_mode.run(str(cfg_no_partners), str(src), out)

    assert result["status"] == "ok"                 # still processed
    assert result["files"][0]["retailer_source"] == "unresolved"
    html = Path(result["report"]).read_text(encoding="utf-8")
    assert "retailer-specific layer skipped" in html.lower() or "unresolved" in html.lower()


def test_directory_intake_processes_all_files(cfg, tmp_path):
    d = tmp_path / "asns"
    d.mkdir()
    (d / "a.edi").write_text(_clean_856(), encoding="utf-8")
    (d / "b.edi").write_text((_SAMPLES / "walmart" / "856_bad_dtm.edi").read_text(),
                             encoding="utf-8")
    out = str(tmp_path / "out")
    result = client_mode.run(cfg, str(d), out)

    assert result["n_files"] == 2
    assert result["n_ok"] == 2
    assert result["total_findings"] == 4            # 856_clean (0) + 856_bad_dtm (4)


def test_850_purchase_order_path(cfg, tmp_path):
    src = tmp_path / "po.edi"
    src.write_text((_SAMPLES / "walmart" / "850_with_allowances.edi").read_text(),
                   encoding="utf-8")
    out = str(tmp_path / "out")
    result = client_mode.run(cfg, str(src), out)

    assert result["status"] == "ok"
    assert result["files"][0]["doc_type"] == "850"
    html = Path(result["report"]).read_text(encoding="utf-8")
    assert "4500012400" in html                     # PO number in the 850 summary


def test_final_flag_drops_watermark(cfg, tmp_path):
    src = tmp_path / "asn.edi"
    src.write_text(_clean_856(), encoding="utf-8")
    out = str(tmp_path / "out")
    result = client_mode.run(cfg, str(src), out, final=True)
    html = Path(result["report"]).read_text(encoding="utf-8")
    assert "ll-draft" not in html
    assert "DRAFT" not in html
