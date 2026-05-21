"""
FastAPI backend for the Highway Cross-Section Analyzer.
Replaces the Streamlit server with REST endpoints.
"""

import os
import sys
import re
import io
import json
import uuid

import fitz  # PyMuPDF
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from dotenv import load_dotenv

# ── Add parent dir to path so we can import agent.py, etc. ────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from agent import extract_image_data_from_bytes  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# ══════════════════════════════════════════════════════════════════════════════
# APP SETUP
# ══════════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="Cross-Section Analyzer API",
    description="Highway cross-section analysis with Gemini Vision",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory PDF storage ─────────────────────────────────────────────────────
_pdf_store: dict[str, bytes] = {}


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _get_page_count(pdf_bytes: bytes) -> int:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    n = len(doc)
    doc.close()
    return n


def _render_page(pdf_bytes: bytes, page_index: int, dpi: int = 150) -> bytes:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc.load_page(page_index)
    rect = page.rect
    scale = dpi / 72
    if (rect.width * scale) * (rect.height * scale) > 3_000_000:
        scale = (3_000_000 / (rect.width * rect.height)) ** 0.5
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
    img_bytes = pix.tobytes("png")
    doc.close()
    return img_bytes


def _parse_result(raw: str) -> dict | None:
    """Strip markdown fences and parse JSON from Gemini response."""
    try:
        clean = re.sub(r"```(?:json)?|```", "", raw).strip()
        return json.loads(clean)
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# MODELS
# ══════════════════════════════════════════════════════════════════════════════

class UploadResponse(BaseModel):
    file_id: str
    total_pages: int
    filename: str


class AnalyzePageRequest(BaseModel):
    file_id: str
    page_num: int


class AnalysisResponse(BaseModel):
    success: bool
    data: dict | None = None
    raw: str | None = None
    error: str | None = None


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "cross-section-analyzer"}


@app.post("/api/upload-pdf", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...)):
    """Upload a PDF and store it in memory. Returns file_id and page count."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    pdf_bytes = await file.read()

    try:
        total_pages = _get_page_count(pdf_bytes)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid PDF: {str(e)}")

    file_id = str(uuid.uuid4())
    _pdf_store[file_id] = pdf_bytes

    return UploadResponse(
        file_id=file_id,
        total_pages=total_pages,
        filename=file.filename,
    )


@app.get("/api/pdf/{file_id}/page/{page_num}")
async def get_pdf_page(file_id: str, page_num: int):
    """Render a specific PDF page as a PNG image."""
    if file_id not in _pdf_store:
        raise HTTPException(status_code=404, detail="PDF not found. Upload it first.")

    pdf_bytes = _pdf_store[file_id]
    total_pages = _get_page_count(pdf_bytes)

    if page_num < 1 or page_num > total_pages:
        raise HTTPException(
            status_code=400,
            detail=f"Page {page_num} out of range (1-{total_pages})",
        )

    img_bytes = _render_page(pdf_bytes, page_num - 1)
    return Response(content=img_bytes, media_type="image/png")


@app.post("/api/analyze/pdf-page", response_model=AnalysisResponse)
async def analyze_pdf_page(request: AnalyzePageRequest):
    """Render a PDF page and send it to Gemini Vision for analysis."""
    if request.file_id not in _pdf_store:
        raise HTTPException(status_code=404, detail="PDF not found. Upload it first.")

    pdf_bytes = _pdf_store[request.file_id]
    total_pages = _get_page_count(pdf_bytes)

    if request.page_num < 1 or request.page_num > total_pages:
        raise HTTPException(
            status_code=400,
            detail=f"Page {request.page_num} out of range (1-{total_pages})",
        )

    img_bytes = _render_page(pdf_bytes, request.page_num - 1)

    try:
        raw_result = extract_image_data_from_bytes(img_bytes)
    except Exception as e:
        return AnalysisResponse(success=False, error=f"Gemini API error: {str(e)}")

    parsed = _parse_result(raw_result)
    if parsed:
        return AnalysisResponse(success=True, data=parsed, raw=raw_result)
    else:
        return AnalysisResponse(
            success=False,
            raw=raw_result,
            error="Could not parse JSON from Gemini response",
        )


@app.post("/api/analyze/image", response_model=AnalysisResponse)
async def analyze_image(file: UploadFile = File(...)):
    """Accept a PNG/JPG image and send it directly to Gemini Vision."""
    allowed_types = (".png", ".jpg", ".jpeg")
    if not file.filename.lower().endswith(allowed_types):
        raise HTTPException(
            status_code=400, detail="Only PNG, JPG, JPEG files are accepted"
        )

    img_bytes = await file.read()

    try:
        raw_result = extract_image_data_from_bytes(img_bytes)
    except Exception as e:
        return AnalysisResponse(success=False, error=f"Gemini API error: {str(e)}")

    parsed = _parse_result(raw_result)
    if parsed:
        return AnalysisResponse(success=True, data=parsed, raw=raw_result)
    else:
        return AnalysisResponse(
            success=False,
            raw=raw_result,
            error="Could not parse JSON from Gemini response",
        )


@app.delete("/api/pdf/{file_id}")
async def delete_pdf(file_id: str):
    """Remove a PDF from in-memory storage."""
    if file_id in _pdf_store:
        del _pdf_store[file_id]
        return {"status": "deleted", "file_id": file_id}
    raise HTTPException(status_code=404, detail="PDF not found")
