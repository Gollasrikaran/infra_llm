import os
import io
import base64
import json
import re
import fitz
import pandas as pd
import streamlit as st
from agent import extract_image_data_from_bytes
from dotenv import load_dotenv
from PIL import Image

# =========================
# CONFIG
# =========================
load_dotenv()

st.set_page_config(
    page_title="Cross-Section Analyzer",
    page_icon="🛣️",
    layout="wide"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');

    html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
    .stApp { background: #0f1117; color: #e8eaf0; }

    .hero {
        background: linear-gradient(135deg, #0d1b2a 0%, #1b2d42 100%);
        border: 1px solid #2a3f5a; border-radius: 12px;
        padding: 2rem; margin-bottom: 1.5rem; text-align: center;
    }
    .hero h1 { font-size: 1.8rem; color: #7eb8f7; font-weight: 600; margin: 0 0 0.3rem 0; }
    .hero p  { color: #8899aa; font-size: 0.9rem; margin: 0; }

    .metric-row { display: flex; gap: 1rem; margin-bottom: 1.2rem; }
    .metric-box {
        flex: 1; background: #1a2332; border: 1px solid #2a3f5a;
        border-radius: 8px; padding: 0.8rem 1rem;
    }
    .metric-box .val { font-size: 1.6rem; font-weight: 600; color: #7eb8f7; font-family: 'IBM Plex Mono'; }
    .metric-box .lbl { font-size: 0.75rem; color: #667788; margin-top: 2px; }

    .result-cut  { background: #2a1218; border: 1px solid #e11d48; border-radius: 10px; padding: 1.2rem; margin-top: 1rem; }
    .result-fill { background: #0d2218; border: 1px solid #16a34a; border-radius: 10px; padding: 1.2rem; margin-top: 1rem; }
    .result-unk  { background: #1a1a2e; border: 1px solid #4a5568; border-radius: 10px; padding: 1.2rem; margin-top: 1rem; }

    .result-type { font-size: 2rem; font-weight: 700; font-family: 'IBM Plex Mono'; margin-bottom: 0.5rem; }
    .cut-color  { color: #f87171; }
    .fill-color { color: #4ade80; }

    .info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0.8rem; margin-top: 1rem; }
    .info-item { background: #0f1117; border-radius: 6px; padding: 0.6rem 0.8rem; }
    .info-item .k { font-size: 0.7rem; color: #667788; text-transform: uppercase; letter-spacing: 0.05em; }
    .info-item .v { font-size: 0.9rem; color: #c8d8e8; margin-top: 2px; }

    .section-hdr {
        font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.12em;
        color: #4a6080; font-weight: 600; margin: 1.2rem 0 0.5rem 0;
        border-bottom: 1px solid #1e2d3d; padding-bottom: 4px;
    }

    div[data-testid="stFileUploader"] {
        background: #1a2332; border: 2px dashed #2a4a6a; border-radius: 10px; padding: 0.5rem;
    }
    div[data-testid="stFileUploader"]:hover { border-color: #7eb8f7; }

    .stButton > button {
        background: linear-gradient(135deg, #1d4ed8, #2563eb);
        color: white; border: none; border-radius: 8px;
        padding: 0.6rem 1.5rem; font-weight: 600;
        font-family: 'IBM Plex Sans'; width: 100%; transition: all 0.2s;
    }
    .stButton > button:hover { background: linear-gradient(135deg, #2563eb, #3b82f6); transform: translateY(-1px); }

    .stSelectbox > div > div { background: #1a2332; border-color: #2a3f5a; color: #e8eaf0; }
    .stSpinner > div { border-top-color: #7eb8f7 !important; }
    div[data-testid="stImage"] img { border-radius: 8px; border: 1px solid #2a3f5a; }

    .raw-json {
        background: #0d1117; border: 1px solid #2a3f5a; border-radius: 8px;
        padding: 1rem; font-family: 'IBM Plex Mono'; font-size: 0.8rem;
        color: #8ab4d8; overflow-x: auto; max-height: 300px;
    }
</style>
""", unsafe_allow_html=True)


# =========================
# HELPERS
# =========================

@st.cache_data(show_spinner=False)
def get_page_count(pdf_bytes: bytes) -> int:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    n = len(doc)
    doc.close()
    return n


@st.cache_data(show_spinner=False)
def render_page(pdf_bytes: bytes, page_index: int, dpi: int = 150) -> bytes:
    doc  = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc.load_page(page_index)
    rect = page.rect
    max_px = 3_000_000
    scale  = dpi / 72
    if (rect.width * scale) * (rect.height * scale) > max_px:
        scale = (max_px / (rect.width * rect.height)) ** 0.5
    pix       = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
    img_bytes = pix.tobytes("png")
    doc.close()
    return img_bytes


def parse_result(raw: str) -> dict | None:
    """Safely parse JSON from model response — strips markdown fences if present."""
    try:
        clean = re.sub(r"```(?:json)?|```", "", raw).strip()
        return json.loads(clean)
    except Exception:
        return None


def _safe_width(lx, rx) -> str:
    """Return formatted width string or dash if values aren't numeric."""
    try:
        return f"{abs(float(rx) - float(lx)):.1f} ft"
    except (TypeError, ValueError):
        return "—"


def render_result(data: dict):
    """Render multi-intersection result — one styled card per region."""

    # ── Global header ────────────────────────────────────────────────────────
    station  = data.get("station")               or "—"
    slopes   = data.get("slopes")                or "—"
    extent   = data.get("proposed_grade_extent") or "—"
    eg_line  = data.get("existing_ground_line")  or "—"
    n_regions = data.get("total_intersections", 0)

    st.markdown(f"""
    <div style="background:#1a2332;border:1px solid #2a3f5a;border-radius:10px;
                padding:1rem 1.2rem;margin-bottom:1rem;">
        <div style="display:flex;gap:2rem;flex-wrap:wrap;align-items:flex-start;">
            <div>
                <div class="k" style="font-size:0.7rem;color:#667788;text-transform:uppercase">Station</div>
                <div style="font-size:1.4rem;font-weight:600;color:#7eb8f7;font-family:'IBM Plex Mono'">{station}</div>
            </div>
            <div>
                <div class="k" style="font-size:0.7rem;color:#667788;text-transform:uppercase">Slopes</div>
                <div style="color:#c8d8e8;margin-top:4px">{slopes}</div>
            </div>
            <div>
                <div class="k" style="font-size:0.7rem;color:#667788;text-transform:uppercase">Proposed Grade Extent</div>
                <div style="color:#c8d8e8;margin-top:4px">{extent}</div>
            </div>
            <div>
                <div class="k" style="font-size:0.7rem;color:#667788;text-transform:uppercase">Regions Found</div>
                <div style="font-size:1.4rem;font-weight:600;color:#7eb8f7;font-family:'IBM Plex Mono'">{n_regions}</div>
            </div>
        </div>
        <div style="margin-top:0.8rem;padding-top:0.8rem;border-top:1px solid #1e2d3d">
            <span style="font-size:0.7rem;color:#667788;text-transform:uppercase">Existing Ground — </span>
            <span style="font-size:0.85rem;color:#c8d8e8">{eg_line}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── One card per intersection region ─────────────────────────────────────
    intersections = data.get("intersections", [])

    for region in intersections:
        rid        = region.get("id", "?")
        rtype      = region.get("type", "UNKNOWN").upper()
        lcp        = region.get("left_catch_point",  {})
        rcp        = region.get("right_catch_point", {})
        rnotes     = region.get("notes", "")
        area_calc  = region.get("area_calculation", {})
        total_area = area_calc.get("total_area_sqft")
        samples    = area_calc.get("sample_points", [])

        lx, lelv = lcp.get("x", "—"), lcp.get("elevation", "—")
        rx, relv = rcp.get("x", "—"), rcp.get("elevation", "—")

        if rtype == "CUT":
            card_cls, color_cls, icon = "result-cut",  "cut-color",  "🔴"
            desc = "Proposed grade is BELOW existing ground — excavation needed"
        elif rtype == "FILL":
            card_cls, color_cls, icon = "result-fill", "fill-color", "🟢"
            desc = "Proposed grade is ABOVE existing ground — fill material needed"
        else:
            card_cls, color_cls, icon = "result-unk",  "",           "⚪"
            desc = "Undetermined"

        st.markdown(f"""
        <div class="{card_cls}">
            <div style="font-size:0.68rem;color:#667788;text-transform:uppercase;
                        letter-spacing:0.1em;margin-bottom:0.3rem">
                Intersection {rid}
            </div>
            <div class="result-type {color_cls}">{icon} {rtype}</div>
            <div style="color:#8899aa;font-size:0.85rem;margin-bottom:0.8rem">{desc}</div>
            <div class="info-grid">
                <div class="info-item">
                    <div class="k">Left Catch Point</div>
                    <div class="v">x = {lx} ft &nbsp;|&nbsp; elev = {lelv} ft</div>
                </div>
                <div class="info-item">
                    <div class="k">Right Catch Point</div>
                    <div class="v">x = {rx} ft &nbsp;|&nbsp; elev = {relv} ft</div>
                </div>
                <div class="info-item">
                    <div class="k">Width</div>
                    <div class="v">{_safe_width(lx, rx)}</div>
                </div>
                <div class="info-item">
                    <div class="k">Area</div>
                    <div class="v" style="font-size:1.1rem;color:#7eb8f7;font-family:'IBM Plex Mono'">
                        {f"{total_area:,.1f} sq ft" if total_area is not None else "—"}
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Collapsible sample points table
        if samples:
            df = pd.DataFrame(samples).rename(columns={
                "x":             "Offset (ft)",
                "existing_elev": "Existing Elev (ft)",
                "proposed_elev": "Proposed Elev (ft)",
                "gap":           "Gap (ft)"
            })
            with st.expander(f"📊 Intersection {rid} — Trapezoidal Sample Points"):
                st.dataframe(df, use_container_width=True, hide_index=True)

        if rnotes:
            st.markdown(
                f'<div class="info-item" style="margin-top:0.5rem">'
                f'<div class="k">Notes</div><div class="v">{rnotes}</div></div>',
                unsafe_allow_html=True
            )

    # ── Summary totals ────────────────────────────────────────────────────────
    if intersections:
        cut_total = sum(
            r.get("area_calculation", {}).get("total_area_sqft", 0) or 0
            for r in intersections if r.get("type", "").upper() == "CUT"
        )
        fill_total = sum(
            r.get("area_calculation", {}).get("total_area_sqft", 0) or 0
            for r in intersections if r.get("type", "").upper() == "FILL"
        )
        net = cut_total - fill_total
        net_color = "#f87171" if net > 0 else "#4ade80" if net < 0 else "#7eb8f7"

        st.markdown(f"""
        <div style="background:#1a2332;border:1px solid #2a3f5a;border-radius:10px;
                    padding:1rem 1.2rem;margin-top:1.5rem;">
            <div class="section-hdr" style="margin-top:0">Summary</div>
            <div style="display:flex;gap:2.5rem;flex-wrap:wrap;margin-top:0.6rem">
                <div>
                    <div style="font-size:0.7rem;color:#667788;text-transform:uppercase">Total CUT</div>
                    <div style="font-size:1.4rem;font-weight:600;color:#f87171;font-family:'IBM Plex Mono'">
                        {cut_total:,.1f} sq ft
                    </div>
                </div>
                <div>
                    <div style="font-size:0.7rem;color:#667788;text-transform:uppercase">Total FILL</div>
                    <div style="font-size:1.4rem;font-weight:600;color:#4ade80;font-family:'IBM Plex Mono'">
                        {fill_total:,.1f} sq ft
                    </div>
                </div>
                <div>
                    <div style="font-size:0.7rem;color:#667788;text-transform:uppercase">Net (CUT − FILL)</div>
                    <div style="font-size:1.4rem;font-weight:600;color:{net_color};font-family:'IBM Plex Mono'">
                        {net:+,.1f} sq ft
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── Reasoning ─────────────────────────────────────────────────────────────
    if data.get("reasoning"):
        st.markdown('<div class="section-hdr">Reasoning</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="info-item"><div class="v">{data["reasoning"]}</div></div>',
            unsafe_allow_html=True
        )

    # ── Overall notes ──────────────────────────────────────────────────────────
    if data.get("notes"):
        st.markdown('<div class="section-hdr">Notes</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="info-item"><div class="v">{data["notes"]}</div></div>',
            unsafe_allow_html=True
        )

    # ── Raw JSON ───────────────────────────────────────────────────────────────
    with st.expander("Raw JSON"):
        st.markdown(
            f'<div class="raw-json">{json.dumps(data, indent=2)}</div>',
            unsafe_allow_html=True
        )


# =========================
# UI
# =========================

st.markdown("""
<div class="hero">
    <h1>🛣️ Highway Cross-Section Analyzer</h1>
    <p>Upload a PDF → Select a page → Analyze with Gemini Vision</p>
</div>
""", unsafe_allow_html=True)

uploaded_pdf = st.file_uploader("Upload PDF", type=["pdf"], label_visibility="collapsed")

if not uploaded_pdf:
    st.markdown("""
    <div style="text-align:center;padding:3rem;color:#4a6080;">
        <div style="font-size:3rem">📄</div>
        <p style="margin-top:0.8rem">Drop your highway engineering PDF above to get started</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

pdf_bytes = uploaded_pdf.read()

with st.spinner("Reading PDF..."):
    total_pages = get_page_count(pdf_bytes)

st.markdown(f"""
<div class="metric-row">
    <div class="metric-box"><div class="val">{total_pages}</div><div class="lbl">Total Pages</div></div>
    <div class="metric-box"><div class="val">{total_pages * 5}</div><div class="lbl">Est. Cross-Sections</div></div>
    <div class="metric-box"><div class="val">Gemini</div><div class="lbl">Vision Model</div></div>
</div>
""", unsafe_allow_html=True)

col_left, col_right = st.columns([1, 2])

with col_left:
    st.markdown('<div class="section-hdr">Page Selection</div>', unsafe_allow_html=True)

    selected_page = st.selectbox(
        "Page",
        options=list(range(1, total_pages + 1)),
        format_func=lambda x: f"Page {x}",
        label_visibility="collapsed"
    )
    page_index = selected_page - 1

    with st.spinner(f"Rendering page {selected_page}..."):
        img_bytes = render_page(pdf_bytes, page_index, dpi=150)

    image = Image.open(io.BytesIO(img_bytes))
    st.image(image, caption=f"Page {selected_page}", use_container_width=True)

    analyze_clicked = st.button("🔍 Analyze This Page", use_container_width=True)

with col_right:
    st.markdown('<div class="section-hdr">Analysis Result</div>', unsafe_allow_html=True)

    if analyze_clicked:
        with st.spinner("Sending to Gemini Vision..."):
            raw_result = extract_image_data_from_bytes(img_bytes)

        parsed = parse_result(raw_result)

        if parsed:
            render_result(parsed)
        else:
            st.warning("Could not parse JSON from model response.")
            st.code(raw_result, language="json")
    else:
        st.markdown("""
        <div style="text-align:center;padding:4rem 2rem;color:#4a6080;
                    border:1px dashed #2a3f5a;border-radius:10px;">
            <div style="font-size:2.5rem">📊</div>
            <p style="margin-top:0.8rem;font-size:0.9rem">
                Select a page and click<br>
                <strong style="color:#7eb8f7">Analyze This Page</strong>
            </p>
        </div>
        """, unsafe_allow_html=True)