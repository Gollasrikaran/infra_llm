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
        temperature=0.7,
        google_api_key=GOOGLE_API_KEY
    )
    
    prompt = (
        "This is a highway cross-section engineering drawing.\n\n"
 
        "Look at the V-shaped intersection area in the center of the drawing.\n"
        "At the bottom of the V (the centerline), identify which line is on top:\n\n"
        "  • If the DOTTED line is ABOVE the SOLID line → CUT\n"
        "  • If the SOLID line is ABOVE the DOTTED line → FILL\n\n"
 
        "Also extract any visible text:\n"
        "  • Station number (e.g. 13+00, 20+50)\n"
        "  • Elevation values (e.g. 652.61)\n"
        "  • Slope ratios (e.g. 2:1, 3:1, 6.0%)\n\n"
 
        "Respond ONLY with valid JSON — no markdown, no explanation:\n"
        "{\n"
        '  "type": "CUT" or "FILL",\n'
        '  "station": "station number if visible, else null",\n'
        '  "elevation": "key elevation values if visible, else null",\n'
        '  "slopes": "slope ratios visible on drawing, else null",\n'
        '  "notes": "brief observation"\n'
        "}"
    )
    
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
        # Read image file
        with open(image_path, 'rb') as image_file:
            img_bytes = image_file.read()
        
        # Extract data using the internal function
        filename = os.path.basename(image_path)
        extracted_data = _extract_image_text(img_bytes, filename)
        
        return extracted_data
        
    except Exception as e:
        raise Exception(f"Failed to extract data from image: {str(e)}")


def extract_image_data_from_bytes(img_bytes: bytes) -> str:
    """For Streamlit usage when image is already in memory."""
    return _extract_image_text(img_bytes, filename="image.png")