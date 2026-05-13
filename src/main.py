from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.envelope import EnvelopeError
from src.extract_850 import ExtractionError, extract_850
from src.x12_tokenizer import TokenizeError, tokenize
from src.envelope import parse_envelope

_SRC_DIR = Path(__file__).parent

app = FastAPI(title="EDI Pre-flight")
app.mount("/static", StaticFiles(directory=_SRC_DIR / "static"), name="static")

templates = Jinja2Templates(directory=_SRC_DIR / "templates")

_PO_TYPE_LABELS = {
    "DS": "Drop Ship",
    "SA": "Stand Alone",
    "BE": "Blanket Order",
    "BK": "Blanket Order",
    "NE": "New Order",
}

_PURPOSE_LABELS = {
    "00": "Original",
    "01": "Cancellation",
    "05": "Replace",
    "06": "Confirmation",
}


def _format_edi_date(value: str) -> str:
    if len(value) == 8 and value.isdigit():
        return f"{value[4:6]}/{value[6:8]}/{value[0:4]}"
    return value


def _format_currency(value: float) -> str:
    return f"${value:,.2f}"


def _format_quantity(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return f"{value:g}"


templates.env.filters["edi_date"] = _format_edi_date
templates.env.filters["currency"] = _format_currency
templates.env.filters["qty"] = _format_quantity


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.post("/parse", response_class=HTMLResponse)
async def parse_edi(
    request: Request,
    edi_text: str = Form(""),
    file: UploadFile | None = File(default=None),
):
    content = ""

    if file and file.filename:
        raw_bytes = await file.read()
        try:
            content = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            content = raw_bytes.decode("latin-1")
    elif edi_text.strip():
        content = edi_text

    if not content.strip():
        return templates.TemplateResponse(request, "partials/error.html", {
            "error": "No input provided.",
            "hint": "Paste an EDI document in the text area or upload an .edi file.",
        })

    try:
        tokens = tokenize(content)
        envelope = parse_envelope(tokens)
        po = extract_850(envelope)
    except (TokenizeError, EnvelopeError, ExtractionError) as e:
        return templates.TemplateResponse(request, "partials/error.html", {
            "error": str(e),
            "hint": getattr(e, "hint", ""),
        })
    except Exception as e:
        return templates.TemplateResponse(request, "partials/error.html", {
            "error": f"Unexpected error: {e}",
            "hint": "The document may not be a valid EDI X12 file.",
        })

    return templates.TemplateResponse(request, "partials/results.html", {
        "po": po,
        "po_type_label": _PO_TYPE_LABELS.get(po.po_type, po.po_type),
        "purpose_label": _PURPOSE_LABELS.get(po.purpose_code, po.purpose_code),
    })
