import pytest

from src.x12_tokenizer import (
    Delimiters,
    TokenizeError,
    detect_delimiters,
    tokenize,
)

# Minimal valid Walmart 850 — ISA is exactly 106 chars including segment terminator
WALMART_850_MINIMAL = (
    "ISA*00*          *00*          *ZZ*WALMART        *ZZ*SUPPLIER       "
    "*260512*0900*U*00501*000000001*0*P*>~"
    "GS*PO*WALMART*SUPPLIER*20260512*0900*1*X*005010~"
    "ST*850*0001~"
    "BEG*00*NE*PO123456**20260512~"
    "PO1*1*10*EA*5.99*PE*IN*123456789012~"
    "SE*4*0001~"
    "GE*1*1~"
    "IEA*1*000000001~"
)

# Same document with CRLF line breaks after each segment
WALMART_850_WITH_LINEBREAKS = (
    "ISA*00*          *00*          *ZZ*WALMART        *ZZ*SUPPLIER       "
    "*260512*0900*U*00501*000000001*0*P*>~\r\n"
    "GS*PO*WALMART*SUPPLIER*20260512*0900*1*X*005010~\r\n"
    "ST*850*0001~\r\n"
    "BEG*00*NE*PO123456**20260512~\r\n"
    "PO1*1*10*EA*5.99*PE*IN*123456789012~\r\n"
    "SE*4*0001~\r\n"
    "GE*1*1~\r\n"
    "IEA*1*000000001~\r\n"
)

# Document using unusual delimiters: ^ for element, | for segment, : for sub-element
UNUSUAL_DELIMITERS = (
    "ISA^00^          ^00^          ^ZZ^SENDER         ^ZZ^RECEIVER       "
    "^260512^0900^U^00501^000000001^0^P^:|"
    "GS^PO^SENDER^RECEIVER^20260512^0900^1^X^005010|"
    "ST^850^0001|"
    "SE^2^0001|"
    "GE^1^1|"
    "IEA^1^000000001|"
)

# Document with composite elements (sub-elements)
WITH_COMPOSITES = (
    "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
    "*260512*0900*U*00501*000000001*0*P*>~"
    "GS*PO*SENDER*RECEIVER*20260512*0900*1*X*005010~"
    "ST*850*0001~"
    "SLN*1**I*5*EA*10.00*PE*IN*123456>GTIN~"
    "SE*3*0001~"
    "GE*1*1~"
    "IEA*1*000000001~"
)


class TestDetectDelimiters:
    def test_standard_delimiters(self):
        delims = detect_delimiters(WALMART_850_MINIMAL)
        assert delims.element == "*"
        assert delims.sub_element == ">"
        assert delims.segment == "~"

    def test_unusual_delimiters(self):
        delims = detect_delimiters(UNUSUAL_DELIMITERS)
        assert delims.element == "^"
        assert delims.sub_element == ":"
        assert delims.segment == "|"

    def test_no_isa_raises(self):
        with pytest.raises(TokenizeError, match="No ISA segment found"):
            detect_delimiters("GS*PO*SENDER*RECEIVER~")

    def test_truncated_isa_raises(self):
        with pytest.raises(TokenizeError, match="ISA segment is too short"):
            detect_delimiters("ISA*00*          *00*")

    def test_delimiter_conflict_raises(self):
        # ISA where sub-element sep equals element sep (both *)
        bad = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*260512*0900*U*00501*000000001*0*P**~"
        )
        with pytest.raises(TokenizeError, match="Delimiter conflict"):
            detect_delimiters(bad)


class TestTokenize:
    def test_segment_count(self):
        result = tokenize(WALMART_850_MINIMAL)
        assert len(result.segments) == 8

    def test_segment_ids(self):
        result = tokenize(WALMART_850_MINIMAL)
        ids = [s.segment_id for s in result.segments]
        assert ids == ["ISA", "GS", "ST", "BEG", "PO1", "SE", "GE", "IEA"]

    def test_element_access_by_index(self):
        result = tokenize(WALMART_850_MINIMAL)
        beg = result.segments[3]
        assert beg.segment_id == "BEG"
        assert beg.element(1) == "00"
        assert beg.element(2) == "NE"
        assert beg.element(3) == "PO123456"
        assert beg.element(5) == "20260512"

    def test_element_empty_value(self):
        result = tokenize(WALMART_850_MINIMAL)
        beg = result.segments[3]
        assert beg.element(4) == ""

    def test_element_out_of_range_returns_empty(self):
        result = tokenize(WALMART_850_MINIMAL)
        beg = result.segments[3]
        assert beg.element(0) == ""
        assert beg.element(99) == ""

    def test_po1_line_item_fields(self):
        result = tokenize(WALMART_850_MINIMAL)
        po1 = result.segments[4]
        assert po1.segment_id == "PO1"
        assert po1.element(1) == "1"
        assert po1.element(2) == "10"
        assert po1.element(3) == "EA"
        assert po1.element(4) == "5.99"
        assert po1.element(7) == "123456789012"

    def test_handles_linebreaks(self):
        result = tokenize(WALMART_850_WITH_LINEBREAKS)
        assert len(result.segments) == 8
        ids = [s.segment_id for s in result.segments]
        assert ids == ["ISA", "GS", "ST", "BEG", "PO1", "SE", "GE", "IEA"]

    def test_unusual_delimiters(self):
        result = tokenize(UNUSUAL_DELIMITERS)
        assert len(result.segments) == 6
        gs = result.segments[1]
        assert gs.segment_id == "GS"
        assert gs.element(1) == "PO"

    def test_composite_elements(self):
        result = tokenize(WITH_COMPOSITES)
        sln = result.segments[3]
        assert sln.segment_id == "SLN"
        last_el = sln.elements[-1]
        assert last_el.is_composite
        assert last_el.sub_elements == ["123456", "GTIN"]

    def test_sub_element_access(self):
        result = tokenize(WITH_COMPOSITES)
        sln = result.segments[3]
        assert sln.sub_element(9, 1) == "123456"
        assert sln.sub_element(9, 2) == "GTIN"
        assert sln.sub_element(9, 3) == ""

    def test_delimiters_preserved(self):
        result = tokenize(WALMART_850_MINIMAL)
        assert result.delimiters.element == "*"
        assert result.delimiters.sub_element == ">"
        assert result.delimiters.segment == "~"

    def test_empty_input_raises(self):
        with pytest.raises(TokenizeError, match="Empty input"):
            tokenize("")

    def test_whitespace_only_raises(self):
        with pytest.raises(TokenizeError, match="Empty input"):
            tokenize("   \n\t  ")

    def test_non_edi_input_raises(self):
        with pytest.raises(TokenizeError, match="No ISA segment found"):
            tokenize('{"type": "purchase_order", "items": []}')

    def test_csv_input_raises(self):
        with pytest.raises(TokenizeError, match="No ISA segment found"):
            tokenize("item,qty,price\n12345,10,5.99\n")

    def test_leading_whitespace_before_isa(self):
        result = tokenize("  \n  " + WALMART_850_MINIMAL)
        assert result.segments[0].segment_id == "ISA"
        assert len(result.segments) == 8
