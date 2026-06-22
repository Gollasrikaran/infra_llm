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
# from station_extractor import extract_station_from_image  # commented out — using page numbers only

# need the parent dir on the path so we can pull in agent.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from agent import extract_image_data_from_bytes, extract_station_only_from_bytes  # noqa: E402
from shoelace_calculator import calculate_cross_section_area  # noqa: E402
from cross_section_colorizer import colorize_cross_section  # noqa: E402

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

# Colored page images stored in memory, keyed by file_id -> {page_num: bytes}
colored_cache: dict[str, dict[int, bytes]] = {}


# --- helpers ---


def enrich_with_shoelace(parsed: dict) -> dict:
    """
    Post-process Gemini JSON: for every intersection whose area_calculation
    contains a 'vertices' list, compute total_area_sqft via the Shoelace
    formula and write it back into the dict.

    This keeps all arithmetic deterministic and removes the risk of the LLM
    making calculation errors (e.g. misreading a coordinate then computing
    a wildly wrong area with the trapezoidal approximation).
    """
    for region in parsed.get("intersections", []):
        ac = region.get("area_calculation", {})
        vertices = ac.get("vertices", [])
        if vertices:
            try:
                coords = [(float(v["x"]), float(v["elevation"])) for v in vertices]
                ac["total_area_sqft"] = calculate_cross_section_area(coords)
            except (KeyError, TypeError, ValueError):
                # Leave total_area_sqft as-is if vertices are malformed
                pass
    return parsed

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
    pages: list[dict] = []


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
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    pdf_bytes = await file.read()

    try:
        total_pages = count_pages(pdf_bytes)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid PDF: {str(e)}")

    file_id = str(uuid.uuid4())
    pdf_cache[file_id] = pdf_bytes

    # Step 1: Render each page and build page list (page numbers only)
    pages_info = []
    rendered_pages: dict[int, bytes] = {}  # cache raw renders for coloring step
    for i in range(total_pages):
        try:
            img_bytes = render_page_png(pdf_bytes, i)
            rendered_pages[i] = img_bytes
        except Exception:
            pass
        # Station extraction commented out — using page numbers only
        # station = extract_station_from_image(img_bytes)
        pages_info.append({"page_num": i + 1})

    # Step 2: Run OpenCV cross-section coloring on each page
    colored_cache[file_id] = {}
    for i in range(total_pages):
        try:
            raw_bytes = rendered_pages.get(i) or render_page_png(pdf_bytes, i)
            colored_bytes = colorize_cross_section(raw_bytes)
            colored_cache[file_id][i + 1] = colored_bytes
        except Exception:
            # If coloring fails, fall back to the raw image
            colored_cache[file_id][i + 1] = rendered_pages.get(i) or render_page_png(pdf_bytes, i)

    return UploadResponse(
        file_id=file_id,
        total_pages=total_pages,
        filename=file.filename,
        pages=pages_info,
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


@app.get("/api/pdf/{file_id}/page/{page_num}/colored")
async def get_pdf_page_colored(file_id: str, page_num: int):
    """Serve the pre-colored cross-section image for a page."""
    if file_id not in pdf_cache:
        raise HTTPException(status_code=404, detail="PDF not found. Upload it first.")

    total_pages = count_pages(pdf_cache[file_id])
    if page_num < 1 or page_num > total_pages:
        raise HTTPException(
            status_code=400,
            detail=f"Page {page_num} out of range (1-{total_pages})",
        )

    # Return colored image if available, otherwise fall back to raw render
    file_colors = colored_cache.get(file_id, {})
    if page_num in file_colors:
        return Response(content=file_colors[page_num], media_type="image/png")

    img_bytes = render_page_png(pdf_cache[file_id], page_num - 1)
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

    # Use the pre-colored image for Gemini analysis
    file_colors = colored_cache.get(request.file_id, {})
    if request.page_num in file_colors:
        img_bytes = file_colors[request.page_num]
    else:
        img_bytes = render_page_png(pdf_bytes, request.page_num - 1)

    try:
        raw_result = extract_image_data_from_bytes(img_bytes)
    except Exception as e:
        return AnalysisResponse(success=False, error=f"Gemini API error: {str(e)}")

    parsed = try_parse_json(raw_result)
    if parsed:
        parsed = enrich_with_shoelace(parsed)
        return AnalysisResponse(success=True, data=parsed, raw=raw_result)
    else:
        return AnalysisResponse(
            success=False,
            raw=raw_result,
            error="Could not parse JSON from Gemini response",
        )


@app.post("/api/analyze/pdf-page-station-only", response_model=AnalysisResponse)
async def analyze_pdf_page_station_only(request: AnalyzePageRequest):
    """Render a PDF page then send it to Gemini to extract ONLY the station number."""
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
        raw_result = extract_station_only_from_bytes(img_bytes)
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


@app.post("/api/colorize-image")
async def colorize_image(file: UploadFile = File(...)):
    """Accept an image, run OpenCV coloring, and return the colored PNG."""
    allowed = (".png", ".jpg", ".jpeg")
    if not file.filename.lower().endswith(allowed):
        raise HTTPException(
            status_code=400, detail="Only PNG, JPG, JPEG files are accepted"
        )

    img_bytes = await file.read()

    try:
        colored_bytes = colorize_cross_section(img_bytes)
    except Exception:
        colored_bytes = img_bytes  # fall back to raw if coloring fails

    return Response(content=colored_bytes, media_type="image/png")


@app.post("/api/analyze/image", response_model=AnalysisResponse)
async def analyze_image(file: UploadFile = File(...)):
    """Accept an image file and send it straight to Gemini Vision."""
    allowed = (".png", ".jpg", ".jpeg")
    if not file.filename.lower().endswith(allowed):
        raise HTTPException(
            status_code=400, detail="Only PNG, JPG, JPEG files are accepted"
        )

    img_bytes = await file.read()

    # Colorize the image before sending to Gemini
    try:
        img_bytes = colorize_cross_section(img_bytes)
    except Exception:
        pass  # If coloring fails, send the raw image

    try:
        raw_result = extract_image_data_from_bytes(img_bytes)
    except Exception as e:
        return AnalysisResponse(success=False, error=f"Gemini API error: {str(e)}")

    parsed = try_parse_json(raw_result)
    if parsed:
        parsed = enrich_with_shoelace(parsed)
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
        colored_cache.pop(file_id, None)
        return {"status": "deleted", "file_id": file_id}
    raise HTTPException(status_code=404, detail="PDF not found")
