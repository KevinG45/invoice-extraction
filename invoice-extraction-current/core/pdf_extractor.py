"""
PDF Text Extractor — extracts text, blocks, and tables from digital PDFs.

Primary engine : pdfplumber (best for tables + layout)
Fallback engine: PyMuPDF / fitz (fast text extraction with block coordinates)

This module is for *digital* (text-based) PDFs only — no OCR.
"""

import io
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def extract_digital_pdf(path: str) -> Dict[str, Any]:
    """
    Extract all text and table data from a digital (non-scanned) PDF.

    Uses pdfplumber as the primary extraction engine (better table
    detection).  Falls back to PyMuPDF if pdfplumber fails.

    Args:
        path: Path to a digital PDF file.

    Returns:
        {
            "full_text": str,           # All page text concatenated
            "pages": [
                {
                    "page_number": int,
                    "text": str,
                    "blocks": [{"text": str, "bbox": [x0,y0,x1,y1], "block_no": int}],
                    "tables": [{"data": [[...]], "rows": int, "cols": int}]
                }
            ],
            "page_count": int,
            "source_file": str
        }
    """
    path = Path(path)
    logger.info("[pdf_extractor] Extracting digital PDF: %s", path.name)

    result: Dict[str, Any] = {
        "full_text": "",
        "pages": [],
        "page_count": 0,
        "source_file": str(path),
    }

    all_text_parts: List[str] = []

    # ── Primary: pdfplumber (text + tables) ───────────────────────────────
    try:
        import pdfplumber

        with pdfplumber.open(str(path)) as pdf:
            result["page_count"] = len(pdf.pages)

            for page_num, page in enumerate(pdf.pages, start=1):
                page_data: Dict[str, Any] = {
                    "page_number": page_num,
                    "text": "",
                    "blocks": [],
                    "tables": [],
                }

                # Raw text
                page_text = page.extract_text(
                    x_tolerance=3, y_tolerance=3
                ) or ""
                page_data["text"] = page_text
                all_text_parts.append(f"--- Page {page_num} ---\n{page_text}")

                # Word-level blocks with bounding boxes
                try:
                    words = page.extract_words(
                        x_tolerance=3, y_tolerance=3,
                        keep_blank_chars=False,
                    )
                    for idx, w in enumerate(words):
                        page_data["blocks"].append({
                            "text": w["text"],
                            "bbox": [w["x0"], w["top"], w["x1"], w["bottom"]],
                            "block_no": idx,
                        })
                except Exception as we:
                    logger.debug(
                        "[pdf_extractor] Word extraction failed on page %d: %s",
                        page_num, we,
                    )

                # Tables
                try:
                    tables = page.extract_tables()
                    for table in tables:
                        if table:
                            page_data["tables"].append({
                                "data": table,
                                "rows": len(table),
                                "cols": len(table[0]) if table else 0,
                            })
                except Exception as te:
                    logger.warning(
                        "[pdf_extractor] Table extraction failed on page %d: %s",
                        page_num, te,
                    )

                result["pages"].append(page_data)

    except ImportError:
        logger.warning("[pdf_extractor] pdfplumber not installed; using PyMuPDF")
        result = _extract_with_pymupdf(path, result)
    except Exception as e:
        logger.error("[pdf_extractor] pdfplumber failed: %s", e)
        result = _extract_with_pymupdf(path, result)

    # Build full_text from whatever was collected
    if not all_text_parts:
        all_text_parts = [
            f"--- Page {p['page_number']} ---\n{p['text']}"
            for p in result["pages"]
        ]
    result["full_text"] = "\n\n".join(all_text_parts)

    logger.info(
        "[pdf_extractor] Extracted %d pages, %d chars",
        result["page_count"], len(result["full_text"]),
    )
    return result


# ── Fallback extractor ────────────────────────────────────────────────────


def _extract_with_pymupdf(path: Path, result: Dict[str, Any]) -> Dict[str, Any]:
    """Fallback extractor using PyMuPDF for text + block coordinates."""
    logger.info("[pdf_extractor] Falling back to PyMuPDF for %s", path.name)

    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error(
            "[pdf_extractor] Neither pdfplumber nor PyMuPDF available"
        )
        raise

    try:
        doc = fitz.open(str(path))
        result["page_count"] = len(doc)
        result["pages"] = []

        for page_num, page in enumerate(doc, start=1):
            page_text = page.get_text("text") or ""
            blocks_raw = page.get_text("blocks")
            # Each block: (x0, y0, x1, y1, text, block_no, block_type)

            blocks: List[Dict[str, Any]] = []
            for b in blocks_raw:
                if b[6] == 0:  # block_type 0 = text
                    blocks.append({
                        "text": b[4].strip(),
                        "bbox": [b[0], b[1], b[2], b[3]],
                        "block_no": b[5],
                    })

            result["pages"].append({
                "page_number": page_num,
                "text": page_text,
                "blocks": blocks,
                "tables": [],
            })

        doc.close()
    except Exception as e:
        logger.error("[pdf_extractor] PyMuPDF also failed: %s", e)
        raise

    return result


# ── Helper: convert PDF pages to images ───────────────────────────────────


def pdf_to_images(path: str, dpi: int = 300) -> List["Image.Image"]:
    """
    Convert PDF pages to PIL Images for OCR processing.

    Args:
        path: Path to the PDF file.
        dpi: Resolution for rendering (higher = better OCR, slower).

    Returns:
        List of PIL Image objects, one per page.
    """
    from PIL import Image as PILImage

    images: List[PILImage.Image] = []

    # Try PyMuPDF first (no external Poppler dependency)
    try:
        import fitz

        doc = fitz.open(path)
        for page in doc:
            zoom = dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("png")
            img = PILImage.open(io.BytesIO(img_bytes)).convert("RGB")
            images.append(img)
        doc.close()
        logger.info(
            "Converted %d PDF pages to images at %d DPI via PyMuPDF",
            len(images), dpi,
        )
        return images
    except ImportError:
        logger.warning(
            "PyMuPDF not available for PDF→image conversion; trying pdf2image"
        )

    # Fallback: pdf2image (requires poppler)
    try:
        from pdf2image import convert_from_path

        images = convert_from_path(path, dpi=dpi)
        logger.info(
            "Converted %d PDF pages to images at %d DPI via pdf2image",
            len(images), dpi,
        )
        return images
    except ImportError:
        logger.error(
            "Neither PyMuPDF nor pdf2image available for PDF→image conversion"
        )
        raise
    except Exception as e:
        logger.error("pdf2image failed: %s", e)
        raise


# ── Backward-compatible alias ─────────────────────────────────────────────


def extract_text_from_pdf(path: str) -> Dict[str, Any]:
    """
    Legacy wrapper — delegates to extract_digital_pdf and reshapes output
    to the old dict format for callers that expect it.
    """
    raw = extract_digital_pdf(path)
    return {
        "text": raw["full_text"],
        "pages": [p["text"] for p in raw["pages"]],
        "tables": [
            t["data"]
            for p in raw["pages"]
            for t in p.get("tables", [])
        ],
        "page_count": raw["page_count"],
        "method": "pdfplumber",
    }
