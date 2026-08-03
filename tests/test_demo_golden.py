"""Demo golden-file lock for edi-preflight.

Pins the engine output on the two files the deployed demo actually serves
(``src.main._SAMPLE_FILES``) so the live site's demo experience cannot drift
during the client-mode conversion. If either the served sample file or the
engine changes what the demo shows, these tests fail on purpose.

The 856 sample (``856_bad_dtm``) is deliberately chosen to exercise a
chargeback-tier rule so the demo's "Est. Chargebacks" tile is non-empty; the
850 sample (``850_with_allowances``) exercises header + line allowances. See
the note in ``src/main.py`` next to ``_SAMPLE_FILES``.
"""

from collections import Counter

from src.envelope import Retailer, parse_envelope
from src.extract_850 import extract_850
from src.main import _SAMPLE_FILES
from src.validate_856 import validate_856
from src.validate_856_walmart import validate_856_walmart
from src.x12_tokenizer import tokenize


def _load(doc_type: str) -> str:
    return _SAMPLE_FILES[doc_type].read_text()


class TestDemo856Golden:
    """Locks the deployed 856 demo (walmart/856_bad_dtm.edi)."""

    def test_sample_856_is_the_walmart_bad_dtm_file(self):
        assert _SAMPLE_FILES["856"].name == "856_bad_dtm.edi"

    def test_sample_856_findings_are_locked(self):
        env = parse_envelope(tokenize(_load("856")))
        assert env.retailer is Retailer.WALMART
        result = validate_856_walmart(validate_856(env))
        assert len(result.findings) == 4
        by_severity = dict(Counter(f.severity.value for f in result.findings))
        assert by_severity == {
            "may-cause-chargeback": 3,
            "will-cause-chargeback": 1,
        }
        assert sorted(f.rule_id for f in result.findings) == [
            "invalid_bsn_date",
            "invalid_dtm_date",
            "invalid_dtm_date",
            "invalid_sscc18_format",
        ]

    def test_sample_856_fee_breakdown_is_locked(self):
        env = parse_envelope(tokenize(_load("856")))
        result = validate_856_walmart(validate_856(env))
        # One $1/case labeling defect; per-basis breakdown, never a cross-basis sum.
        assert result.fee_breakdown == [
            {"fee_per": "case", "count": 1, "subtotal": 1.0}
        ]


class TestDemo850Golden:
    """Locks the deployed 850 demo (walmart/850_with_allowances.edi)."""

    def test_sample_850_is_the_walmart_with_allowances_file(self):
        assert _SAMPLE_FILES["850"].name == "850_with_allowances.edi"

    def test_sample_850_extraction_is_locked(self):
        env = parse_envelope(tokenize(_load("850")))
        assert env.retailer is Retailer.WALMART
        po = extract_850(env)
        assert po.po_number == "4500012400"
        assert po.po_type == "SA"
        assert po.purpose_code == "00"
        assert len(po.line_items) == 3
        assert po.total_line_items == 3
        assert po.total_quantity == 420.0
        assert po.total_amount == 9329.7
        assert len(po.header_allowances) == 2
        assert len(po.all_allowances) == 6
        assert [(a.entity_code, a.entity_name) for a in po.addresses] == [
            ("ST", "WALMART RDC 7033"),
            ("BT", "WALMART ACCOUNTS PAYABLE"),
        ]
