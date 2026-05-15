import re
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.envelope import EnvelopeError, Retailer, TransactionType, parse_envelope
from src.export_csv import export_850_csv
from src.export_pdf import export_850_pdf
from src.export_validation_pdf import export_validation_pdf
from src.extract_850 import ExtractionError, extract_850
from src.validate_856 import validate_856
from src.validate_856_amazon import validate_856_amazon
from src.validate_856_costco import validate_856_costco
from src.validate_856_kehe import validate_856_kehe
from src.validate_856_unfi import validate_856_unfi
from src.validate_856_walmart import validate_856_walmart
from src.formatting import format_currency, format_edi_date, format_quantity
from src.x12_tokenizer import TokenizeError, tokenize

_SRC_DIR = Path(__file__).parent
_MAX_INPUT_BYTES = 2 * 1024 * 1024  # 2 MB

app = FastAPI(title="EDI Pre-flight", docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' https://www.googletagmanager.com; "
        "img-src 'self' data: https://www.google-analytics.com; "
        "connect-src 'self' https://www.google-analytics.com https://analytics.google.com; "
        "style-src 'self' 'unsafe-inline'"
    )
    if response.headers.get("content-type", "").startswith("text/html"):
        response.headers["Cache-Control"] = "no-cache"
    return response


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


_SAMPLES_DIR = _SRC_DIR.parent / "samples"

templates.env.filters["edi_date"] = format_edi_date
templates.env.filters["currency"] = format_currency
templates.env.filters["qty"] = format_quantity


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


_SAMPLE_FILES = {
    "850": _SAMPLES_DIR / "walmart" / "850_with_allowances.edi",
    "856": _SAMPLES_DIR / "walmart" / "856_wrong_hl_order.edi",
}


@app.get("/sample/{doc_type}")
def get_sample(doc_type: str):
    path = _SAMPLE_FILES.get(doc_type)
    if not path or not path.exists():
        return Response(content="Sample not found", status_code=404)
    return Response(content=path.read_text(), media_type="text/plain")


class InputTooLargeError(Exception):
    pass


async def _read_edi_content(
    edi_text: str = "",
    file: UploadFile | None = None,
) -> str:
    if file and file.filename:
        raw_bytes = await file.read()
        if len(raw_bytes) > _MAX_INPUT_BYTES:
            raise InputTooLargeError(
                f"File exceeds the 2 MB limit ({len(raw_bytes):,} bytes)."
            )
        try:
            return raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return raw_bytes.decode("latin-1")
    if edi_text.strip():
        if len(edi_text.encode("utf-8")) > _MAX_INPUT_BYTES:
            raise InputTooLargeError("Pasted text exceeds the 2 MB limit.")
        return edi_text
    return ""


@app.post("/parse", response_class=HTMLResponse)
async def parse_edi(
    request: Request,
    edi_text: str = Form(""),
    file: UploadFile | None = File(default=None),
):
    try:
        content = await _read_edi_content(edi_text, file)
    except InputTooLargeError as e:
        return templates.TemplateResponse(request, "partials/error.html", {
            "error": str(e),
            "hint": "EDI documents are typically under 100 KB. Check that you're uploading the right file.",
        })

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
    except Exception:
        return templates.TemplateResponse(request, "partials/error.html", {
            "error": "An unexpected error occurred while processing the document.",
            "hint": "The document may not be a valid EDI X12 file.",
        })

    return templates.TemplateResponse(request, "partials/results.html", {
        "po": po,
        "po_type_label": _PO_TYPE_LABELS.get(po.po_type, po.po_type),
        "purpose_label": _PURPOSE_LABELS.get(po.purpose_code, po.purpose_code),
        "edi_content": content,
    })


def _safe_filename(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "", value)


def _validate_856_or_error(edi_text: str, retailer: str = "auto"):
    try:
        tokens = tokenize(edi_text)
        envelope = parse_envelope(tokens)
    except (TokenizeError, EnvelopeError) as e:
        return None, None, None, Response(
            content=str(e), status_code=400, media_type="text/plain",
        )
    except Exception:
        return None, None, None, Response(
            content="An unexpected error occurred while processing the document.",
            status_code=400,
            media_type="text/plain",
        )

    result = validate_856(envelope)

    detected = envelope.retailer
    if retailer != "auto":
        try:
            detected = Retailer(retailer)
        except ValueError:
            pass

    validator = _RETAILER_VALIDATORS.get(detected)
    if validator:
        result = validator(result)

    retailer_label = _RETAILER_LABELS.get(detected, detected.value.title())
    return result, retailer_label, detected, None


