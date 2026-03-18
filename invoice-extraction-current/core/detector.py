"""
PDF Type Detector — determines if a file is digital PDF, scanned PDF, or image.

Inspects the actual content of PDF files (not just the extension) to decide
the correct processing pathway:
  - "digital"  → PDF with extractable text (use pdfplumber/PyMuPDF)
  - "scanned"  → PDF with no/minimal text (use OCR pipeline)
  - "image"    → Direct image file (use OCR pipeline)

Uses PyMuPDF (fitz) to sample up to 3 pages and measure average character
count. If avg chars/page >= MIN_TEXT_CHARS the PDF is digital.
"""

import logging
from pathlib import Path
from typing import Literal

from core.config import MIN_TEXT_CHARS, SUPPORTED_EXTENSIONS

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}


def detect_file_type(path: str) -> str:
    """
    Inspect a file and return one of:
      "digital"  → PDF with extractable text (use pdfplumber/PyMuPDF)
      "scanned"  → PDF with no/minimal text (use OCR pipeline)
      "image"    → Direct image file (use OCR pipeline)

    Args:
        path: Path to the input file.

    Returns:
        One of "digital", "scanned", or "image".

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file extension is not supported.
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type: {ext}. Supported: {SUPPORTED_EXTENSIONS}"
        )

    # Pure image files — no PDF parsing needed
    if ext in IMAGE_EXTENSIONS:
        logger.info("[detector] %s → image", path.name)
        return "image"

    # PDF files — inspect content to decide digital vs scanned
    if ext == ".pdf":
        return _classify_pdf(str(path))

    # Fallback for any other supported but non-PDF, non-image extension
    return "image"


def _classify_pdf(path: str) -> str:
    """
    Open a PDF and check whether it contains extractable text.
    Samples up to 3 pages and computes average chars per page.

    Returns:
        "digital" if avg chars/page >= MIN_TEXT_CHARS, else "scanned".
        Defaults to "scanned" if the PDF cannot be opened.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("PyMuPDF (fitz) not installed. Run: pip install pymupdf")
        raise

    try:
        doc = fitz.open(path)
        total_chars = 0
        pages_sampled = min(3, len(doc))

        if pages_sampled == 0:
            doc.close()
            logger.info("[detector] %s → scanned (0 pages)", Path(path).name)
            return "scanned"

        for page_num in range(pages_sampled):
            page = doc[page_num]
            text = page.get_text("text").strip()
            total_chars += len(text)

        doc.close()
        avg_chars_per_page = total_chars / pages_sampled

        if avg_chars_per_page >= MIN_TEXT_CHARS:
            logger.info(
                "[detector] %s → digital (avg %.0f chars/page)",
                Path(path).name, avg_chars_per_page,
            )
            return "digital"
        else:
            logger.info(
                "[detector] %s → scanned (avg %.0f chars/page)",
                Path(path).name, avg_chars_per_page,
            )
            return "scanned"

    except Exception as e:
        logger.warning(
            "[detector] Could not classify PDF (%s), defaulting to 'scanned'", e
        )
        return "scanned"


# ── Convenience alias for backward compatibility ──────────────────────────
def detect_pdf_type(path: str) -> Literal["digital", "scanned"]:
    """Classify a PDF as 'digital' or 'scanned'. Thin wrapper over _classify_pdf."""
    return _classify_pdf(str(path))
