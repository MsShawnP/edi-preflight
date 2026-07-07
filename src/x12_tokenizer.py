from dataclasses import dataclass, field


@dataclass(frozen=True)
class Delimiters:
    element: str
    sub_element: str
    segment: str
    repetition: str = ""


@dataclass
class Element:
    value: str
    sub_elements: list[str] = field(default_factory=list)

    @property
    def is_composite(self) -> bool:
        return len(self.sub_elements) > 1

    def __str__(self) -> str:
        return self.value


@dataclass
class Segment:
    segment_id: str
    elements: list[Element] = field(default_factory=list)
    raw: str = ""

    def element(self, index: int) -> str:
        """Get element value by 1-based index (matching EDI convention).
        ISA01 = index 1, ISA02 = index 2, etc."""
        if index < 1 or index > len(self.elements):
            return ""
        return self.elements[index - 1].value

    def sub_element(self, element_index: int, sub_index: int) -> str:
        """Get sub-element by 1-based element index and 1-based sub-element index."""
        if element_index < 1 or element_index > len(self.elements):
            return ""
        el = self.elements[element_index - 1]
        if sub_index < 1 or sub_index > len(el.sub_elements):
            return ""
        return el.sub_elements[sub_index - 1]


@dataclass
class TokenizeResult:
    delimiters: Delimiters
    segments: list[Segment]
    raw: str


class TokenizeError(Exception):
    """Raised when EDI text cannot be tokenized."""

    def __init__(self, message: str, hint: str = ""):
        self.hint = hint
        super().__init__(message)


def _detect_input_format(raw: str) -> str:
    """Return a format-specific hint when the input is clearly not EDI."""
    stripped = raw.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        return ("This looks like JSON, not EDI. EDI X12 documents start with "
                "an ISA segment (e.g., ISA*00*...).")
    if stripped.startswith("<?xml") or stripped.startswith("<"):
        return ("This looks like XML, not EDI. EDI X12 documents start with "
                "an ISA segment (e.g., ISA*00*...).")
    if "," in stripped.split("\n")[0] and stripped.count(",") > stripped.count("*"):
        return ("This looks like CSV or tabular data, not EDI. EDI X12 "
                "documents start with an ISA segment (e.g., ISA*00*...).")
    return ("EDI X12 documents start with an ISA segment. Check that you "
            "pasted the complete document.")


def detect_delimiters(raw: str) -> Delimiters:
    """Detect delimiters from the ISA segment.

    ISA is fixed-length: 106 characters including the segment terminator.
    - Index 3: element separator (character after "ISA")
    - Index 104: sub-element separator (ISA16)
    - Index 105: segment terminator
    - Index 82: repetition separator (ISA11, v4020+)
    """
    isa_pos = raw.find("ISA")
    if isa_pos == -1:
        hint = _detect_input_format(raw)
        raise TokenizeError(
            "No ISA segment found — this doesn't look like an EDI X12 document.",
            hint=hint,
        )

    text_from_isa = raw[isa_pos:]
    if len(text_from_isa) < 106:
        raise TokenizeError(
            "ISA segment is too short — the document appears truncated.",
            hint=f"Expected at least 106 characters from ISA, got {len(text_from_isa)}. "
            "The document may be incomplete.",
        )

    element_sep = text_from_isa[3]
    sub_element_sep = text_from_isa[104]
    segment_term = text_from_isa[105]
    repetition_sep = text_from_isa[82]

    if element_sep == sub_element_sep or element_sep == segment_term or sub_element_sep == segment_term:
        raise TokenizeError(
            "Delimiter conflict — element separator, sub-element separator, and "
            "segment terminator must all be different characters.",
            hint=f"Detected: element='{element_sep}', sub-element='{sub_element_sep}', "
            f"segment='{segment_term}'.",
        )

    return Delimiters(
        element=element_sep,
        sub_element=sub_element_sep,
        segment=segment_term,
        repetition=repetition_sep,
    )


def _strip_line_breaks(raw: str, segment_term: str) -> str:
    """Remove CR/LF characters that appear after segment terminators.

    Many systems insert line breaks after segment terminators for readability.
    These are not part of the EDI data and must be stripped before splitting."""
    cleaned = raw.replace(segment_term + "\r\n", segment_term)
    cleaned = cleaned.replace(segment_term + "\n", segment_term)
    cleaned = cleaned.replace(segment_term + "\r", segment_term)
    return cleaned


def _parse_segment(raw_segment: str, delimiters: Delimiters) -> Segment:
    parts = raw_segment.split(delimiters.element)
    segment_id = parts[0]
    elements = []
    for part in parts[1:]:
        sub_parts = part.split(delimiters.sub_element)
        elements.append(Element(value=part, sub_elements=sub_parts))
    return Segment(segment_id=segment_id, elements=elements, raw=raw_segment)


def tokenize(raw: str) -> TokenizeResult:
    """Tokenize raw EDI X12 text into segments with elements and sub-elements."""
    raw = raw.strip()
    if not raw:
        raise TokenizeError(
            "Empty input — nothing to parse.",
            hint="Paste or upload an EDI document to get started.",
        )

    delimiters = detect_delimiters(raw)
    cleaned = _strip_line_breaks(raw, delimiters.segment)

    isa_pos = cleaned.find("ISA")
    cleaned = cleaned[isa_pos:]

    raw_segments = cleaned.split(delimiters.segment)
    raw_segments = [s.strip() for s in raw_segments if s.strip()]

    if not raw_segments:
        raise TokenizeError(
            "No segments found after splitting — the document may use an "
            "unexpected format.",
        )

    segments = [_parse_segment(s, delimiters) for s in raw_segments]

    return TokenizeResult(delimiters=delimiters, segments=segments, raw=raw)
