"""
Text Extractor for Baseline Invoice Extraction.

Extracts text from invoice documents using the best available method:

  DIGITAL PDF → pdfplumber
    - Extracts embedded text directly (100% accuracy for digital text)
    - Also extracts table structures (rows, columns, cells)
    - Preserves spatial layout information

  SCANNED PDF / IMAGE → Tesseract OCR
    - First applies image preprocessing (enhance contrast, deskew)
    - Then runs Tesseract OCR to convert pixels to text
    - Returns text with confidence scores per word

WHY TWO METHODS:
  Digital PDFs have text stored as Unicode strings - we can read them
  perfectly. No AI/ML needed. This is like copy-pasting from a Word document.

  Scanned PDFs and images are just pictures of text. We need OCR
  (Optical Character Recognition) to "read" the text from pixels.
  OCR can make mistakes, especially on low-quality images.

PREPROCESSING FOR OCR:
  Before running OCR on an image, we improve it:
  1. Convert to grayscale (OCR works on B&W)
  2. Enhance contrast (make text darker, background lighter)
  3. Remove noise (smooth out speckles)
  4. Binarize (convert to pure black and white)
  These steps can improve OCR accuracy by 10-30%.

Author: ML Engineering Team
Date: 2026-02-19
Version: 3.0.0 (Baseline)
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

logger = logging.getLogger("invoice_extraction.baseline.text_extractor")


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class TextBlock:
    """
    A block of text with position and confidence information.

    Attributes:
        text: The extracted text string.
        confidence: OCR confidence (0-100). For pdfplumber, always 99.0.
        bbox: Bounding box (x0, y0, x1, y1) in pixels. May be None.
        page_number: Which page this text came from (1-indexed).
    """
    text: str = ""
    confidence: float = 0.0
    bbox: Optional[Tuple[float, float, float, float]] = None
    page_number: int = 1


@dataclass
class ExtractedText:
    """
    Complete text extraction result for a document.

    Attributes:
        full_text: All text concatenated (for regex matching).
        text_blocks: Individual text blocks with positions.
        tables: Extracted tables (for digital PDFs via pdfplumber).
            Each table is a list of rows, each row is a list of cell strings.
        method: Which extraction method was used.
        avg_confidence: Average OCR confidence across all blocks.
        extraction_time_ms: How long extraction took in milliseconds.
    """
    full_text: str = ""
    text_blocks: List[TextBlock] = field(default_factory=list)
    tables: List[List[List[Optional[str]]]] = field(default_factory=list)
    method: str = ""  # "pdfplumber", "tesseract"
    avg_confidence: float = 0.0
    extraction_time_ms: int = 0


# =============================================================================
# TEXT EXTRACTOR
# =============================================================================

class TextExtractor:
    """
    Extracts text from invoice documents.

    Automatically chooses the best extraction method based on document type:
    - Digital PDF → pdfplumber (perfect text + tables)
    - Image/Scan → Tesseract OCR (with preprocessing)

    Usage:
        extractor = TextExtractor()

        # For digital PDFs (pdfplumber_doc from DocumentLoader)
        result = extractor.extract_from_digital_pdf(pdfplumber_doc, page_num=0)

        # For images (PIL Image from DocumentLoader)
        result = extractor.extract_from_image(pil_image)
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {}
        # Tesseract configuration
        self.tesseract_lang = config.get("tesseract_lang", "eng")
        # PSM 6 = Assume a single uniform block of text (good for invoices)
        # PSM 3 = Fully automatic page segmentation (default)
        self.tesseract_psm = config.get("tesseract_psm", 6)
        # Whether to apply preprocessing before OCR
        self.preprocess = config.get("preprocess", True)

    # =========================================================================
    # DIGITAL PDF TEXT EXTRACTION (via pdfplumber)
    # =========================================================================

    def extract_from_digital_pdf(
        self,
        pdfplumber_doc: Any,
        page_numbers: Optional[List[int]] = None,
    ) -> ExtractedText:
        """
        Extract text and tables from a digital PDF using pdfplumber.

        This gives us PERFECT text extraction for digital PDFs.
        No OCR needed - the text is read directly from the PDF file.

        Args:
            pdfplumber_doc: An open pdfplumber document object.
            page_numbers: Which pages to extract (0-indexed). None = all pages.

        Returns:
            ExtractedText with full text, text blocks, and tables.
        """
        start_time = time.time()
        result = ExtractedText(method="pdfplumber")

        try:
            if page_numbers is None:
                page_numbers = list(range(len(pdfplumber_doc.pages)))

            all_text_parts = []
            all_blocks = []
            all_tables = []

            for page_idx in page_numbers:
                if page_idx >= len(pdfplumber_doc.pages):
                    continue

                page = pdfplumber_doc.pages[page_idx]

                # --- Extract full text ---
                page_text = page.extract_text() or ""
                if page_text.strip():
                    all_text_parts.append(page_text)

                # --- Extract text with positions (word-level) ---
                words = page.extract_words() or []
                for word in words:
                    block = TextBlock(
                        text=word.get("text", ""),
                        confidence=99.0,  # Digital PDF = perfect text
                        bbox=(
                            word.get("x0", 0),
                            word.get("top", 0),
                            word.get("x1", 0),
                            word.get("bottom", 0),
                        ),
                        page_number=page_idx + 1,
                    )
                    all_blocks.append(block)

                # --- Extract tables ---
                # pdfplumber can detect and extract tables automatically
                page_tables = page.extract_tables() or []
                for table in page_tables:
                    if table and len(table) > 0:
                        all_tables.append(table)
                        logger.debug(
                            f"  Page {page_idx + 1}: Found table with "
                            f"{len(table)} rows × {len(table[0]) if table[0] else 0} columns"
                        )

            result.full_text = "\n\n".join(all_text_parts)
            result.text_blocks = all_blocks
            result.tables = all_tables
            result.avg_confidence = 99.0  # Digital PDF = perfect

            logger.info(
                f"pdfplumber extracted: {len(result.full_text)} chars, "
                f"{len(result.text_blocks)} words, {len(result.tables)} tables"
            )

        except Exception as e:
            logger.error(f"pdfplumber extraction failed: {e}")

        result.extraction_time_ms = int((time.time() - start_time) * 1000)
        return result

    # =========================================================================
    # IMAGE / SCANNED PDF TEXT EXTRACTION (via Tesseract OCR)
    # =========================================================================

    def extract_from_image(
        self,
        image: Image.Image,
        page_number: int = 1,
    ) -> ExtractedText:
        """
        Extract text from an image using Tesseract OCR.

        Applies preprocessing to improve OCR quality, then runs Tesseract.

        Args:
            image: PIL Image to extract text from.
            page_number: Page number for metadata (1-indexed).

        Returns:
            ExtractedText with full text and confidence scores.
        """
        start_time = time.time()
        result = ExtractedText(method="tesseract")

        try:
            # Step 1: Preprocess image for better OCR
            if self.preprocess:
                processed_image = self._preprocess_for_ocr(image)
            else:
                processed_image = image

            # Step 2: Run Tesseract OCR
            result = self._run_tesseract(processed_image, page_number)

        except ImportError:
            logger.error(
                "pytesseract not installed. Install with: pip install pytesseract"
            )
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")

        result.extraction_time_ms = int((time.time() - start_time) * 1000)
        return result

    def _run_tesseract(
        self,
        image: Image.Image,
        page_number: int = 1,
    ) -> ExtractedText:
        """
        Run Tesseract OCR and get text with confidence scores.

        Uses Tesseract's detailed output mode which gives:
        - Text for each word
        - Confidence score for each word
        - Bounding box for each word
        """
        import pytesseract

        result = ExtractedText(method="tesseract")

        # Get detailed OCR data (word-level with confidence and bounding boxes)
        # OEM 3 = Default, PSM configured in __init__
        custom_config = f"--oem 3 --psm {self.tesseract_psm}"

        try:
            # Get word-level data with confidence
            ocr_data = pytesseract.image_to_data(
                image,
                lang=self.tesseract_lang,
                config=custom_config,
                output_type=pytesseract.Output.DICT,
            )

            text_blocks = []
            full_text_parts = []
            confidences = []
            current_line = []
            current_line_num = -1

            n_words = len(ocr_data["text"])
            for i in range(n_words):
                word = ocr_data["text"][i].strip()
                conf = int(ocr_data["conf"][i])
                line_num = ocr_data["line_num"][i]

                # Skip empty words and very low confidence
                if not word or conf < 0:
                    continue

                # Track line breaks for full text reconstruction
                if line_num != current_line_num:
                    if current_line:
                        full_text_parts.append(" ".join(current_line))
                    current_line = []
                    current_line_num = line_num

                current_line.append(word)
                confidences.append(conf)

                # Create text block with position
                block = TextBlock(
                    text=word,
                    confidence=float(conf),
                    bbox=(
                        ocr_data["left"][i],
                        ocr_data["top"][i],
                        ocr_data["left"][i] + ocr_data["width"][i],
                        ocr_data["top"][i] + ocr_data["height"][i],
                    ),
                    page_number=page_number,
                )
                text_blocks.append(block)

            # Don't forget the last line
            if current_line:
                full_text_parts.append(" ".join(current_line))

            result.full_text = "\n".join(full_text_parts)
            result.text_blocks = text_blocks
            result.avg_confidence = (
                sum(confidences) / len(confidences) if confidences else 0.0
            )

            logger.info(
                f"Tesseract OCR: {len(result.full_text)} chars, "
                f"{len(text_blocks)} words, avg confidence: {result.avg_confidence:.0f}%"
            )

        except Exception as e:
            logger.error(f"Tesseract detailed extraction failed: {e}")
            # Fallback: simple text extraction
            try:
                result.full_text = pytesseract.image_to_string(
                    image,
                    lang=self.tesseract_lang,
                    config=custom_config,
                )
                result.avg_confidence = 50.0
                logger.info("Tesseract fallback (simple mode) succeeded")
            except Exception as e2:
                logger.error(f"Tesseract simple extraction also failed: {e2}")

        return result

    # =========================================================================
    # IMAGE PREPROCESSING FOR OCR
    # =========================================================================

    def _preprocess_for_ocr(self, image: Image.Image) -> Image.Image:
        """
        Preprocess an image to improve OCR accuracy.

        Steps applied:
        1. Resize if too small (upscale for better OCR)
        2. Convert to grayscale
        3. Enhance contrast
        4. Sharpen
        5. Light denoising
        6. Binarize (adaptive threshold)

        These steps can improve OCR accuracy by 10-30% on poor quality images.

        Args:
            image: Original PIL Image (RGB).

        Returns:
            Preprocessed PIL Image (RGB, ready for Tesseract).
        """
        # Step 1: Ensure minimum size (Tesseract works best on larger images)
        w, h = image.size
        min_dimension = 1000
        if w < min_dimension or h < min_dimension:
            scale = max(min_dimension / w, min_dimension / h)
            new_w = int(w * scale)
            new_h = int(h * scale)
            image = image.resize((new_w, new_h), Image.LANCZOS)
            logger.debug(f"Upscaled image from {w}x{h} to {new_w}x{new_h}")

        # Step 2: Enhance contrast (makes text stand out from background)
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.5)

        # Step 3: Sharpen (makes text edges clearer)
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(1.5)

        # Step 4: Light denoising (remove speckles without blurring text)
        image = image.filter(ImageFilter.MedianFilter(size=3))

        # Step 5: Adaptive binarization using numpy
        # Convert to grayscale numpy array
        img_array = np.array(image.convert("L"))

        # Apply adaptive threshold:
        # For each pixel, compare to local mean in a window
        # If darker than mean → black, else → white
        window_size = 25  # Size of local neighborhood
        # Pad the array to handle edges
        padded = np.pad(img_array, window_size // 2, mode='edge')

        # Calculate local mean using a sliding window (efficient approach)
        # We use cumulative sum for O(n) computation
        cumsum = np.cumsum(np.cumsum(padded.astype(np.float64), axis=0), axis=1)

        h, w = img_array.shape
        # Calculate local means
        y1 = np.arange(h)
        y2 = y1 + window_size
        x1 = np.arange(w)
        x2 = x1 + window_size

        # Use integral image for fast local mean computation
        local_sum = (
            cumsum[np.ix_(y2, x2)]
            - cumsum[np.ix_(y1, x2)]
            - cumsum[np.ix_(y2, x1)]
            + cumsum[np.ix_(y1, x1)]
        )
        local_mean = local_sum / (window_size * window_size)

        # Binarize: pixel is white if it's brighter than local mean - offset
        offset = 10  # Small offset to avoid noise
        binary = ((img_array > (local_mean - offset)) * 255).astype(np.uint8)

        # Convert back to RGB PIL Image (Tesseract can handle both, but
        # we keep RGB for consistency with the rest of the pipeline)
        result = Image.fromarray(binary).convert("RGB")

        return result

    # =========================================================================
    # COMBINED EXTRACTION
    # =========================================================================

    def extract(
        self,
        document_type: str,
        pdfplumber_doc: Any = None,
        images: List[Image.Image] = None,
        page_numbers: Optional[List[int]] = None,
    ) -> ExtractedText:
        """
        High-level extraction that chooses the best method automatically.

        For digital PDFs: uses pdfplumber (text + tables).
        For images/scans: uses Tesseract OCR on each page.

        Args:
            document_type: "digital_pdf", "scanned_pdf", or "image".
            pdfplumber_doc: Open pdfplumber document (for digital PDFs).
            images: List of PIL Images (for OCR).
            page_numbers: Which pages to process (0-indexed).

        Returns:
            Combined ExtractedText from all pages.
        """
        if document_type == "digital_pdf" and pdfplumber_doc is not None:
            # Digital PDF → pdfplumber (perfect text)
            result = self.extract_from_digital_pdf(pdfplumber_doc, page_numbers)

            # If pdfplumber returned very little text, fall back to OCR
            if len(result.full_text.strip()) < 50 and images:
                logger.warning(
                    "pdfplumber returned little text, supplementing with OCR"
                )
                ocr_result = self._extract_all_images(images, page_numbers)
                # Merge: keep pdfplumber tables, add OCR text if richer
                if len(ocr_result.full_text) > len(result.full_text):
                    result.full_text = ocr_result.full_text
                    result.text_blocks = ocr_result.text_blocks
                    result.avg_confidence = ocr_result.avg_confidence
                    result.method = "pdfplumber+tesseract"

            return result

        elif images:
            # Image/Scanned PDF → Tesseract OCR
            return self._extract_all_images(images, page_numbers)

        else:
            logger.error("No extraction source provided")
            return ExtractedText()

    def _extract_all_images(
        self,
        images: List[Image.Image],
        page_numbers: Optional[List[int]] = None,
    ) -> ExtractedText:
        """Run OCR on all provided images and combine results."""
        if page_numbers is None:
            page_numbers = list(range(len(images)))

        combined = ExtractedText(method="tesseract")
        all_text_parts = []
        all_blocks = []
        all_confidences = []

        for page_idx in page_numbers:
            if page_idx >= len(images):
                continue

            page_result = self.extract_from_image(
                images[page_idx],
                page_number=page_idx + 1,
            )

            if page_result.full_text.strip():
                all_text_parts.append(page_result.full_text)
            all_blocks.extend(page_result.text_blocks)
            if page_result.avg_confidence > 0:
                all_confidences.append(page_result.avg_confidence)

        combined.full_text = "\n\n".join(all_text_parts)
        combined.text_blocks = all_blocks
        combined.avg_confidence = (
            sum(all_confidences) / len(all_confidences)
            if all_confidences else 0.0
        )

        return combined
