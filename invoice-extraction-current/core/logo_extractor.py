import os
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'

"""
Logo-based vendor name extractor — fallback for when LLM/regex miss the vendor name.

Crops the top 40% of the invoice image (where logos and company names typically
appear) and runs OCR to find the most likely company name.

Strategy:
    1. Try Tesseract first (stable, no segfault risk)
    2. Fall back to EasyOCR if Tesseract finds no valid candidates

Public API:
    extract_vendor_from_logo(file_path) → dict
"""

import logging
import re
import threading
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_EASYOCR_READER = None
_READER_LOCK = threading.Lock()

# Shared skip patterns for both Tesseract and EasyOCR candidates
_SKIP_PATTERNS = re.compile(
    r'^('
    r'invoice|tax\s*invoice|original|duplicate|bill\s*to|ship\s*to'
    r'|date|due\s*date|invoice\s*date|p\.?o\.?\s*(number|date)'
    r'|gstin|place\s*of\s*supply|billing|receipt'
    r'|waybill|delivery|vehicle|shipping|l\.?r\.?\s*no'
    r'|for\s+recipient|original\s+for'
    r')\b',
    re.IGNORECASE,
)


def _get_reader():
    """Lazily initialise EasyOCR reader with a thread lock to prevent double-init."""
    global _EASYOCR_READER
    with _READER_LOCK:
        if _EASYOCR_READER is None:
            import easyocr
            _EASYOCR_READER = easyocr.Reader(['en'], gpu=False, verbose=False)
    return _EASYOCR_READER


def _is_valid_candidate(text: str) -> bool:
    """Return True if the text looks like a company name, not a label/number."""
    text = text.strip()
    if len(text) <= 2:
        return False
    if re.search(r'\d[/\-]\d', text):  # date-like
        return False
    if re.match(r'^[\d\s.,]+$', text):  # pure number
        return False
    if _SKIP_PATTERNS.search(text):
        return False
    if re.search(r'(?:January|February|March|April|May|June|July|August|'
                 r'September|October|November|December)\s+\d', text, re.IGNORECASE):
        return False
    if '@' in text or 'http' in text.lower() or text.lower().endswith('.in') \
            or text.lower().endswith('.com') or text.lower().endswith('.co'):
        return False
    digits = sum(c.isdigit() for c in text)
    if digits > len(text) * 0.6 and digits >= 6:  # phone-like
        return False
    return True


def _vendor_from_tesseract(top_np) -> Optional[str]:
    """Extract vendor name candidate using Tesseract on the cropped top region."""
    try:
        import pytesseract
        import numpy as np
        from PIL import Image

        img = Image.fromarray(top_np)
        data = pytesseract.image_to_data(img, lang='eng', output_type=pytesseract.Output.DICT)

        # Group words into lines by their block_num/par_num/line_num
        lines: dict = {}
        for i, word in enumerate(data['text']):
            word = word.strip()
            if not word:
                continue
            conf = int(data['conf'][i])
            if conf < 30:  # skip very low-confidence words
                continue
            line_key = (data['block_num'][i], data['par_num'][i], data['line_num'][i])
            lines.setdefault(line_key, []).append((word, data['top'][i]))

        candidates = []
        for line_key, words_tops in lines.items():
            line_text = ' '.join(w for w, _ in words_tops)
            avg_top = sum(t for _, t in words_tops) / len(words_tops)
            if _is_valid_candidate(line_text):
                candidates.append((line_text, avg_top))

        if not candidates:
            return None

        # Prefer lines nearest the top (company name is usually first)
        candidates.sort(key=lambda x: x[1])
        return candidates[0][0]

    except Exception as e:
        logger.debug("[logo_extractor] Tesseract candidate extraction failed: %s", e)
        return None


def extract_vendor_from_logo(file_path: str) -> Dict:
    """
    Attempt to extract the vendor/company name from the logo region of an invoice.

    Tries Tesseract first; falls back to EasyOCR if no valid candidate found.

    Args:
        file_path: Absolute path to the invoice image file.

    Returns:
        {
            "vendor_name": str | None,
            "confidence": float,
            "source": "logo_extractor",
            "method": "tesseract" | "easyocr",
        }
    """
    import cv2
    cv2.setNumThreads(1)

    _fail = {
        "vendor_name": None,
        "confidence": 0.0,
        "source": "logo_extractor",
        "method": "none",
    }

    try:
        from PIL import Image, ImageEnhance, ImageFilter
        import numpy as np

        # Open image and crop to top 40%
        img = Image.open(file_path).convert("RGB")
        w, h = img.size
        crop_h = int(h * 0.40)
        top_region = img.crop((0, 0, w, crop_h))

        # Preprocess for better OCR
        top_region = top_region.convert('L')
        top_region = ImageEnhance.Contrast(top_region).enhance(2.0)
        top_region = top_region.filter(ImageFilter.SHARPEN)
        # Only upscale if image is small
        if top_region.width < 900:
            top_region = top_region.resize((top_region.width * 2, top_region.height * 2))
        top_region = top_region.convert("RGB")
        top_np = np.array(top_region)

        # ── Strategy 1: Tesseract (stable, no segfault risk) ──────────
        tess_result = _vendor_from_tesseract(top_np)
        if tess_result:
            logger.info("[logo_extractor] Tesseract vendor: '%s'", tess_result)
            return {
                "vendor_name": tess_result,
                "confidence": 0.8,
                "source": "logo_extractor",
                "method": "tesseract",
            }

        # ── Strategy 2: EasyOCR fallback ──────────────────────────────
        reader = _get_reader()
        results = reader.readtext(top_np)

        if not results:
            logger.info("[logo_extractor] EasyOCR returned no text")
            return _fail

        candidates = []
        for _bbox, text, conf in results:
            text = text.strip()
            if _is_valid_candidate(text):
                candidates.append((text, float(conf), _bbox))

        if not candidates:
            logger.info("[logo_extractor] No valid candidates in logo region")
            return _fail

        img_w = top_np.shape[1]
        scored = []
        for text, conf, bbox in candidates:
            y_center = (bbox[0][1] + bbox[2][1]) / 2 / top_np.shape[0]
            x_center = (bbox[0][0] + bbox[2][0]) / 2 / img_w
            pos_bonus = 1.0 - (y_center * 0.3 + x_center * 0.1)
            score = conf * pos_bonus
            scored.append((text, conf, score))

        best_text, best_conf, _ = max(scored, key=lambda c: c[2])

        logger.info("[logo_extractor] EasyOCR vendor: '%s' (conf=%.2f)", best_text, best_conf)
        return {
            "vendor_name": best_text,
            "confidence": best_conf,
            "source": "logo_extractor",
            "method": "easyocr",
        }

    except Exception as e:
        logger.error("[logo_extractor] Failed: %s", e)
        return _fail
