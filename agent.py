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
- DOTTED/DASHED line = Existing Ground (natural surface)
- SOLID line (with slope labels like 2:1, 3:1, 6.0%) = Proposed Grade (design template)

STEP 2 — DETERMINE CUT OR FILL:
Look at the centerline (x = 0):
  • DOTTED above SOLID → CUT (excavation needed)
  • SOLID above DOTTED → FILL (embankment needed)

STEP 3 — FIND INTERSECTION POINTS:
Identify every point where the proposed grade line crosses the existing ground line.
These are the "catch points" — read their (x, elevation) coordinates from the grid.
Example: left catch point at x = -28 ft, right catch point at x = +32 ft.

STEP 4 — CALCULATE AREA using the TRAPEZOIDAL METHOD:
Between the two catch points, sample the vertical distance (gap) between the two lines
at regular horizontal intervals (every 5 or 10 feet). 

Area ≈ Σ [ (gap_i + gap_{i+1}) / 2 × Δx ]

Where:
  - gap_i = |proposed_elevation_i − existing_elevation_i| at station x_i
  - Δx = horizontal distance between sample points (in feet)

Read as many sample points as you can from the drawing for accuracy.
The final area should be in SQUARE FEET (ft²).

Also extract:
  - Station number (e.g. 20+50)
  - Key elevations (e.g. centerline existing, centerline proposed, catch point elevations)
  - Slope ratios (e.g. 2:1, 3:1, 6.0%)
  - Left and right catch point offsets (feet from centerline)

Respond ONLY with valid JSON — no markdown, no explanation, no code fences:
{
  "type": "CUT" or "FILL",
  "station": "station number if visible, else null",
  "elevation": "key elevations as a readable string",
  "slopes": "all slope ratios visible",
  "intersection_points": "left catch point: x=? ft, elev=?; right catch point: x=? ft, elev=?",
  "existing_ground_line": "dotted line description",
  "proposed_grade_line": "solid line description",
  "area_calculation": {
    "method": "trapezoidal",
    "sample_points": [
      {"x": 0, "existing_elev": 0, "proposed_elev": 0, "gap": 0}
    ],
    "total_area_sqft": 0
  },
  "Area": "numeric value followed by sq ft, e.g. 1234.5 sq ft",
  "reasoning": "brief explanation of CUT/FILL decision and area calculation approach",
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