def _extract_po_or_error(edi_text: str):
    try:
        tokens = tokenize(edi_text)
        envelope = parse_envelope(tokens)
        return extract_850(envelope), None
    except (TokenizeError, EnvelopeError, ExtractionError) as e:
        return None, Response(content=str(e), status_code=400, media_type="text/plain")
    except Exception:
        return None, Response(
            content="An unexpected error occurred while processing the document.",
            status_code=400,
            media_type="text/plain",
        )


@app.post("/export/csv")
def export_csv(edi_text: str = Form("")):
    po, error = _extract_po_or_error(edi_text)
    if error:
        return error

    csv_content = export_850_csv(po)
    filename = f"PO_{_safe_filename(po.po_number)}.csv" if po.po_number else "purchase_order.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/export/pdf")
def export_pdf(edi_text: str = Form("")):
    po, error = _extract_po_or_error(edi_text)
    if error:
        return error

    pdf_bytes = export_850_pdf(po)
    filename = f"PO_{_safe_filename(po.po_number)}.pdf" if po.po_number else "purchase_order.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


_RETAILER_VALIDATORS = {
    Retailer.WALMART: validate_856_walmart,
    Retailer.AMAZON: validate_856_amazon,
    Retailer.UNFI: validate_856_unfi,
    Retailer.KEHE: validate_856_kehe,
    Retailer.COSTCO: validate_856_costco,
}

_RETAILER_LABELS = {
    Retailer.WALMART: "Walmart",
    Retailer.AMAZON: "Amazon",
    Retailer.UNFI: "UNFI",
    Retailer.KEHE: "KeHE",
    Retailer.COSTCO: "Costco",
    Retailer.UNKNOWN: "Unknown",
}


@app.post("/validate", response_class=HTMLResponse)
async def validate_edi(
    request: Request,
    edi_text: str = Form(""),
    retailer: str = Form("auto"),
    file: UploadFile | None = File(default=None),
):
    try:
        content = await _read_edi_content(edi_text, file)
    except InputTooLargeError as e:
        return templates.TemplateResponse(request, "partials/error.html", {
            "error": str(e),
            "hint": "EDI documents are typically under 100 KB. Check that you're uploading the right file.",
        })

    if not content.strip():
        return templates.TemplateResponse(request, "partials/error.html", {
            "error": "No input provided.",
            "hint": "Paste an EDI document in the text area or upload an .edi file.",
        })

    try:
        tokens = tokenize(content)
        envelope = parse_envelope(tokens)
    except (TokenizeError, EnvelopeError) as e:
        return templates.TemplateResponse(request, "partials/error.html", {
            "error": str(e),
            "hint": getattr(e, "hint", ""),
        })
    except Exception:
        return templates.TemplateResponse(request, "partials/error.html", {
            "error": "An unexpected error occurred while processing the document.",
            "hint": "The document may not be a valid EDI X12 file.",
        })

    # Check transaction type — warn if this isn't an 856
    if envelope.transactions:
        tx_type = envelope.transactions[0].transaction_type
        if tx_type != TransactionType.ASN_856:
            type_label = tx_type.value if tx_type != TransactionType.UNKNOWN else "unknown"
            return templates.TemplateResponse(request, "partials/error.html", {
                "error": f"This document is a {type_label} transaction, not an 856 ASN.",
                "hint": "The outbound validator checks 856 Advance Ship Notices. "
                        "Switch to the Inbound 850 Parser tab if this is a "
                        "purchase order.",
            })

    # Run structural + field-level validation
    result = validate_856(envelope)

    # Determine retailer for layer 3
    detected = envelope.retailer
    if retailer != "auto":
        try:
            detected = Retailer(retailer)
        except ValueError:
            pass

    # Run retailer-specific validation if available
    validator = _RETAILER_VALIDATORS.get(detected)
    if validator:
        result = validator(result)

    retailer_label = _RETAILER_LABELS.get(detected, detected.value.title())

    finding_counts = {
        "total": len(result.findings),
        "structural": len(result.structural_findings),
        "field": len(result.field_findings),
        "retailer": len(result.retailer_findings),
    }

    return templates.TemplateResponse(
        request, "partials/validation_results.html", {
            "result": result,
            "retailer_label": retailer_label,
            "finding_counts": finding_counts,
            "edi_content": content,
            "retailer_value": detected.value,
        }
    )


@app.post("/export/validation-pdf")
def export_validation_pdf_endpoint(
    edi_text: str = Form(""),
    retailer: str = Form("auto"),
):
    result, retailer_label, detected, error = _validate_856_or_error(edi_text, retailer)
    if error:
        return error

    pdf_bytes = export_validation_pdf(result, retailer_label)

    shipment_id = _safe_filename(result.bsn_data.get("shipment_id", ""))
    filename = f"856_validation_{shipment_id}.pdf" if shipment_id else "856_validation.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
