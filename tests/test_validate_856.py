"""Tests for 856 structural and field-level validation (layers 1 and 2)."""

from pathlib import Path

from src.envelope import parse_envelope
from src.validate_856 import validate_856, Severity
from src.x12_tokenizer import tokenize

SAMPLES = Path(__file__).parent.parent / "samples" / "walmart"


def _load_and_validate(filename: str):
    raw = (SAMPLES / filename).read_text()
    tokens = tokenize(raw)
    envelope = parse_envelope(tokens)
    return validate_856(envelope)


# --- Clean document: structural + field layers should pass ---

class TestCleanDocument:
    def setup_method(self):
        self.result = _load_and_validate("856_clean.edi")

    def test_no_structural_findings(self):
        assert len(self.result.structural_findings) == 0

    def test_no_field_findings(self):
        assert len(self.result.field_findings) == 0

    def test_is_valid(self):
        assert self.result.is_valid

    def test_bsn_data_extracted(self):
        assert self.result.bsn_data["purpose_code"] == "00"
        assert self.result.bsn_data["shipment_id"] == "SHP20260510001"
        assert self.result.bsn_data["date"] == "20260510"

    def test_hl_tree_has_shipment_root(self):
        assert len(self.result.hl_tree) == 1
        assert self.result.hl_tree[0].level_code == "S"

    def test_total_fees_zero(self):
        assert self.result.total_fees == 0.0


# --- Bad DTM: field-level date format violations ---

class TestBadDtmFormat:
    def setup_method(self):
        self.result = _load_and_validate("856_bad_dtm.edi")

    def test_finds_invalid_dates(self):
        date_findings = [f for f in self.result.findings if f.rule_id in ("invalid_dtm_date", "invalid_bsn_date")]
        assert len(date_findings) >= 2

    def test_bsn_date_flagged(self):
        bsn_findings = [f for f in self.result.findings if f.rule_id == "invalid_bsn_date"]
        assert len(bsn_findings) == 1
        assert "05/10/2026" in bsn_findings[0].message

    def test_dtm_dates_flagged(self):
        dtm_findings = [f for f in self.result.findings if f.rule_id == "invalid_dtm_date"]
        assert len(dtm_findings) == 2

    def test_severity_is_may_cause_chargeback(self):
        date_findings = [f for f in self.result.findings if "date" in f.rule_id]
        for f in date_findings:
            assert f.severity == Severity.MAY_CAUSE_CHARGEBACK

    def test_layer_is_field(self):
        date_findings = [f for f in self.result.findings if "date" in f.rule_id]
        for f in date_findings:
            assert f.layer == "field"


# --- Wrong HL order: structural validation should still parse ---

class TestWrongHLOrder:
    """Wrong HL order is a retailer-specific rule (S→O→I→P), not structural.
    Structural validation just checks that HL segments exist and BSN is present.
    The ordering check is done in layer 3 (retailer-specific)."""

    def setup_method(self):
        self.result = _load_and_validate("856_wrong_hl_order.edi")

    def test_hl_tree_parsed(self):
        assert len(self.result.hl_tree) >= 1

    def test_shipment_level_found(self):
        assert self.result.hl_tree[0].level_code == "S"

    def test_no_structural_errors(self):
        assert len(self.result.structural_findings) == 0


# --- Missing segment: missing N1*ST and PRF ---

class TestMissingSegment:
    """Missing N1*ST and PRF are retailer-specific rules (layer 3).
    Structural validation only checks envelope-level requirements."""

    def setup_method(self):
        self.result = _load_and_validate("856_missing_segment.edi")

    def test_structural_layer_passes(self):
        # Missing N1*ST and PRF are retailer rules, not structural
        assert len(self.result.structural_findings) == 0

    def test_field_layer_passes(self):
        assert len(self.result.field_findings) == 0


# --- Synthetic edge cases via inline EDI ---

