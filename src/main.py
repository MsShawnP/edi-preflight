from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.envelope import EnvelopeError, parse_envelope
from src.export_csv import export_csv
from src.export_pdf import export_pdf
from src.extract_850 import ExtractionError, extract_850
from src.x12_tokenizer import TokenizeError, tokenize

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
    "CN": "Consigned",
    "NP": "New Product",
    "RO": "Rush Order",
    "ZZ": "Consignment",
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


async def _read_edi_content(
    edi_text: str = "",
    file: UploadFile | None = None,
) -> str:
    if file and file.filename:
        raw_bytes = await file.read()
        try:
            return raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return raw_bytes.decode("latin-1")
    elif edi_text.strip():
        return edi_text
    return ""


@app.post("/parse", response_class=HTMLResponse)
async def parse_edi(
    request: Request,
    edi_text: str = Form(""),
    file: UploadFile | None = File(default=None),
):
    content = await _read_edi_content(edi_text, file)

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
        "edi_content": content,
    })


@app.post("/export/csv")
async def export_csv_endpoint(edi_text: str = Form("")):
    tokens = tokenize(edi_text)
    envelope = parse_envelope(tokens)
    po = extract_850(envelope)
    csv_data = export_csv(po)
    filename = f"PO_{po.po_number}.csv" if po.po_number else "purchase_order.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/export/pdf")
async def export_pdf_endpoint(edi_text: str = Form("")):
    tokens = tokenize(edi_text)
    envelope = parse_envelope(tokens)
    po = extract_850(envelope)
    pdf_data = export_pdf(po)
    filename = f"PO_{po.po_number}.pdf" if po.po_number else "purchase_order.pdf"
    return Response(
        content=pdf_data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
