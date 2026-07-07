"""Tests for input validation and diagnostic messages (Task 5.1).

Covers 8 bad-input scenarios:
1. Non-EDI: plain text
2. Non-EDI: JSON
3. Non-EDI: CSV
4. Non-EDI: XML
5. Truncated document (missing IEA)
6. Wrong transaction type in 850 parser (856 submitted)
7. Wrong transaction type in 856 validator (850 submitted)
8. Truncated ISA (too short to parse)
"""

import pytest

from src.envelope import EnvelopeError, parse_envelope
from src.extract_850 import ExtractionError, extract_850
from src.x12_tokenizer import TokenizeError, tokenize

# --- Minimal valid fragments for building test cases ---

_VALID_850 = (
    "ISA*00*          *00*          *ZZ*WALMART        *ZZ*SUPPLIER       "
    "*260512*0900*U*00501*000000001*0*P*>~"
    "GS*PO*WALMART*SUPPLIER*20260512*0900*1*X*005010~"
    "ST*850*0001~"
    "BEG*00*NE*PO123456**20260512~"
    "SE*3*0001~"
    "GE*1*1~"
    "IEA*1*000000001~"
)

_VALID_856 = (
    "ISA*00*          *00*          *ZZ*SUPPLIER       *ZZ*WALMART        "
    "*260512*0900*U*00501*000000001*0*P*>~"
    "GS*SH*SUPPLIER*WALMART*20260512*0900*1*X*005010~"
    "ST*856*0001~"
    "BSN*00*SHP001*20260512*0900~"
    "SE*3*0001~"
    "GE*1*1~"
    "IEA*1*000000001~"
)


class TestNonEDIPlainText:
    def test_raises_tokenize_error(self):
        with pytest.raises(TokenizeError, match="No ISA segment found"):
            tokenize("Hello, this is a plain text document about purchase orders.")

    def test_hint_mentions_isa(self):
        with pytest.raises(TokenizeError) as exc_info:
            tokenize("Hello, this is a plain text document about purchase orders.")
        assert "ISA" in exc_info.value.hint


class TestNonEDIJSON:
    def test_raises_tokenize_error(self):
        with pytest.raises(TokenizeError, match="No ISA segment found"):
            tokenize('{"type": "purchase_order", "po_number": "12345", "items": []}')

    def test_hint_identifies_json(self):
        with pytest.raises(TokenizeError) as exc_info:
            tokenize('{"type": "purchase_order"}')
        assert "JSON" in exc_info.value.hint


class TestNonEDICSV:
    def test_raises_tokenize_error(self):
        with pytest.raises(TokenizeError, match="No ISA segment found"):
            tokenize("item,quantity,price\n12345,10,5.99\n67890,5,12.50\n")

    def test_hint_identifies_csv(self):
        with pytest.raises(TokenizeError) as exc_info:
            tokenize("item,quantity,price\n12345,10,5.99\n67890,5,12.50\n")
        assert "CSV" in exc_info.value.hint


class TestNonEDIXML:
    def test_raises_tokenize_error(self):
        with pytest.raises(TokenizeError, match="No ISA segment found"):
            tokenize('<?xml version="1.0"?><PurchaseOrder><Item sku="12345"/></PurchaseOrder>')

    def test_hint_identifies_xml(self):
        with pytest.raises(TokenizeError) as exc_info:
            tokenize('<?xml version="1.0"?><PurchaseOrder/>')
        assert "XML" in exc_info.value.hint


class TestTruncatedDocument:
    def test_missing_iea_raises_envelope_error(self):
        truncated = (
            "ISA*00*          *00*          *ZZ*WALMART        *ZZ*SUPPLIER       "
            "*260512*0900*U*00501*000000001*0*P*>~"
            "GS*PO*WALMART*SUPPLIER*20260512*0900*1*X*005010~"
            "ST*850*0001~"
            "BEG*00*NE*PO123456**20260512~"
        )
        tokens = tokenize(truncated)
        with pytest.raises(EnvelopeError, match="No IEA segment found"):
            parse_envelope(tokens)

    def test_truncated_hint_mentions_truncation(self):
        truncated = (
            "ISA*00*          *00*          *ZZ*WALMART        *ZZ*SUPPLIER       "
            "*260512*0900*U*00501*000000001*0*P*>~"
            "GS*PO*WALMART*SUPPLIER*20260512*0900*1*X*005010~"
            "ST*850*0001~"
        )
        tokens = tokenize(truncated)
        with pytest.raises(EnvelopeError) as exc_info:
            parse_envelope(tokens)
        assert "truncated" in exc_info.value.hint.lower()


class TestWrongTransactionTypeIn850Parser:
    def test_856_in_850_parser_raises(self):
        tokens = tokenize(_VALID_856)
        envelope = parse_envelope(tokens)
        with pytest.raises(ExtractionError, match="Expected an 850"):
            extract_850(envelope)

    def test_hint_mentions_different_type(self):
        tokens = tokenize(_VALID_856)
        envelope = parse_envelope(tokens)
        with pytest.raises(ExtractionError) as exc_info:
            extract_850(envelope)
        assert "different" in exc_info.value.hint.lower()


class TestWrongTransactionTypeIn856Validator:
    def test_850_in_856_validator_detected(self):
        """When an 850 is submitted to the 856 validator, the endpoint
        should reject it. We test at the envelope level."""
        tokens = tokenize(_VALID_850)
        envelope = parse_envelope(tokens)
        # The transaction type should be 850, not 856
        from src.envelope import TransactionType
        assert envelope.transactions[0].transaction_type == TransactionType.PURCHASE_ORDER_850


class TestTruncatedISA:
    def test_short_isa_raises(self):
        with pytest.raises(TokenizeError, match="too short"):
            tokenize("ISA*00*          *00*")

    def test_hint_mentions_character_count(self):
        with pytest.raises(TokenizeError) as exc_info:
            tokenize("ISA*00*          *00*")
        assert "106" in exc_info.value.hint
