import pytest

from src.envelope import (
    Envelope,
    EnvelopeError,
    Retailer,
    TransactionType,
    detect_retailer,
    parse_envelope,
)
from src.x12_tokenizer import tokenize


def _make_edi(sender_id: str, receiver_id: str, gs_sender: str = "", gs_receiver: str = "",
              tx_type: str = "850", gs_func: str = "PO") -> str:
    """Build a minimal valid EDI document with the given ISA/GS identifiers."""
    sender_padded = sender_id.ljust(15)
    receiver_padded = receiver_id.ljust(15)
    gs_s = gs_sender or sender_id
    gs_r = gs_receiver or receiver_id
    return (
        f"ISA*00*          *00*          *ZZ*{sender_padded}*ZZ*{receiver_padded}"
        f"*260512*0900*U*00501*000000001*0*P*>~"
        f"GS*{gs_func}*{gs_s}*{gs_r}*20260512*0900*1*X*005010~"
        f"ST*{tx_type}*0001~"
        f"BEG*00*NE*PO123456**20260512~"
        f"SE*3*0001~"
        f"GE*1*1~"
        f"IEA*1*000000001~"
    )


WALMART_850 = _make_edi("WALMART", "SUPPLIER")
AMAZON_850 = _make_edi("AMAZON", "SUPPLIER")
UNFI_850 = _make_edi("UNFI", "SUPPLIER")
KEHE_850 = _make_edi("KEHE", "SUPPLIER")
COSTCO_850 = _make_edi("COSTCO", "SUPPLIER")
UNKNOWN_850 = _make_edi("XYZPARTNER", "SUPPLIER")

# Retailer detection via DUNS IDs (no name in the string)
KEHE_DUNS_850 = _make_edi("0569813430000", "SUPPLIER")
WALMART_DUNS_850 = _make_edi("0078742000000", "SUPPLIER")
COSTCO_PHONE_850 = _make_edi("4253138601CH", "SUPPLIER")

# Retailer as receiver (outbound 856 scenario)
WALMART_856_OUTBOUND = _make_edi("SUPPLIER", "WALMART", "SUPPLIER", "WALMART",
                                  tx_type="856", gs_func="SH")

# Document missing IEA
NO_IEA = (
    "ISA*00*          *00*          *ZZ*WALMART        *ZZ*SUPPLIER       "
    "*260512*0900*U*00501*000000001*0*P*>~"
    "GS*PO*WALMART*SUPPLIER*20260512*0900*1*X*005010~"
    "ST*850*0001~"
    "SE*2*0001~"
    "GE*1*1~"
)


class TestRetailerDetection:
    def test_walmart_from_sender_name(self):
        result = tokenize(WALMART_850)
        assert detect_retailer(result) == Retailer.WALMART

    def test_amazon_from_sender_name(self):
        result = tokenize(AMAZON_850)
        assert detect_retailer(result) == Retailer.AMAZON

    def test_unfi_from_sender_name(self):
        result = tokenize(UNFI_850)
        assert detect_retailer(result) == Retailer.UNFI

    def test_kehe_from_sender_name(self):
        result = tokenize(KEHE_850)
        assert detect_retailer(result) == Retailer.KEHE

    def test_costco_from_sender_name(self):
        result = tokenize(COSTCO_850)
        assert detect_retailer(result) == Retailer.COSTCO

    def test_unknown_retailer(self):
        result = tokenize(UNKNOWN_850)
        assert detect_retailer(result) == Retailer.UNKNOWN

    def test_kehe_from_duns_id(self):
        result = tokenize(KEHE_DUNS_850)
        assert detect_retailer(result) == Retailer.KEHE

    def test_walmart_from_duns_id(self):
        result = tokenize(WALMART_DUNS_850)
        assert detect_retailer(result) == Retailer.WALMART

    def test_costco_from_phone_id(self):
        result = tokenize(COSTCO_PHONE_850)
        assert detect_retailer(result) == Retailer.COSTCO

    def test_walmart_from_receiver_in_856(self):
        result = tokenize(WALMART_856_OUTBOUND)
        assert detect_retailer(result) == Retailer.WALMART

    def test_case_insensitive_detection(self):
        edi = _make_edi("Walmart", "supplier")
        result = tokenize(edi)
        assert detect_retailer(result) == Retailer.WALMART

    def test_partial_match_wmt(self):
        edi = _make_edi("WMT-US-001", "SUPPLIER")
        result = tokenize(edi)
        assert detect_retailer(result) == Retailer.WALMART

    def test_partial_match_amzn(self):
        edi = _make_edi("AMZN-VC-001", "SUPPLIER")
        result = tokenize(edi)
        assert detect_retailer(result) == Retailer.AMAZON


