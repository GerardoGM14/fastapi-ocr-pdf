import re
from datetime import datetime
from typing import Optional
from PIL import Image
import pytesseract

DATE_RX = re.compile(r"(\d{2})/(\d{2})/(\d{4})")

def to_iso(d: str) -> str:
    m = DATE_RX.search(d)
    if not m: 
        return d
    dd, mm, yyyy = m.groups()
    return f"{yyyy}-{mm}-{dd}"

def ocr_image_to_text(img: Image.Image) -> str:
    return pytesseract.image_to_string(img, lang="spa")

def try_float(x) -> Optional[float]:
    try:
        return float(str(x).replace(",", "."))  # por si viene con coma
    except:
        return None
