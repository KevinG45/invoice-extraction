"""
Document Loader for Baseline Invoice Extraction.

Handles loading invoices from various file formats and detecting document type.
The document type determines which text extraction strategy to use:

  DIGITAL PDF → pdfplumber (perfect text extraction, no OCR needed)
  SCANNED PDF → Convert to image → Tesseract OCR
  IMAGE FILES → Tesseract OCR (JPG, PNG, TIFF, BMP)

HOW DOCUMENT TYPE DETECTION WORKS:
  For PDFs, we check if the PDF contains extractable text:
  1. Open with pdfplumber
  2. Try to extract text from the first page
  3. If text length > 50 characters → DIGITAL PDF (has embedded text)
  4. If text length ≤ 50 characters → SCANNED PDF (just an image embedded)

WHY THIS MATTERS:
  Digital PDFs give us PERFECT text (100% accuracy) because the text
  is stored as Unicode strings in the PDF file itself.
  Scanned PDFs and images need OCR, which introduces errors.

SUPPORTED FORMATS:
  .pdf  → Digital or Scanned PDF
  .jpg, .jpeg → JPEG image
  .png  → PNG image
  .tiff, .tif → TIFF image
  .bmp  → Bitmap image

Author: ML Engineering Team
Date: 2026-02-19
Version: 3.0.0 (Baseline)
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

logger = logging.getLogger("invoice_extraction.baseline.document_loader")

# Supported file extensions (lowercase)
SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp"}


@dataclass
class LoadedDocument:
    """
    A loaded invoice document ready for processing.

    Attributes:
        file_path: Original file path.
        file_name: Just the filename (e.g., "invoice.pdf").
        document_type: One of "digital_pdf", "scanned_pdf", "image".
        images: List of PIL Image objects (one per page).
        page_count: Number of pages in the document.
        pdfplumber_doc: The pdfplumber document object (for digital PDFs only).
            This is kept open so the text extractor can use it directly.
    """
    file_path: str = ""
    file_name: str = ""
    document_type: str = ""  # "digital_pdf", "scanned_pdf", "image"
    images: List[Image.Image] = field(default_factory=list)
    page_count: int = 0
    pdfplumber_doc: Any = None  # pdfplumber.PDF object, kept for text extraction

    def close(self):
        """Close any open resources (like pdfplumber doc)."""
        if self.pdfplumber_doc is not None:
            try:
                self.pdfplumber_doc.close()
            except Exception:
                pass
            self.pdfplumber_doc = None


class DocumentLoader:
    """
    Loads invoice documents from file paths.

    Usage:
        loader = DocumentLoader()
        doc = loader.load("invoice.pdf")
        print(doc.document_type)  # "digital_pdf" or "scanned_pdf"
        print(doc.page_count)     # 1, 2, 3, ...
        for img in doc.images:
            # Process each page image
            pass

    Configuration:
        pdf_dpi: DPI for converting PDF pages to images (default: 300).
            Higher DPI = better OCR accuracy but slower processing.
        max_pages: Maximum number of pages to process (default: 50).
        min_text_length: Minimum characters to classify as digital PDF (default: 50).
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {}
        # PDF to image conversion DPI (300 is standard for OCR)
        self.pdf_dpi = config.get("pdf_dpi", 300)
        # Maximum pages to process per document
        self.max_pages = config.get("max_pages", 50)
        # Minimum text length to classify PDF as digital (not scanned)
        self.min_text_length = config.get("min_text_length", 50)

    def load(self, file_path: str) -> LoadedDocument:
        """
        Load a document from file path.

        Args:
            file_path: Path to PDF or image file.

        Returns:
            LoadedDocument with images and type classification.

        Raises:
            FileNotFoundError: If file doesn't exist.
            ValueError: If file type is not supported.
        """
        file_path = os.path.abspath(file_path)

        # Validate file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # Check file extension
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type: '{ext}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            )

        file_name = os.path.basename(file_path)
        logger.info(f"Loading document: {file_name}")

        # Route to appropriate loader based on file type
        if ext == ".pdf":
            return self._load_pdf(file_path, file_name)
        else:
            return self._load_image(file_path, file_name)

    def _load_pdf(self, file_path: str, file_name: str) -> LoadedDocument:
        """
        Load a PDF document and classify as digital or scanned.

        Strategy:
        1. Open with pdfplumber to check for text
        2. If has text → digital PDF (keep pdfplumber doc open for extraction)
        3. If no text → scanned PDF (convert pages to images for OCR)
        4. Either way, also convert to images (for model-based extraction)
        """
        doc = LoadedDocument(file_path=file_path, file_name=file_name)

        # Step 1: Try pdfplumber to check for embedded text
        pdfplumber_doc = None
        has_text = False
        try:
            import pdfplumber
            pdfplumber_doc = pdfplumber.open(file_path)
            page_count = len(pdfplumber_doc.pages)
            doc.page_count = min(page_count, self.max_pages)

            # Check first page for text content
            if page_count > 0:
                first_page = pdfplumber_doc.pages[0]
                text = first_page.extract_text() or ""
                # If we get substantial text, it's a digital PDF
                has_text = len(text.strip()) > self.min_text_length
                logger.debug(
                    f"PDF text check: {len(text.strip())} chars → "
                    f"{'digital' if has_text else 'scanned'}"
                )
        except ImportError:
            logger.warning("pdfplumber not installed. Treating all PDFs as scanned.")
        except Exception as e:
            logger.warning(f"pdfplumber failed to open {file_name}: {e}")

        # Step 2: Classify document type
        if has_text:
            doc.document_type = "digital_pdf"
            doc.pdfplumber_doc = pdfplumber_doc  # Keep open for text extraction
            logger.info(f"  Type: DIGITAL PDF ({doc.page_count} pages)")
        else:
            doc.document_type = "scanned_pdf"
            # Close pdfplumber if we won't use it
            if pdfplumber_doc:
                pdfplumber_doc.close()
            logger.info(f"  Type: SCANNED PDF ({doc.page_count} pages)")

        # Step 3: Convert PDF pages to images (needed for both types)
        doc.images = self._pdf_to_images(file_path, doc.page_count)
        if not doc.images:
            logger.error(f"Failed to convert {file_name} to images")
        else:
            logger.info(f"  Images: {len(doc.images)} page(s) converted")

        return doc

    def _load_image(self, file_path: str, file_name: str) -> LoadedDocument:
        """
        Load an image file (JPG, PNG, TIFF, BMP).

        Images are always treated as scanned documents that need OCR.
        Multi-page TIFF files are handled by extracting all frames.
        """
        doc = LoadedDocument(
            file_path=file_path,
            file_name=file_name,
            document_type="image",
        )

        try:
            img = Image.open(file_path)

            # Handle multi-frame images (e.g., multi-page TIFF)
            if hasattr(img, 'n_frames') and img.n_frames > 1:
                doc.page_count = min(img.n_frames, self.max_pages)
                for i in range(doc.page_count):
                    img.seek(i)
                    # Convert to RGB (some images are RGBA, L, CMYK, etc.)
                    page_img = self._ensure_rgb(img.copy())
                    doc.images.append(page_img)
            else:
                doc.page_count = 1
                doc.images = [self._ensure_rgb(img)]

            logger.info(f"  Type: IMAGE ({doc.page_count} page(s))")

        except Exception as e:
            logger.error(f"Failed to load image {file_name}: {e}")
            doc.page_count = 0

        return doc

    def _pdf_to_images(self, file_path: str, page_count: int) -> List[Image.Image]:
        """
        Convert PDF pages to PIL Images.

        Tries two methods in order:
        1. PyMuPDF (fitz) - faster, no external dependencies
        2. pdf2image - requires poppler installed

        Args:
            file_path: Path to the PDF file.
            page_count: Number of pages to convert.

        Returns:
            List of PIL Image objects.
        """
        images = []

        # Method 1: PyMuPDF (fitz) - preferred
        try:
            import fitz  # PyMuPDF
            pdf_doc = fitz.open(file_path)
            for page_idx in range(min(len(pdf_doc), page_count)):
                page = pdf_doc[page_idx]
                # Render at specified DPI
                pix = page.get_pixmap(dpi=self.pdf_dpi)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                images.append(img)
            pdf_doc.close()
            return images
        except ImportError:
            logger.debug("PyMuPDF not available, trying pdf2image...")
        except Exception as e:
            logger.warning(f"PyMuPDF failed: {e}, trying pdf2image...")

        # Method 2: pdf2image (requires poppler)
        try:
            from pdf2image import convert_from_path
            pil_images = convert_from_path(
                file_path,
                dpi=self.pdf_dpi,
                first_page=1,
                last_page=page_count,
            )
            images = [self._ensure_rgb(img) for img in pil_images]
            return images
        except ImportError:
            logger.error(
                "Neither PyMuPDF nor pdf2image is installed. "
                "Install one: pip install PyMuPDF  OR  pip install pdf2image"
            )
        except Exception as e:
            logger.error(f"pdf2image failed: {e}")

        return images

    def _ensure_rgb(self, image: Image.Image) -> Image.Image:
        """
        Convert any image mode to RGB.

        Images can come in many modes: RGBA, L (grayscale), CMYK, P (palette).
        We need RGB for consistent processing downstream.
        """
        if image.mode == "RGBA":
            # Composite RGBA onto white background
            background = Image.new("RGB", image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[3])
            return background
        elif image.mode != "RGB":
            return image.convert("RGB")
        return image


def discover_files(input_path: str) -> List[str]:
    """
    Discover all supported invoice files in a path.

    Args:
        input_path: Path to a single file or a directory.

    Returns:
        Sorted list of absolute file paths.
    """
    input_path = os.path.abspath(input_path)

    if os.path.isfile(input_path):
        ext = os.path.splitext(input_path)[1].lower()
        if ext in SUPPORTED_EXTENSIONS:
            return [input_path]
        else:
            logger.warning(f"Unsupported file type: {ext}")
            return []

    if os.path.isdir(input_path):
        files = []
        # Walk directory recursively
        for root, _, filenames in os.walk(input_path):
            for fn in sorted(filenames):
                ext = os.path.splitext(fn)[1].lower()
                if ext in SUPPORTED_EXTENSIONS:
                    files.append(os.path.join(root, fn))
        logger.info(f"Discovered {len(files)} invoice files in {input_path}")
        return sorted(files)

    logger.error(f"Input path not found: {input_path}")
    return []
