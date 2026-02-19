"""
PaddleOCR-VL 1.5 Extractor - Fallback model for poor quality inputs.

Released: January 29, 2026
Benchmarks: 94.5% OmniDocBench v1.5
Strengths: 109 languages, seal recognition, skewed/warped scans, 0.9B ultra-compact

Author: ML Engineering Team
Version: 2.0.0
"""

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

from src.models.base_extractor import (
    BaseExtractor,
    ExtractionOutput,
    FieldValue,
    LineItemOutput,
)

logger = logging.getLogger("invoice_extraction.models.paddleocr_vl")


class PaddleOCRVLExtractor(BaseExtractor):
    """
    PaddleOCR-VL 1.5 extractor for challenging input conditions.

    Fallback model specialized for:
    - Poor quality scans (skewed, warped, blurry)
    - Stamped invoices (seal recognition built-in)
    - Mobile phone captures and screen photos
    - 109 languages (most comprehensive)
    - Ultra-lightweight (0.9B parameters)
    """

    MODEL_NAME = "paddleocr-vl-1.5"
    MODEL_VERSION = "2026.01"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.model_name = self.MODEL_NAME
        self.use_angle_cls = config.get("use_angle_cls", True)
        self.default_lang = config.get("default_lang", "en")
        self.use_gpu = config.get("use_gpu", True)
        self.show_log = config.get("show_log", False)
        self.enable_structure = config.get("enable_structure", True)

        self._ocr = None
        self._structure_engine = None

    def _load_model(self) -> bool:
        """Lazy-load PaddleOCR."""
        if self._ocr is not None:
            return True

        try:
            from paddleocr import PaddleOCR

            logger.info("Loading PaddleOCR-VL 1.5...")

            self._ocr = PaddleOCR(
                use_angle_cls=self.use_angle_cls,
                lang=self.default_lang,
                use_gpu=self.use_gpu,
                show_log=self.show_log,
            )

            # Load structure engine for table extraction
            if self.enable_structure:
                try:
                    from paddleocr import PPStructure
                    self._structure_engine = PPStructure(
                        show_log=self.show_log,
                        image_orientation=True,
                    )
                except Exception as e:
                    logger.warning(f"PPStructure not available: {e}")

            self._loaded = True
            logger.info("PaddleOCR-VL 1.5 loaded successfully")
            return True

        except ImportError:
            logger.error(
                "PaddleOCR not installed. Install with: pip install paddleocr>=3.0.0"
            )
            return False
        except Exception as e:
            logger.error(f"Failed to load PaddleOCR: {e}")
            return False

    def is_available(self) -> bool:
        """Check if PaddleOCR is available."""
        try:
            import paddleocr
            return True
        except ImportError:
            return False

    def extract(self, image: Image.Image, **kwargs) -> ExtractionOutput:
        """
        Extract invoice data using PaddleOCR-VL 1.5.

        Uses OCR text extraction + pattern matching for field identification.
        For tables, uses PPStructure engine.

        Args:
            image: PIL Image of the invoice.
            **kwargs: source_file, page_number, lang, etc.

        Returns:
            ExtractionOutput with extracted fields.
        """
        start_time = time.time()
        output = self._create_output(
            source_file=kwargs.get("source_file", ""),
            page_number=kwargs.get("page_number", 1),
            total_pages=kwargs.get("total_pages", 1),
            model_version=self.MODEL_VERSION,
        )

        if not self._load_model():
            output.errors.append("Failed to load PaddleOCR-VL 1.5")
            output.processing_time_seconds = time.time() - start_time
            return output

        try:
            import numpy as np

            # Convert PIL Image to numpy array
            img_array = np.array(image)

            # Run OCR
            lang = kwargs.get("lang", self.default_lang)
            ocr_result = self._ocr.ocr(img_array, cls=True)

            if not ocr_result or not ocr_result[0]:
                output.errors.append("PaddleOCR returned no results")
                output.processing_time_seconds = time.time() - start_time
                return output

            # Extract text lines with positions
            text_lines = self._parse_ocr_result(ocr_result[0])

            # Build full text for pattern matching
            full_text = "\n".join(line["text"] for line in text_lines)
            output.raw_output = full_text

            # Extract header fields using patterns
            self._extract_header_fields(text_lines, full_text, output)

            # Extract line items using structure engine or pattern matching
            if self._structure_engine:
                self._extract_line_items_structured(img_array, output)
            else:
                self._extract_line_items_pattern(text_lines, output)

        except Exception as e:
            logger.error(f"PaddleOCR extraction failed: {e}")
            output.errors.append(f"Extraction error: {str(e)}")

        output.processing_time_seconds = time.time() - start_time
        output.calculate_overall_confidence()
        return output

    def _parse_ocr_result(
        self, ocr_lines: List
    ) -> List[Dict[str, Any]]:
        """Parse PaddleOCR output into structured text lines."""
        text_lines = []
        for line in ocr_lines:
            if len(line) >= 2:
                bbox = line[0]
                text_info = line[1]
                text = text_info[0] if isinstance(text_info, (list, tuple)) else str(text_info)
                conf = float(text_info[1]) if isinstance(text_info, (list, tuple)) and len(text_info) > 1 else 0.5

                # Calculate bounding box center
                if bbox and len(bbox) >= 4:
                    y_center = (bbox[0][1] + bbox[2][1]) / 2
                    x_center = (bbox[0][0] + bbox[2][0]) / 2
                else:
                    y_center = 0
                    x_center = 0

                text_lines.append({
                    "text": text,
                    "confidence": conf,
                    "bbox": bbox,
                    "y_center": y_center,
                    "x_center": x_center,
                })

        # Sort by vertical position (top to bottom)
        text_lines.sort(key=lambda x: x["y_center"])
        return text_lines

    def _extract_header_fields(
        self,
        text_lines: List[Dict[str, Any]],
        full_text: str,
        output: ExtractionOutput,
    ) -> None:
        """Extract header fields using regex patterns on OCR text."""
        patterns = {
            "invoice_number": [
                r"(?:invoice\s*(?:no|number|#|num))[.:\s]*\s*([A-Z0-9][\w\-/\.#]*)",
                r"(?:inv\s*(?:no|#))[.:\s]*\s*([A-Z0-9][\w\-/\.#]*)",
                r"(?:bill\s*(?:no|number|#))[.:\s]*\s*([A-Z0-9][\w\-/\.#]*)",
                r"(?:reference\s*(?:no|#)?)[.:\s]*\s*([A-Z0-9][\w\-/\.#]*)",
            ],
            "invoice_date": [
                r"(?:invoice\s*date|date\s*of\s*invoice|dated?)[.:\s]*\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})",
                r"(?:invoice\s*date|date)[.:\s]*\s*(\w+\s+\d{1,2},?\s+\d{4})",
                r"(?:date)[.:\s]*\s*(\d{4}[/\-]\d{2}[/\-]\d{2})",
            ],
            "due_date": [
                r"(?:due\s*date|payment\s*due|pay\s*by)[.:\s]*\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})",
                r"(?:due\s*date|due)[.:\s]*\s*(\w+\s+\d{1,2},?\s+\d{4})",
            ],
            "total_amount": [
                r"(?:total\s*(?:amount|due)?|grand\s*total|amount\s*due|balance\s*due)[.:\s]*\s*[\$€£¥₹]?\s*([\d,]+\.?\d*)",
                r"(?:net\s*(?:amount|total))[.:\s]*\s*[\$€£¥₹]?\s*([\d,]+\.?\d*)",
            ],
            "subtotal": [
                r"(?:sub\s*total|subtotal)[.:\s]*\s*[\$€£¥₹]?\s*([\d,]+\.?\d*)",
            ],
            "tax_amount": [
                r"(?:tax|vat|gst|sales\s*tax)[.:\s]*\s*[\$€£¥₹]?\s*([\d,]+\.?\d*)",
            ],
            "shipping": [
                r"(?:shipping|delivery|freight)[.:\s]*\s*[\$€£¥₹]?\s*([\d,]+\.?\d*)",
            ],
            "vendor_name": [
                r"^(.+?)(?:\n|$)",  # First line often is vendor name
            ],
            "customer_name": [
                r"(?:bill\s*to|sold\s*to|customer|buyer|ship\s*to)[.:\s]*\s*(.+?)(?:\n|$)",
            ],
        }

        for field_name, field_patterns in patterns.items():
            for pattern in field_patterns:
                match = re.search(pattern, full_text, re.IGNORECASE | re.MULTILINE)
                if match:
                    value = match.group(1).strip()
                    if value:
                        # Find the confidence of the OCR line containing this value
                        conf = self._find_line_confidence(text_lines, value)
                        fv = FieldValue(
                            value=value,
                            confidence=conf * 100,
                            uncertain=conf < 0.85,
                            source_model=self.MODEL_NAME,
                        )
                        output.set_field(field_name, fv)
                        break

        # Currency detection
        currency_symbols = {"$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY", "₹": "INR"}
        for symbol, code in currency_symbols.items():
            if symbol in full_text:
                output.set_field("currency", FieldValue(
                    value=code, confidence=90.0, source_model=self.MODEL_NAME
                ))
                break

    def _find_line_confidence(
        self, text_lines: List[Dict[str, Any]], value: str
    ) -> float:
        """Find the OCR confidence for the line containing a value."""
        value_lower = value.lower()
        for line in text_lines:
            if value_lower in line["text"].lower():
                return line["confidence"]
        return 0.5

    def _extract_line_items_structured(
        self, img_array, output: ExtractionOutput
    ) -> None:
        """Extract line items using PPStructure table engine."""
        try:
            result = self._structure_engine(img_array)
            if not result:
                return

            for region in result:
                if region.get("type") == "table":
                    table_html = region.get("res", {}).get("html", "")
                    if table_html:
                        items = self._parse_table_html(table_html)
                        for i, item_data in enumerate(items):
                            item = LineItemOutput(line_number=i + 1)
                            for attr, value in item_data.items():
                                if hasattr(item, attr) and value is not None:
                                    fv = FieldValue(
                                        value=value,
                                        confidence=75.0,
                                        source_model=self.MODEL_NAME,
                                    )
                                    setattr(item, attr, fv)
                            if item.is_valid:
                                output.line_items.append(item)

        except Exception as e:
            logger.warning(f"Structured extraction failed: {e}")
            # Fall back to pattern-based extraction
            self._extract_line_items_pattern([], output)

    def _extract_line_items_pattern(
        self, text_lines: List[Dict[str, Any]], output: ExtractionOutput
    ) -> None:
        """Extract line items using pattern matching (fallback)."""
        # Pattern for line items: quantity, description, unit price, total
        pattern = re.compile(
            r"(\d+)\s+"           # quantity
            r"(.+?)\s+"           # description
            r"[\$€£]?\s*([\d,]+\.?\d*)\s+"  # unit price
            r"[\$€£]?\s*([\d,]+\.?\d*)",     # line total
            re.IGNORECASE
        )

        full_text = "\n".join(line["text"] for line in text_lines)
        matches = pattern.finditer(full_text)

        for i, match in enumerate(matches):
            item = LineItemOutput(line_number=i + 1)
            item.quantity = FieldValue(
                value=int(match.group(1)),
                confidence=60.0,
                uncertain=True,
                source_model=self.MODEL_NAME,
            )
            item.description = FieldValue(
                value=match.group(2).strip(),
                confidence=60.0,
                uncertain=True,
                source_model=self.MODEL_NAME,
            )
            item.unit_price = FieldValue(
                value=float(match.group(3).replace(",", "")),
                confidence=60.0,
                uncertain=True,
                source_model=self.MODEL_NAME,
            )
            item.line_total = FieldValue(
                value=float(match.group(4).replace(",", "")),
                confidence=60.0,
                uncertain=True,
                source_model=self.MODEL_NAME,
            )
            if item.is_valid:
                output.line_items.append(item)

    def _parse_table_html(self, html: str) -> List[Dict[str, Any]]:
        """Parse PPStructure HTML table output into line items."""
        items = []
        try:
            # Simple HTML table parser
            row_pattern = re.compile(r"<tr>(.*?)</tr>", re.DOTALL)
            cell_pattern = re.compile(r"<t[dh]>(.*?)</t[dh]>", re.DOTALL)

            rows = row_pattern.findall(html)
            if len(rows) < 2:
                return items

            # First row is likely header
            header_cells = cell_pattern.findall(rows[0])
            header_map = self._map_table_headers(header_cells)

            # Parse data rows
            for row_html in rows[1:]:
                cells = cell_pattern.findall(row_html)
                if not cells:
                    continue

                item_data = {}
                for col_idx, cell_text in enumerate(cells):
                    cell_text = cell_text.strip()
                    if col_idx in header_map:
                        field_name = header_map[col_idx]
                        # Try to convert numeric values
                        if field_name in ("quantity", "unit_price", "line_total", "tax_amount"):
                            try:
                                cell_text = float(cell_text.replace(",", "").replace("$", ""))
                            except ValueError:
                                pass
                        item_data[field_name] = cell_text

                if item_data:
                    items.append(item_data)

        except Exception as e:
            logger.warning(f"Table HTML parsing failed: {e}")

        return items

    def _map_table_headers(self, headers: List[str]) -> Dict[int, str]:
        """Map table column headers to field names."""
        header_map = {}
        header_patterns = {
            "description": r"desc|item|product|service|name",
            "quantity": r"qty|quantity|units|count|no\.",
            "unit_price": r"unit\s*price|rate|price|each|cost",
            "line_total": r"total|amount|extended|subtotal|line",
            "item_code": r"code|sku|item\s*(?:no|#)|product\s*code",
            "tax_rate": r"tax\s*rate|vat\s*%",
            "tax_amount": r"tax|vat|gst",
            "discount": r"discount|disc",
        }

        for idx, header_text in enumerate(headers):
            header_clean = header_text.strip().lower()
            for field_name, pattern in header_patterns.items():
                if re.search(pattern, header_clean):
                    header_map[idx] = field_name
                    break

        return header_map
