import os
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'

"""
Logo-based vendor name extractor — fallback for when LLM/regex miss the vendor name.

Crops the top 30 % of the invoice image (where logos and company names typically
appear) and runs EasyOCR to find the most likely company name.

Public API:
    extract_vendor_from_logo(file_path) → dict
"""

import logging
import re
from typing import Dict

logger = logging.getLogger(__name__)

_METHOD = "easyocr"

_EASYOCR_READER = None

def _get_reader():
    global _EASYOCR_READER
    if _EASYOCR_READER is None:
        import easyocr
        _EASYOCR_READER = easyocr.Reader(
            ['en'], gpu=False, verbose=False
        )
    return _EASYOCR_READER


def extract_vendor_from_logo(file_path: str) -> Dict:
    """
    Attempt to extract the vendor/company name from the logo region of an invoice.

    Args:
        file_path: Absolute path to the invoice image or first-page image.

    Returns:
        {
            "vendor_name": str | None,
            "confidence": float,        # 0.0 – 1.0
            "source": "logo_extractor",
            "method": "easyocr",
        }
    """
    import cv2; cv2.setNumThreads(1)

    _fail = {
        "vendor_name": None,
        "confidence": 0.0,
        "source": "logo_extractor",
        "method": _METHOD,
    }

    try:
        from PIL import Image, ImageEnhance, ImageFilter
        import numpy as np

        # ── Open image and crop to top 40 % ──────────────────────────
        img = Image.open(file_path).convert("RGB")
        w, h = img.size
        crop_h = int(h * 0.40)
        top_region = img.crop((0, 0, w, crop_h))

        # ── Preprocess for better OCR ─────────────────────────────────
        top_region = top_region.convert('L')
        top_region = ImageEnhance.Contrast(top_region).enhance(2.0)
        top_region = top_region.filter(ImageFilter.SHARPEN)
        top_region = top_region.resize((top_region.width*2, top_region.height*2))
        top_region = top_region.convert("RGB")

        top_np = np.array(top_region)

        # ── Run EasyOCR on the cropped region ─────────────────────────
        reader = _get_reader()
        results = reader.readtext(top_np)
        # results: list of (bbox, text, confidence)

        if not results:
            logger.info("[logo_extractor] EasyOCR returned no text from top region")
            return _fail

        # ── Filter and pick the best candidate ────────────────────────
        # Common invoice labels / headers that are NOT vendor names
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

        candidates = []
        for _bbox, text, conf in results:
            text = text.strip()
            if len(text) <= 2:
                continue
            # Skip date-like strings (contains / or - with digits around it)
            if re.search(r'\d[/\-]\d', text):
                continue
            # Skip number-only strings
            if re.match(r'^[\d\s.,]+$', text):
                continue
            # Skip common invoice labels and headers
            if _SKIP_PATTERNS.search(text):
                continue
            # Skip strings that look like dates even without separators
            if re.search(r'(?:January|February|March|April|May|June|July|August|'
                         r'September|October|November|December)\s+\d', text, re.IGNORECASE):
                continue
            # Skip email addresses and URLs
            if '@' in text or 'http' in text.lower() or '.in' == text[-3:].lower():
                continue
            # Skip phone-number-like strings (mostly digits)
            digits = sum(c.isdigit() for c in text)
            if digits > len(text) * 0.6 and digits >= 6:
                continue
            candidates.append((text, float(conf), _bbox))

        if not candidates:
            logger.info("[logo_extractor] No valid text candidates in logo region")
            return _fail

        # Prefer text that appears in the top-left area (logo zone) with good confidence.
        # Score = confidence * positional_bonus (higher=closer to top-left).
        img_w = top_np.shape[1]
        scored = []
        for text, conf, bbox in candidates:
            # bbox: [[x1,y1],[x2,y1],[x2,y2],[x1,y2]] from easyocr
            y_center = (bbox[0][1] + bbox[2][1]) / 2 / top_np.shape[0]
            x_center = (bbox[0][0] + bbox[2][0]) / 2 / img_w
            # Favor top-left: lower y and lower x get a bonus
            pos_bonus = 1.0 - (y_center * 0.3 + x_center * 0.1)
            score = conf * pos_bonus
            scored.append((text, conf, score))

        best_text, best_conf, _score = max(scored, key=lambda c: c[2])

        logger.info(
            "[logo_extractor] Extracted vendor name: '%s' (conf=%.2f)",
            best_text, best_conf,
        )
        return {
            "vendor_name": best_text,
            "confidence": best_conf,
            "source": "logo_extractor",
            "method": _METHOD,
        }

    except Exception as e:
        logger.error("[logo_extractor] Failed: %s", e)
        return _fail
