"""
FastAPI backend for the Highway Cross-Section Analyzer.
Handles PDF uploads, page rendering, and Gemini Vision analysis.
"""

import os
import sys
import re
import json
import uuid

import fitz  # PyMuPDF
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from dotenv import load_dotenv

# need the parent dir on the path so we can pull in agent.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from agent import extract_image_data_from_bytes  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

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

# PDF bytes stored in memory, keyed by file_id
pdf_cache: dict[str, bytes] = {}


# --- helpers ---

def count_pages(pdf_bytes: bytes) -> int:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    n = len(doc)
    doc.close()
    return n


def render_page_png(pdf_bytes: bytes, page_index: int, dpi: int = 150) -> bytes:
    """Renders a single page to PNG bytes. Caps resolution to ~3M pixels."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc.load_page(page_index)
    rect = page.rect
    scale = dpi / 72
    # don't blow up memory on huge pages
    if (rect.width * scale) * (rect.height * scale) > 3_000_000:
        scale = (3_000_000 / (rect.width * rect.height)) ** 0.5
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
    img_bytes = pix.tobytes("png")
    doc.close()
    return img_bytes


def try_parse_json(raw: str) -> dict | None:
    """Try to extract JSON from a Gemini response (strips markdown fences)."""
    try:
        clean = re.sub(r"```(?:json)?|```", "", raw).strip()
        return json.loads(clean)
    except Exception:
        return None


# --- request/response models ---

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


# --- endpoints ---

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "cross-section-analyzer"}


@app.post("/api/upload-pdf", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...)):
    """Upload a PDF, store it in memory, return a file_id + page count."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    pdf_bytes = await file.read()

    try:
        total_pages = count_pages(pdf_bytes)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid PDF: {str(e)}")

    file_id = str(uuid.uuid4())
    pdf_cache[file_id] = pdf_bytes

    return UploadResponse(
        file_id=file_id,
        total_pages=total_pages,
        filename=file.filename,
    )


@app.get("/api/pdf/{file_id}/page/{page_num}")
async def get_pdf_page(file_id: str, page_num: int):
    """Render one page of a previously-uploaded PDF as PNG."""
    if file_id not in pdf_cache:
        raise HTTPException(status_code=404, detail="PDF not found. Upload it first.")

    pdf_bytes = pdf_cache[file_id]
    total_pages = count_pages(pdf_bytes)

    if page_num < 1 or page_num > total_pages:
        raise HTTPException(
            status_code=400,
            detail=f"Page {page_num} out of range (1-{total_pages})",
        )

    img_bytes = render_page_png(pdf_bytes, page_num - 1)
    return Response(content=img_bytes, media_type="image/png")


@app.post("/api/analyze/pdf-page", response_model=AnalysisResponse)
async def analyze_pdf_page(request: AnalyzePageRequest):
    """Render a PDF page then send it to Gemini for cross-section analysis."""
    if request.file_id not in pdf_cache:
        raise HTTPException(status_code=404, detail="PDF not found. Upload it first.")

    pdf_bytes = pdf_cache[request.file_id]
    total_pages = count_pages(pdf_bytes)

    if request.page_num < 1 or request.page_num > total_pages:
        raise HTTPException(
            status_code=400,
            detail=f"Page {request.page_num} out of range (1-{total_pages})",
        )

    img_bytes = render_page_png(pdf_bytes, request.page_num - 1)

    try:
        raw_result = extract_image_data_from_bytes(img_bytes)
    except Exception as e:
        return AnalysisResponse(success=False, error=f"Gemini API error: {str(e)}")

    parsed = try_parse_json(raw_result)
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
    """Accept an image file and send it straight to Gemini Vision."""
    allowed = (".png", ".jpg", ".jpeg")
    if not file.filename.lower().endswith(allowed):
        raise HTTPException(
            status_code=400, detail="Only PNG, JPG, JPEG files are accepted"
        )

    img_bytes = await file.read()

    try:
        raw_result = extract_image_data_from_bytes(img_bytes)
    except Exception as e:
        return AnalysisResponse(success=False, error=f"Gemini API error: {str(e)}")

    parsed = try_parse_json(raw_result)
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
    """Remove a PDF from the in-memory cache."""
    if file_id in pdf_cache:
        del pdf_cache[file_id]
        return {"status": "deleted", "file_id": file_id}
    raise HTTPException(status_code=404, detail="PDF not found")