class TestParseEnvelope:
    def test_interchange_fields(self):
        result = tokenize(WALMART_850)
        env = parse_envelope(result)
        assert env.interchange.sender_qualifier == "ZZ"
        assert env.interchange.sender_id == "WALMART"
        assert env.interchange.receiver_qualifier == "ZZ"
        assert env.interchange.receiver_id == "SUPPLIER"
        assert env.interchange.date == "260512"
        assert env.interchange.time == "0900"
        assert env.interchange.control_number == "000000001"
        assert env.interchange.version == "00501"
        assert env.interchange.test_indicator == "P"

    def test_functional_group(self):
        result = tokenize(WALMART_850)
        env = parse_envelope(result)
        assert len(env.groups) == 1
        group = env.groups[0]
        assert group.functional_id == "PO"
        assert group.sender_code == "WALMART"
        assert group.receiver_code == "SUPPLIER"
        assert group.transaction_type == TransactionType.PURCHASE_ORDER_850

    def test_transaction_set_850(self):
        result = tokenize(WALMART_850)
        env = parse_envelope(result)
        assert len(env.transactions) == 1
        tx = env.transactions[0]
        assert tx.transaction_type == TransactionType.PURCHASE_ORDER_850
        assert tx.control_number == "0001"

    def test_transaction_set_856(self):
        result = tokenize(WALMART_856_OUTBOUND)
        env = parse_envelope(result)
        assert len(env.transactions) == 1
        tx = env.transactions[0]
        assert tx.transaction_type == TransactionType.ASN_856

    def test_transaction_segments_exclude_st_se(self):
        result = tokenize(WALMART_850)
        env = parse_envelope(result)
        tx = env.transactions[0]
        segment_ids = [s.segment_id for s in tx.segments]
        assert "ST" not in segment_ids
        assert "SE" not in segment_ids
        assert "BEG" in segment_ids

    def test_retailer_set_on_envelope(self):
        result = tokenize(WALMART_850)
        env = parse_envelope(result)
        assert env.retailer == Retailer.WALMART

    def test_all_segments_preserved(self):
        result = tokenize(WALMART_850)
        env = parse_envelope(result)
        ids = [s.segment_id for s in env.all_segments]
        assert ids == ["ISA", "GS", "ST", "BEG", "SE", "GE", "IEA"]

    def test_missing_iea_raises(self):
        result = tokenize(NO_IEA)
        with pytest.raises(EnvelopeError, match="No IEA segment found"):
            parse_envelope(result)

    def test_gs_func_id_maps_to_856(self):
        result = tokenize(WALMART_856_OUTBOUND)
        env = parse_envelope(result)
        assert env.groups[0].functional_id == "SH"
        assert env.groups[0].transaction_type == TransactionType.ASN_856


class TestMultipleTransactions:
    def test_two_transactions_in_one_group(self):
        edi = (
            "ISA*00*          *00*          *ZZ*WALMART        *ZZ*SUPPLIER       "
            "*260512*0900*U*00501*000000001*0*P*>~"
            "GS*PO*WALMART*SUPPLIER*20260512*0900*1*X*005010~"
            "ST*850*0001~"
            "BEG*00*NE*PO-001**20260512~"
            "SE*3*0001~"
            "ST*850*0002~"
            "BEG*00*NE*PO-002**20260512~"
            "SE*3*0002~"
            "GE*2*1~"
            "IEA*1*000000001~"
        )
        result = tokenize(edi)
        env = parse_envelope(result)
        assert len(env.transactions) == 2
        assert env.transactions[0].control_number == "0001"
        assert env.transactions[1].control_number == "0002"
        po1_beg = env.transactions[0].segments[0]
        assert po1_beg.element(3) == "PO-001"
        po2_beg = env.transactions[1].segments[0]
        assert po2_beg.element(3) == "PO-002"
