"""Tests for shared retailer validation logic (validate_856_common.py)."""

from src.envelope import parse_envelope
from src.validate_856 import validate_856, Severity
from src.validate_856_common import RetailerConfig, run_retailer_checks, validate_sscc18
from src.x12_tokenizer import tokenize

_FEES = {
    "missing_sscc18": {"fee": 100.00, "per": "case"},
    "invalid_sscc18_format": {"fee": 100.00, "per": "case"},
    "wrong_hl_hierarchy": {"fee": 0.00, "per": "document"},
    "missing_catch_weight": {"fee": 100.00, "per": "item"},
    "missing_po_reference": {"fee": 0.00, "per": "order"},
    "missing_ship_to": {"fee": 0.00, "per": "document"},
    "missing_ship_date": {"fee": 0.00, "per": "document"},
    "missing_carrier": {"fee": 0.00, "per": "document"},
}

_CONFIG = RetailerConfig(name="TestRetailer", fees=_FEES)


def _validate(raw: str):
    result = validate_856(parse_envelope(tokenize(raw)))
    return run_retailer_checks(result, _CONFIG)


class TestUnknownHLLevel:
    def test_flags_unknown_level_code(self):
        raw = (
            "ISA*00*          *00*          *ZZ*CINDERHAVEN    *ZZ*WALMART        "
            "*260510*1430*U*00501*000000001*0*P*>~"
            "GS*SH*CINDERHAVEN*WALMART*20260510*143000*1*X*005010~"
            "ST*856*0001~"
            "BSN*00*SHP001*20260510*1430~"
            "HL*1**S~"
            "TD5*B*2*UPSN*M~"
            "DTM*011*20260510~"
            "N1*ST*WAREHOUSE*92*WH001~"
            "HL*2*1*X~"
            "SE*7*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        result = _validate(raw)
        findings = [f for f in result.findings if f.rule_id == "unknown_hl_level"]
        assert len(findings) == 1
        assert "'X'" in findings[0].message
        assert findings[0].severity == Severity.BLOCKS_TRANSMISSION


class TestInvalidSSCC18Format:
    def test_flags_bad_check_digit(self):
        raw = (
            "ISA*00*          *00*          *ZZ*CINDERHAVEN    *ZZ*WALMART        "
            "*260510*1430*U*00501*000000001*0*P*>~"
            "GS*SH*CINDERHAVEN*WALMART*20260510*143000*1*X*005010~"
            "ST*856*0001~"
            "BSN*00*SHP001*20260510*1430~"
            "HL*1**S~"
            "TD5*B*2*UPSN*M~"
            "DTM*011*20260510~"
            "N1*ST*WAREHOUSE*92*WH001~"
            "HL*2*1*O~"
            "PRF*PO123~"
            "HL*3*2*I~"
            "MAN*GM*006141410000123459~"
            "SE*10*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        result = _validate(raw)
        findings = [f for f in result.findings if f.rule_id == "invalid_sscc18_format"]
        assert len(findings) == 1
        assert findings[0].severity == Severity.WILL_CAUSE_CHARGEBACK
        assert findings[0].fee == 100.00

    def test_flags_short_sscc18(self):
        raw = (
            "ISA*00*          *00*          *ZZ*CINDERHAVEN    *ZZ*WALMART        "
            "*260510*1430*U*00501*000000001*0*P*>~"
            "GS*SH*CINDERHAVEN*WALMART*20260510*143000*1*X*005010~"
            "ST*856*0001~"
            "BSN*00*SHP001*20260510*1430~"
            "HL*1**S~"
            "TD5*B*2*UPSN*M~"
            "DTM*011*20260510~"
            "N1*ST*WAREHOUSE*92*WH001~"
            "HL*2*1*O~"
            "PRF*PO123~"
            "HL*3*2*I~"
            "MAN*GM*12345~"
            "SE*10*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        result = _validate(raw)
        findings = [f for f in result.findings if f.rule_id == "invalid_sscc18_format"]
        assert len(findings) == 1
        assert "5 digits" in findings[0].message


class TestValidateSSCC18Function:
    def test_valid_sscc18_returns_none(self):
        assert validate_sscc18("006141410000123452") is None

    def test_short_value_returns_error(self):
        error = validate_sscc18("1234567890")
        assert error is not None
        assert "10 digits" in error

    def test_non_numeric_returns_error(self):
        error = validate_sscc18("00614141ABCD123452")
        assert error is not None
        assert "non-numeric" in error

    def test_bad_check_digit_returns_error(self):
        error = validate_sscc18("006141410000123459")
        assert error is not None
        assert "check digit" in error

    def test_all_zeros_valid(self):
        assert validate_sscc18("000000000000000000") is None


class TestRetailerConfigDefaults:
    def test_all_checks_enabled_by_default(self):
        config = RetailerConfig(name="Test", fees={})
        assert config.require_sscc18 is True
        assert config.require_td5 is True
        assert config.require_dtm_011 is True
        assert config.require_ship_to is True
        assert config.require_prf is True
        assert config.check_catch_weight is True

    def test_checks_can_be_disabled(self):
        config = RetailerConfig(
            name="Test", fees={},
            require_sscc18=False, require_td5=False,
        )
        assert config.require_sscc18 is False
        assert config.require_td5 is False
