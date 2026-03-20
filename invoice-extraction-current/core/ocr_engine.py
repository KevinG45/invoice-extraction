"""
OCR Engine — PaddleOCR wrapper with preprocessing for scanned/image invoices.

Primary engine : PaddleOCR v2.x (PP-OCRv4)
Fallback engine: docTR
Image preprocessing chain: grayscale → contrast → denoise → binarize.

Public API:
    run_ocr(image_input, engine)          → list[dict]   (single image)
    run_ocr_on_pdf(pdf_path, engine, dpi) → dict          (multi-page PDF)
    run_ocr_on_image_file(image_path)     → dict          (single image file)
    ocr_image(image, preprocess)          → dict          (legacy compat)
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from core.config import USE_GPU, OCR_LANG

logger = logging.getLogger(__name__)

# Disable MKL-DNN to avoid "fused_conv2d" / OneDNN crashes on some CPUs
os.environ.setdefault("FLAGS_use_mkldnn", "0")

# ── Lazy-loaded engine instances (expensive to create) ────────────────────
_paddle_ocr_instance = None
_doctr_model_instance = None


# ══════════════════════════════════════════════════════════════════════════
# Engine initialisation helpers
# ══════════════════════════════════════════════════════════════════════════

def _get_paddle_ocr():
    """Lazy-initialise PaddleOCR to avoid slow import on startup."""
    global _paddle_ocr_instance
    if _paddle_ocr_instance is None:
        logger.info("[ocr_engine] Initialising PaddleOCR...")
        try:
            from paddleocr import PaddleOCR

            _paddle_ocr_instance = PaddleOCR(
                use_angle_cls=True,
                lang=OCR_LANG,
                use_gpu=USE_GPU,
                show_log=False,
                enable_mkldnn=False,
            )
            logger.info("[ocr_engine] PaddleOCR initialised (gpu=%s, lang=%s)", USE_GPU, OCR_LANG)
        except Exception as e:
            logger.error("[ocr_engine] PaddleOCR init failed: %s", e)
            raise
    return _paddle_ocr_instance


def _get_doctr_model():
    """Lazy-initialise docTR as fallback."""
    global _doctr_model_instance
    if _doctr_model_instance is None:
        logger.info("[ocr_engine] Initialising docTR fallback...")
        from doctr.models import ocr_predictor

        _doctr_model_instance = ocr_predictor(pretrained=True)
        logger.info("[ocr_engine] docTR initialised")
    return _doctr_model_instance


# ══════════════════════════════════════════════════════════════════════════
# Image preprocessing
# ══════════════════════════════════════════════════════════════════════════

def preprocess_image(image: Image.Image) -> Image.Image:
    """
    Apply preprocessing chain to improve OCR accuracy on invoice images.

    Pipeline:
        1. Convert to RGB
        2. Contrast enhancement (factor 1.5)
        3. Sharpening (factor 1.3)
        4. Convert to greyscale
        5. Otsu binarisation
        6. Convert back to RGB (for engine compatibility)
    """
    if image.mode != "RGB":
        image = image.convert("RGB")

    # Scale up only if image is below target width — avoids 4x pixel-count blowup
    # on already high-resolution scans (300+ DPI A4 = 2480px wide)
    TARGET_WIDTH = 1800  # px optimal for Tesseract on A4 invoices
    w, h = image.size
    if w < TARGET_WIDTH:
        scale = TARGET_WIDTH / w
        image = image.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        w, h = image.size
    # Autocontrast — normalises pixel range before further processing
    image = ImageOps.autocontrast(image)

    # Enhance contrast (helps with faded scans)
    image = ImageEnhance.Contrast(image).enhance(1.5)
    # Sharpen (helps with blurry scans)
    image = ImageEnhance.Sharpness(image).enhance(1.3)
    # Convert to greyscale for binarisation
    grey = image.convert("L")
    # Otsu-style binarisation via adaptive threshold
    import cv2
    grey_arr = np.array(grey)
    _, binary = cv2.threshold(grey_arr, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    image = Image.fromarray(binary).convert("RGB")

    return image


# ══════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════

def run_ocr(
    image_input: Union[str, Image.Image, np.ndarray],
    engine: str = "paddleocr",
) -> List[Dict[str, Any]]:
    """
    Run OCR on a single image.

    Args:
        image_input: file path (str), PIL.Image, or numpy ndarray.
        engine: ``"paddleocr"`` (default) or ``"doctr"``.

    Returns:
        List of dicts:
        ``[{"text": str, "bbox": [x1,y1,x2,y2], "confidence": float}]``
    """
    # Normalise to PIL Image
    if isinstance(image_input, str):
        image = Image.open(image_input).convert("RGB")
    elif isinstance(image_input, np.ndarray):
        image = Image.fromarray(image_input).convert("RGB")
    elif isinstance(image_input, Image.Image):
        image = image_input.convert("RGB")
    else:
        raise TypeError(f"Unsupported image_input type: {type(image_input)}")

    # Apply preprocessing before OCR
    image = preprocess_image(image)

    if engine == "paddleocr":
        return _run_paddleocr(image)
    elif engine == "tesseract":
        return _run_tesseract(image)
    elif engine == "doctr":
        return _run_doctr(image)
    else:
        raise ValueError(f"Unknown OCR engine: {engine}. Use 'paddleocr', 'tesseract', or 'doctr'")


def run_ocr_on_pdf(
    pdf_path: str,
    engine: str = "paddleocr",
    dpi: int = 200,
) -> Dict[str, Any]:
    """
    Convert each PDF page to an image and run OCR.

    Args:
        pdf_path: Path to a PDF file.
        engine: OCR engine to use.
        dpi: Resolution for PDF → image conversion.

    Returns:
        Same structure as ``extract_digital_pdf()`` for pipeline consistency::

            {"full_text", "pages": [{page_number, text, blocks}], "page_count", "source_file"}
    """
    pdf_path = Path(pdf_path)
    logger.info("[ocr_engine] Converting PDF to images: %s at %d DPI", pdf_path.name, dpi)

    # Use PyMuPDF for conversion (no Poppler dependency)
    images = _pdf_to_images(str(pdf_path), dpi=dpi)
    logger.info("[ocr_engine] Converted %d pages. Running OCR...", len(images))

    result: Dict[str, Any] = {
        "full_text": "",
        "pages": [],
        "page_count": len(images),
        "source_file": str(pdf_path),
    }
    all_text_parts: List[str] = []

    for page_num, image in enumerate(images, start=1):
        logger.info("[ocr_engine] OCR page %d/%d", page_num, len(images))
        blocks = run_ocr(image, engine=engine)
        page_text = " ".join(b["text"] for b in blocks if b["text"].strip())
        result["pages"].append({
            "page_number": page_num,
            "text": page_text,
            "blocks": blocks,
        })
        all_text_parts.append(f"--- Page {page_num} ---\n{page_text}")

    result["full_text"] = "\n\n".join(all_text_parts)
    logger.info("[ocr_engine] OCR complete. Total chars: %d", len(result["full_text"]))
    return result


def run_ocr_on_image_file(
    image_path: str,
    engine: str = "paddleocr",
) -> Dict[str, Any]:
    """
    Run OCR on a single image file (not a PDF).

    Returns the same dict structure as ``run_ocr_on_pdf`` for consistency.
    """
    image_path = Path(image_path)
    logger.info("[ocr_engine] OCR on image: %s", image_path.name)
    blocks = run_ocr(str(image_path), engine=engine)
    page_text = _reconstruct_text(blocks)
    return {
        "full_text": page_text,
        "pages": [{"page_number": 1, "text": page_text, "blocks": blocks}],
        "page_count": 1,
        "source_file": str(image_path),
    }


# ══════════════════════════════════════════════════════════════════════════
# Legacy / backward-compatible wrapper
# ══════════════════════════════════════════════════════════════════════════

def ocr_image(
    image: Image.Image,
    preprocess: bool = True,
) -> Dict[str, Any]:
    """
    Run PaddleOCR on a PIL Image and return structured results.

    This is the legacy interface kept for backward compatibility.

    Returns:
        ``{"text": str, "lines": [...], "confidence": float}``
    """
    if preprocess:
        image = preprocess_image(image)

    img_array = np.array(image)
    ocr = _get_paddle_ocr()

    try:
        result = ocr.ocr(img_array, cls=True)
    except Exception as e:
        logger.error("[ocr_engine] PaddleOCR inference failed: %s", e)
        return {"text": "", "lines": [], "confidence": 0.0}

    lines: List[Dict[str, Any]] = []
    all_text: List[str] = []
    confidences: List[float] = []

    if result and result[0]:
        for line_data in result[0]:
            if line_data and len(line_data) >= 2:
                bbox = line_data[0]
                text_conf = line_data[1]

                if isinstance(text_conf, (list, tuple)) and len(text_conf) >= 2:
                    text = str(text_conf[0])
                    conf = float(text_conf[1])
                else:
                    text = str(text_conf)
                    conf = 0.5

                lines.append({"text": text, "confidence": conf, "bbox": bbox})
                all_text.append(text)
                confidences.append(conf)

    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
    return {"text": "\n".join(all_text), "lines": lines, "confidence": avg_conf}


def ocr_image_batch(
    images: List[Image.Image],
    preprocess: bool = True,
) -> List[Dict[str, Any]]:
    """Run OCR on multiple images and return results for each."""
    results = []
    for i, img in enumerate(images):
        logger.info("[ocr_engine] OCR batch %d/%d", i + 1, len(images))
        results.append(ocr_image(img, preprocess=preprocess))
    return results


# ══════════════════════════════════════════════════════════════════════════
# Text reconstruction from OCR blocks
# ══════════════════════════════════════════════════════════════════════════

def _reconstruct_text(blocks: List[Dict[str, Any]]) -> str:
    """
    Reconstruct readable text from OCR blocks using spatial position.

    Groups words into lines based on y-coordinate proximity, then sorts
    words within each line by x-coordinate. Inserts newlines between lines.
    """
    if not blocks:
        return ""

    # Filter to blocks with text and valid bboxes
    valid = [b for b in blocks if b.get("text", "").strip() and b.get("bbox")]
    if not valid:
        return ""

    # Sort by top-y, then left-x
    valid.sort(key=lambda b: (b["bbox"][1], b["bbox"][0]))

    # Group into lines: blocks whose top-y is within a threshold of each other
    lines: List[List[Dict]] = []
    current_line: List[Dict] = [valid[0]]
    for b in valid[1:]:
        prev_top = current_line[0]["bbox"][1]
        prev_bottom = current_line[0]["bbox"][3]
        line_height = max(prev_bottom - prev_top, 10)
        # If this block's top-y is within half a line height of the current line, same line
        if abs(b["bbox"][1] - prev_top) < line_height * 0.5:
            current_line.append(b)
        else:
            lines.append(current_line)
            current_line = [b]
    lines.append(current_line)

    # Sort words within each line by x-coordinate and join
    text_lines = []
    for line in lines:
        line.sort(key=lambda b: b["bbox"][0])
        text_lines.append(" ".join(b["text"] for b in line))

    return "\n".join(text_lines)


# ══════════════════════════════════════════════════════════════════════════
# Private engine implementations
# ══════════════════════════════════════════════════════════════════════════

def _run_paddleocr(image: Image.Image) -> List[Dict[str, Any]]:
    """Run PaddleOCR on a PIL Image. Returns list of text blocks."""
    try:
        ocr = _get_paddle_ocr()
        img_array = np.array(image)
        raw_result = ocr.ocr(img_array, cls=True)

        blocks: List[Dict[str, Any]] = []
        if raw_result and raw_result[0]:
            for line in raw_result[0]:
                if line is None:
                    continue
                bbox_raw, (text, confidence) = line
                # PaddleOCR: [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
                xs = [p[0] for p in bbox_raw]
                ys = [p[1] for p in bbox_raw]
                blocks.append({
                    "text": text.strip(),
                    "bbox": [min(xs), min(ys), max(xs), max(ys)],
                    "confidence": float(confidence),
                })
        return blocks

    except Exception as e:
        logger.error("[ocr_engine] PaddleOCR inference failed: %s", e)
        logger.info("[ocr_engine] Trying docTR fallback...")
        return _run_doctr(image)


def _run_tesseract(image: Image.Image) -> List[Dict[str, Any]]:
    """Run Tesseract OCR on a PIL Image. Returns list of text blocks."""
    try:
        import pytesseract

        # Use pytesseract to get word-level data with bboxes and confidences
        data = pytesseract.image_to_data(image, lang="eng", output_type=pytesseract.Output.DICT)

        blocks: List[Dict[str, Any]] = []
        n = len(data["text"])
        for i in range(n):
            text = data["text"][i].strip()
            conf = int(data["conf"][i])
            if not text or conf < 0:
                continue
            x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
            blocks.append({
                "text": text,
                "bbox": [x, y, x + w, y + h],
                "confidence": conf / 100.0,
            })
        return blocks

    except Exception as e:
        logger.error("[ocr_engine] Tesseract inference failed: %s", e)
        return []


def _run_doctr(image: Image.Image) -> List[Dict[str, Any]]:
    """Run docTR on a PIL Image. Returns list of text blocks."""
    try:
        from doctr.io import DocumentFile

        model = _get_doctr_model()

        # docTR needs a file path
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            image.save(tmp.name)
            tmp_path = tmp.name

        doc = DocumentFile.from_images([tmp_path])
        output = model(doc)
        os.unlink(tmp_path)

        blocks: List[Dict[str, Any]] = []
        for page in output.pages:
            for block in page.blocks:
                for line in block.lines:
                    for word in line.words:
                        blocks.append({
                            "text": word.value,
                            "bbox": list(word.geometry[0]) + list(word.geometry[1]),
                            "confidence": float(word.confidence),
                        })
        return blocks

    except Exception as e:
        logger.error("[ocr_engine] docTR also failed: %s", e)
        return []  # Return empty rather than crash the pipeline


# ── PDF → image helper (PyMuPDF primary, pdf2image fallback) ──────────────

def _pdf_to_images(path: str, dpi: int = 200) -> List[Image.Image]:
    """Convert PDF pages to PIL Images."""
    import io as _io

    # Try PyMuPDF first
    try:
        import fitz

        doc = fitz.open(path)
        images: List[Image.Image] = []
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        for page in doc:
            pix = page.get_pixmap(matrix=mat)
            img = Image.open(_io.BytesIO(pix.tobytes("png"))).convert("RGB")
            images.append(img)
        doc.close()
        return images
    except ImportError:
        pass

    # Fallback: pdf2image
    try:
        from pdf2image import convert_from_path

        return convert_from_path(path, dpi=dpi)
    except ImportError:
        logger.error("[ocr_engine] Neither PyMuPDF nor pdf2image available")
        raise
    except Exception as e:
        logger.error("[ocr_engine] pdf2image failed: %s. Is Poppler installed?", e)
        raise