class TestMissingBSN:
    def test_flags_missing_bsn(self):
        raw = (
            "ISA*00*          *00*          *ZZ*CINDERHAVEN    *ZZ*WALMART        "
            "*260510*1430*U*00501*000000001*0*P*>~"
            "GS*SH*CINDERHAVEN*WALMART*20260510*143000*1*X*005010~"
            "ST*856*0001~"
            "HL*1**S~"
            "TD5*B*2*UPSN*M~"
            "SE*3*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        result = validate_856(parse_envelope(tokenize(raw)))
        bsn_findings = [f for f in result.findings if f.rule_id == "missing_bsn"]
        assert len(bsn_findings) == 1
        assert bsn_findings[0].severity == Severity.BLOCKS_TRANSMISSION


class TestNoHLSegments:
    def test_flags_no_hl_loops(self):
        raw = (
            "ISA*00*          *00*          *ZZ*CINDERHAVEN    *ZZ*WALMART        "
            "*260510*1430*U*00501*000000001*0*P*>~"
            "GS*SH*CINDERHAVEN*WALMART*20260510*143000*1*X*005010~"
            "ST*856*0001~"
            "BSN*00*SHP001*20260510*1430~"
            "SE*2*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        result = validate_856(parse_envelope(tokenize(raw)))
        hl_findings = [f for f in result.findings if f.rule_id == "no_hl_loops"]
        assert len(hl_findings) == 1


class TestWrongTransactionType:
    def test_flags_non_856(self):
        raw = (
            "ISA*00*          *00*          *ZZ*CINDERHAVEN    *ZZ*WALMART        "
            "*260510*1430*U*00501*000000001*0*P*>~"
            "GS*PO*WALMART*CINDERHAVEN*20260510*143000*1*X*005010~"
            "ST*850*0001~"
            "BEG*00*DS*4500012345**20260510~"
            "SE*2*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        result = validate_856(parse_envelope(tokenize(raw)))
        type_findings = [f for f in result.findings if f.rule_id == "wrong_transaction_type"]
        assert len(type_findings) == 1


class TestControlNumberMismatch:
    def test_flags_isa_iea_mismatch(self):
        raw = (
            "ISA*00*          *00*          *ZZ*CINDERHAVEN    *ZZ*WALMART        "
            "*260510*1430*U*00501*000000001*0*P*>~"
            "GS*SH*CINDERHAVEN*WALMART*20260510*143000*1*X*005010~"
            "ST*856*0001~"
            "BSN*00*SHP001*20260510*1430~"
            "HL*1**S~"
            "SE*3*0001~"
            "GE*1*1~"
            "IEA*1*000000099~"
        )
        result = validate_856(parse_envelope(tokenize(raw)))
        mismatch = [f for f in result.findings if f.rule_id == "isa_iea_mismatch"]
        assert len(mismatch) == 1
        assert "000000001" in mismatch[0].message
        assert "000000099" in mismatch[0].message


class TestInvalidBSNPurpose:
    def test_flags_bad_purpose_code(self):
        raw = (
            "ISA*00*          *00*          *ZZ*CINDERHAVEN    *ZZ*WALMART        "
            "*260510*1430*U*00501*000000001*0*P*>~"
            "GS*SH*CINDERHAVEN*WALMART*20260510*143000*1*X*005010~"
            "ST*856*0001~"
            "BSN*99*SHP001*20260510*1430~"
            "HL*1**S~"
            "SE*3*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        result = validate_856(parse_envelope(tokenize(raw)))
        purpose_findings = [f for f in result.findings if f.rule_id == "invalid_bsn_purpose"]
        assert len(purpose_findings) == 1
        assert "99" in purpose_findings[0].message


class TestInvalidSN1Quantity:
    def test_flags_non_numeric_quantity(self):
        raw = (
            "ISA*00*          *00*          *ZZ*CINDERHAVEN    *ZZ*WALMART        "
            "*260510*1430*U*00501*000000001*0*P*>~"
            "GS*SH*CINDERHAVEN*WALMART*20260510*143000*1*X*005010~"
            "ST*856*0001~"
            "BSN*00*SHP001*20260510*1430~"
            "HL*1**S~"
            "HL*2*1*O~"
            "PRF*PO123~"
            "HL*3*2*I~"
            "MAN*GM*001234567890123456~"
            "HL*4*3*P~"
            "SN1*1*ABC*CS~"
            "SE*9*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        result = validate_856(parse_envelope(tokenize(raw)))
        qty_findings = [f for f in result.findings if f.rule_id == "invalid_sn1_quantity"]
        assert len(qty_findings) == 1
        assert "ABC" in qty_findings[0].message

    def test_flags_zero_quantity(self):
        raw = (
            "ISA*00*          *00*          *ZZ*CINDERHAVEN    *ZZ*WALMART        "
            "*260510*1430*U*00501*000000001*0*P*>~"
            "GS*SH*CINDERHAVEN*WALMART*20260510*143000*1*X*005010~"
            "ST*856*0001~"
            "BSN*00*SHP001*20260510*1430~"
            "HL*1**S~"
            "HL*2*1*O~"
            "PRF*PO123~"
            "HL*3*2*I~"
            "MAN*GM*001234567890123456~"
            "HL*4*3*P~"
            "SN1*1*0*CS~"
            "SE*9*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        result = validate_856(parse_envelope(tokenize(raw)))
        qty_findings = [f for f in result.findings if f.rule_id == "invalid_sn1_quantity"]
        assert len(qty_findings) == 1


class TestSortedFindings:
    def test_sorted_by_severity_order(self):
        raw = (
            "ISA*00*          *00*          *ZZ*CINDERHAVEN    *ZZ*WALMART        "
            "*260510*1430*U*00501*000000001*0*P*>~"
            "GS*SH*CINDERHAVEN*WALMART*20260510*143000*1*X*005010~"
            "ST*856*0001~"
            "BSN*99*SHP001*05/10/2026*1430~"
            "HL*1**S~"
            "TD5*B*2*UPSN*Z~"
            "SE*4*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        result = validate_856(parse_envelope(tokenize(raw)))
        sorted_f = result.sorted_findings()
        for i in range(len(sorted_f) - 1):
            assert sorted_f[i].severity.order <= sorted_f[i + 1].severity.order
