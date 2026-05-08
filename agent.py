import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from PIL import Image
import base64

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
PRIMARY_MODEL = os.getenv("GEMINI_MODEL")

def _extract_image_text(img_bytes: bytes, filename: str) -> str:
    """Extract text and data from image using Google Gemini."""
    llm = ChatGoogleGenerativeAI(
        model=PRIMARY_MODEL,
        temperature=0.2,          # Lower temp = more precise/deterministic for engineering data
        google_api_key=GOOGLE_API_KEY
    )

    prompt = """You are an expert highway engineer analyzing a cross-section drawing.

GRID SCALE (read from the axis labels on the drawing):
- X-axis (horizontal): Each labeled interval = 10 feet (offset from centerline)
- Y-axis (vertical): Each labeled interval = 10 feet (elevation)
- The X-axis zero is at the centerline; negative values are to the LEFT, positive to the RIGHT.

STEP 1 — IDENTIFY LINE TYPES:
- DOTTED/DASHED line = Existing Ground (natural surface). This line spans the full drawing width.
- SOLID line (with slope labels like 2:1, 3:1, 6.0%, 8.0%) = Proposed Grade (design template).
  ⚠️ The SOLID proposed grade line has a LIMITED horizontal extent — it does NOT span the full drawing.
  It starts at the LEFT catch point and ends at the RIGHT catch point where it meets the dashed line.
  DO NOT assume the proposed grade continues beyond where the solid line visually ends.

STEP 2 — DETERMINE CUT OR FILL:
Look at the centerline (x = 0). Compare which line is higher AT THE CENTERLINE ONLY:
  • DOTTED above SOLID at x=0 → CUT (excavation needed)
  • SOLID above DOTTED at x=0 → FILL (embankment needed)
  • If the solid line does not reach x=0, check the deepest point of the solid line instead.

STEP 3 — FIND CATCH POINTS (CRITICAL STEP):
The catch points are where the SOLID proposed grade line physically meets the DASHED existing ground line.
These are the ONLY boundaries for area calculation.

  ✅ LEFT catch point  = leftmost point where solid line touches/crosses dashed line
  ✅ RIGHT catch point = rightmost point where solid line touches/crosses dashed line

  ⚠️ CRITICAL RULES:
  - If the solid line ends before reaching the right edge of the drawing, the right catch point
    is where the solid line ENDS (meets the dashed line), NOT the drawing edge.
  - DO NOT extend the proposed grade line beyond where it visually ends in the drawing.
  - Only include x-offsets between the left and right catch points in your sample_points.
  - Sample points outside the catch points must NOT be included — there is no cross-section area there.

STEP 4 — CALCULATE AREA using the TRAPEZOIDAL METHOD:
Sample the vertical gap between the two lines ONLY between the two catch points, every 5 or 10 feet.

Area ≈ Σ [ (gap_i + gap_{i+1}) / 2 × Δx ]

Where:
  - gap_i = |proposed_elevation_i − existing_elevation_i| at offset x_i
  - Δx = horizontal spacing between samples (feet)
  - gap at each catch point = 0.0 (lines meet there)
  - The final area is in SQUARE FEET (ft²)

Also extract:
  - Station number (e.g. 13+00, 20+50)
  - Key elevations (centerline existing, centerline proposed, catch point elevations)
  - Slope ratios visible on the solid line (e.g. 2:1, 4:1, 8.0%)
  - Left and right catch point x-offsets

Respond ONLY with valid JSON — no markdown, no explanation, no code fences:
{
  "type": "CUT" or "FILL",
  "station": "station number if visible, else null",
  "elevation": "key elevations as a readable string",
  "slopes": "all slope ratios visible on the solid proposed grade line",
  "intersection_points": "left catch point: x=? ft, elev=?; right catch point: x=? ft, elev=?",
  "existing_ground_line": "brief description",
  "proposed_grade_line": "brief description including its x-extent, e.g. solid line from x=-50 to x=-10",
  "area_calculation": {
    "method": "trapezoidal",
    "left_catch_point_x": 0,
    "right_catch_point_x": 0,
    "sample_points": [
      {"x": 0, "existing_elev": 0, "proposed_elev": 0, "gap": 0}
    ],
    "total_area_sqft": 0
  },
  "Area": "numeric value followed by sq ft, e.g. 123.4 sq ft",
  "reasoning": "explain where the solid line starts and ends, why those are the catch points, and how area was computed",
  "notes": "any other observations"
}"""

    # Convert image bytes to base64 for LangChain
    image_base64 = base64.b64encode(img_bytes).decode('utf-8')

    try:
        response = llm.invoke([
            {"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}}
            ]}
        ])
        return response.content
    except Exception as e:
        return f"Error processing image: {str(e)}"


def extract_image_data(image_path: str) -> str:
    """Main function to extract data from an image file."""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")

    try:
        with open(image_path, 'rb') as image_file:
            img_bytes = image_file.read()

        filename = os.path.basename(image_path)
        extracted_data = _extract_image_text(img_bytes, filename)
        return extracted_data

    except Exception as e:
        raise Exception(f"Failed to extract data from image: {str(e)}")


def extract_image_data_from_bytes(img_bytes: bytes) -> str:
    """For Streamlit usage when image is already in memory."""
    return _extract_image_text(img_bytes, filename="image.png")