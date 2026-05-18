"""
image_analyzer.py
-----------------
Standalone Streamlit page for uploading a PNG/JPG image directly
and running the OpenCV area calculation on it.

Run with:
    streamlit run image_analyzer.py
"""

import io
import streamlit as st
from PIL import Image

from area_calculator import crop_to_drawing, calculate_area, generate_debug_image

st.set_page_config(page_title="Image Area Analyzer", page_icon="📐", layout="wide")
st.cache_data.clear()

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');
    html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
    .stApp { background: #0f1117; color: #e8eaf0; }
    .hero { background: linear-gradient(135deg,#0d1b2a,#1b2d42); border:1px solid #2a3f5a;
            border-radius:12px; padding:2rem; margin-bottom:1.5rem; text-align:center; }
    .hero h1 { font-size:1.8rem; color:#7eb8f7; font-weight:600; margin:0 0 .3rem; }
    .hero p  { color:#8899aa; font-size:.9rem; margin:0; }
    .section-hdr { font-size:.7rem; text-transform:uppercase; letter-spacing:.12em;
                   color:#4a6080; font-weight:600; margin:1.2rem 0 .5rem;
                   border-bottom:1px solid #1e2d3d; padding-bottom:4px; }
    .opencv-box { background:#0d1f2d; border:1px solid #1e4d6b; border-radius:10px;
                  padding:1.2rem; margin-top:1rem; }
    .opencv-box .title { font-size:.75rem; text-transform:uppercase; letter-spacing:.1em;
                         color:#4a90c4; font-weight:600; margin-bottom:.8rem; }
    .result-cut  { background:#2a1218; border:1px solid #e11d48; border-radius:10px; padding:1.2rem; margin-top:1rem; }
    .result-fill { background:#0d2218; border:1px solid #16a34a; border-radius:10px; padding:1.2rem; margin-top:1rem; }
    .result-unk  { background:#1a1a2e; border:1px solid #4a5568; border-radius:10px; padding:1.2rem; margin-top:1rem; }
    .result-type { font-size:2rem; font-weight:700; font-family:'IBM Plex Mono'; margin-bottom:.5rem; }
    .cut-color  { color:#f87171; }
    .fill-color { color:#4ade80; }
    .info-grid { display:grid; grid-template-columns:1fr 1fr; gap:.8rem; margin-top:1rem; }
    .info-item { background:#0f1117; border-radius:6px; padding:.6rem .8rem; }
    .info-item .k { font-size:.7rem; color:#667788; text-transform:uppercase; letter-spacing:.05em; }
    .info-item .v { font-size:.9rem; color:#c8d8e8; margin-top:2px; }
    div[data-testid="stFileUploader"] { background:#1a2332; border:2px dashed #2a4a6a; border-radius:10px; padding:.5rem; }
    .stButton>button { background:linear-gradient(135deg,#1d4ed8,#2563eb); color:white; border:none;
                       border-radius:8px; padding:.6rem 1.5rem; font-weight:600; width:100%; transition:all .2s; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
    <h1>📐 Image Area Analyzer</h1>
    <p>Upload a cross-section image → Analyze with OpenCV</p>
</div>
""", unsafe_allow_html=True)

# ── Upload ────────────────────────────────────────────────────────────────────
uploaded_img = st.file_uploader(
    "Upload Image", type=["png", "jpg", "jpeg"], label_visibility="collapsed"
)

if not uploaded_img:
    st.markdown("""
    <div style="text-align:center;padding:3rem;color:#4a6080;">
        <div style="font-size:3rem">🖼️</div>
        <p style="margin-top:.8rem">Drop a PNG or JPG cross-section image above</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

img_bytes = uploaded_img.read()

col_left, col_right = st.columns([1, 2])

with col_left:
    st.markdown('<div class="section-hdr">Uploaded Image</div>', unsafe_allow_html=True)
    image = Image.open(io.BytesIO(img_bytes))
    st.image(image, caption=uploaded_img.name, use_container_width=True)
    analyze_clicked = st.button("🔍 Analyze Image", use_container_width=True)

with col_right:
    st.markdown('<div class="section-hdr">Analysis Result</div>', unsafe_allow_html=True)

    if analyze_clicked:

        with st.spinner("📐 Measuring pixel area with OpenCV..."):
            img_bytes_cropped = crop_to_drawing(img_bytes)
            cv_result         = calculate_area(img_bytes_cropped)
            debug_png         = generate_debug_image(img_bytes_cropped)

        # ── Result display ────────────────────────────────────────────────────
        if cv_result.get("error"):
            st.error(f"OpenCV Error: {cv_result['error']}")
        else:
            grid_px    = cv_result.get("grid_px", "—")
            px_sqft    = cv_result.get("px_per_sqft", "—")
            regions    = cv_result.get("regions", [])
            cut_total  = cv_result.get("total_cut_sqft",  0)
            fill_total = cv_result.get("total_fill_sqft", 0)
            net        = cv_result.get("net_sqft", 0)
            net_color  = "#f87171" if net > 0 else "#4ade80" if net < 0 else "#7eb8f7"

            st.markdown(f"""
            <div class="opencv-box">
                <div class="title">📐 OpenCV Pixel-Based Area Measurement</div>
                <div style="display:flex;gap:2rem;flex-wrap:wrap;margin-bottom:1rem">
                    <div>
                        <div class="k" style="font-size:.7rem;color:#667788;text-transform:uppercase">Grid Square</div>
                        <div style="color:#7eb8f7;font-family:'IBM Plex Mono';font-size:1rem">
                            {grid_px}px × {grid_px}px = 100 sq ft
                        </div>
                    </div>
                    <div>
                        <div class="k" style="font-size:.7rem;color:#667788;text-transform:uppercase">Scale</div>
                        <div style="color:#c8d8e8;font-family:'IBM Plex Mono';font-size:1rem">
                            {px_sqft} px² = 1 sq ft
                        </div>
                    </div>
                    <div>
                        <div class="k" style="font-size:.7rem;color:#667788;text-transform:uppercase">Regions Detected</div>
                        <div style="color:#7eb8f7;font-family:'IBM Plex Mono';font-size:1rem">{len(regions)}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            for i, r in enumerate(regions, 1):
                rtype    = r.get("type", "UNKNOWN")
                area     = r.get("area_sqft", 0)
                width_px = r.get("width_px", 0)
                if rtype == "CUT":
                    card_cls, color_cls, icon = "result-cut",  "cut-color",  "🔴"
                elif rtype == "FILL":
                    card_cls, color_cls, icon = "result-fill", "fill-color", "🟢"
                else:
                    card_cls, color_cls, icon = "result-unk",  "",           "⚪"

                st.markdown(f"""
                <div class="{card_cls}">
                    <div style="font-size:.68rem;color:#667788;text-transform:uppercase;margin-bottom:.3rem">Region {i}</div>
                    <div class="result-type {color_cls}">{icon} {rtype}</div>
                    <div class="info-grid">
                        <div class="info-item"><div class="k">Width</div><div class="v">{width_px} px</div></div>
                        <div class="info-item">
                            <div class="k">Area (OpenCV)</div>
                            <div class="v" style="font-size:1.1rem;color:#7eb8f7;font-family:'IBM Plex Mono'">{area:,.2f} sq ft</div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown(f"""
            <div style="background:#1a2332;border:1px solid #2a3f5a;border-radius:10px;padding:1rem 1.2rem;margin-top:1.5rem;">
                <div class="section-hdr" style="margin-top:0">OpenCV Summary</div>
                <div style="display:flex;gap:2.5rem;flex-wrap:wrap;margin-top:.6rem">
                    <div>
                        <div style="font-size:.7rem;color:#667788;text-transform:uppercase">Total CUT</div>
                        <div style="font-size:1.4rem;font-weight:600;color:#f87171;font-family:'IBM Plex Mono'">{cut_total:,.2f} sq ft</div>
                    </div>
                    <div>
                        <div style="font-size:.7rem;color:#667788;text-transform:uppercase">Total FILL</div>
                        <div style="font-size:1.4rem;font-weight:600;color:#4ade80;font-family:'IBM Plex Mono'">{fill_total:,.2f} sq ft</div>
                    </div>
                    <div>
                        <div style="font-size:.7rem;color:#667788;text-transform:uppercase">Net (CUT − FILL)</div>
                        <div style="font-size:1.4rem;font-weight:600;color:{net_color};font-family:'IBM Plex Mono'">{net:+,.2f} sq ft</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # ── Debug visualization ───────────────────────────────────────────────
        st.markdown('<div class="section-hdr">🔍 OpenCV Detection Visualization</div>',
                    unsafe_allow_html=True)
        st.image(debug_png,
                 caption="Green=grid lines | Red=line1 | Orange=line2 | Cyan=enclosed area | Yellow=1 grid square(100 sqft)",
                 use_container_width=True)

    else:
        st.markdown("""
        <div style="text-align:center;padding:4rem 2rem;color:#4a6080;
                    border:1px dashed #2a3f5a;border-radius:10px;">
            <div style="font-size:2.5rem">📊</div>
            <p style="margin-top:.8rem;font-size:.9rem">
                Upload an image and click<br>
                <strong style="color:#7eb8f7">Analyze Image</strong>
            </p>
        </div>
        """, unsafe_allow_html=True)
