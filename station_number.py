import fitz
import os
import re
import pytesseract
from PIL import Image
import io

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

file_to_process = r"C:\Users\srika\Downloads\19series.pdf"

def extract_station_numbers(pdf_path):
    if not os.path.exists(pdf_path):
        print(f"ERROR: File '{pdf_path}' not found.")
        return

    doc = fitz.open(pdf_path)
    print(f"Total pages: {len(doc)}\n")

    for i in range(len(doc)):
        page = doc[i]
        rect = page.rect

        # OCR only the right strip where station numbers appear
        right_strip = fitz.Rect(rect.width * 0.80, 0, rect.width, rect.height)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=right_strip)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        text = pytesseract.image_to_string(img, config="--psm 6")

        # Find anything matching a station number pattern e.g. 10+00, 10+50
        stations = re.findall(r'\d{1,4}\+\d{2}', text)

        if stations:
            for sta in stations:
                print(f"Page {i+1} | Station: {sta}")

extract_station_numbers(file_to_process)