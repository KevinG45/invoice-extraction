"""
Field Extractor for Baseline Invoice Extraction.

Extracts header fields (invoice number, date, vendor, amounts, etc.)
from invoice text using a multi-strategy approach:

  STRATEGY 1: REGEX PATTERN MATCHING (Fast, High Accuracy for Structured Text)
    - Curated regex patterns for each field
    - Special patterns for Indian GST invoices (GSTIN, HSN codes)
    - Handles multiple date formats, currency symbols, etc.

  STRATEGY 2: LAYOUTLM DOCUMENT QA (Semantic Understanding)
    - Uses the impira/layoutlm-document-qa model from HuggingFace
    - Asks questions like "What is the invoice number?" against the document
    - Understands document layout and context
    - ~400MB model, runs locally, free to use

  STRATEGY 3: MERGE (Combining Both)
    - If both strategies extract the same field, pick the higher confidence one
    - If they disagree, prefer regex for structured fields (numbers, dates)
    - Prefer LayoutLM for free-text fields (names, addresses)

WHY REGEX + ML MODEL:
  Regex is extremely accurate for well-structured fields like invoice numbers
  (e.g., "INV-2026-001"), dates ("15/01/2026"), and amounts ("₹1,234.56").
  But regex struggles with free-text fields like vendor names where the
  format varies wildly. LayoutLM complements by understanding the document's
  visual layout and semantic context.

FIELD DEFINITIONS (14 standard header fields):
  - invoice_number: Unique identifier for the invoice
  - invoice_date: When the invoice was issued
  - due_date: Payment deadline
  - vendor_name: Seller/supplier company name
  - vendor_address: Seller's address
  - vendor_email: Seller's email
  - vendor_phone: Seller's phone number
  - vendor_gstin: Seller's GST Identification Number (India)
  - customer_name: Buyer/client company name
  - customer_address: Buyer's address
  - customer_gstin: Buyer's GST ID (India)
  - subtotal: Total before tax
  - tax_amount: Tax amount (GST, VAT, etc.)
  - total_amount: Final total (subtotal + tax)

Author: ML Engineering Team
Date: 2026-02-19
Version: 3.0.0 (Baseline)
"""

import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

from src.baseline.result import InvoiceResult, HEADER_FIELD_NAMES

logger = logging.getLogger("invoice_extraction.baseline.field_extractor")


# =============================================================================
# REGEX PATTERNS FOR FIELD EXTRACTION
# =============================================================================
# Each field has a list of regex patterns, tried in order.
# The first match wins. Patterns are written to handle common invoice formats.
# Group 1 in each pattern captures the actual value.

FIELD_PATTERNS = {
    # =========================================================================
    # INVOICE NUMBER
    # Formats: INV-2026-001, GST/24/001, #12345, Bill No. 789
    # =========================================================================
    "invoice_number": [
        # "Invoice No" / "Invoice Number" / "Invoice #" followed by value
        r"(?:invoice\s*(?:no\.?|number|#|num\.?))\s*[:\-]?\s*([A-Za-z0-9][\w\-/\.#]{2,30})",
        # "Inv No" / "Inv #"
        r"(?:inv\.?\s*(?:no\.?|#))\s*[:\-]?\s*([A-Za-z0-9][\w\-/\.#]{2,30})",
        # "Bill No" / "Bill Number"
        r"(?:bill\s*(?:no\.?|number|#))\s*[:\-]?\s*([A-Za-z0-9][\w\-/\.#]{2,30})",
        # "Reference" / "Ref No"
        r"(?:ref(?:erence)?\s*(?:no\.?|#)?)\s*[:\-]?\s*([A-Za-z0-9][\w\-/\.#]{2,30})",
        # "Voucher No"
        r"(?:voucher\s*(?:no\.?|#))\s*[:\-]?\s*([A-Za-z0-9][\w\-/\.#]{2,30})",
    ],

    # =========================================================================
    # INVOICE DATE
    # Formats: 15/01/2026, 2026-01-15, January 15, 2026, 15-Jan-2026
    # =========================================================================
    "invoice_date": [
        # "Invoice Date" / "Date" / "Dated" followed by date
        r"(?:invoice\s*date|date\s*of\s*invoice|dated?)\s*[:\-]?\s*(\d{1,2}[\s/\-\.]\d{1,2}[\s/\-\.]\d{2,4})",
        # Date in "Month DD, YYYY" format
        r"(?:invoice\s*date|date)\s*[:\-]?\s*([A-Za-z]+\.?\s+\d{1,2},?\s+\d{4})",
        # Date in "DD-Mon-YYYY" format
        r"(?:invoice\s*date|date)\s*[:\-]?\s*(\d{1,2}[\s\-][A-Za-z]{3,9}[\s\-]\d{2,4})",
        # ISO format YYYY-MM-DD
        r"(?:invoice\s*date|date)\s*[:\-]?\s*(\d{4}[\-/]\d{2}[\-/]\d{2})",
        # Standalone date near top of document (DD/MM/YYYY or MM/DD/YYYY)
        r"(?:^|\n)\s*(?:date)\s*[:\-]?\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})",
    ],

    # =========================================================================
    # DUE DATE
    # =========================================================================
    "due_date": [
        r"(?:due\s*date|payment\s*due|pay\s*by|due\s*on)\s*[:\-]?\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})",
        r"(?:due\s*date|payment\s*due)\s*[:\-]?\s*([A-Za-z]+\.?\s+\d{1,2},?\s+\d{4})",
        r"(?:due\s*date|payment\s*due)\s*[:\-]?\s*(\d{1,2}[\s\-][A-Za-z]{3,9}[\s\-]\d{2,4})",
    ],

    # =========================================================================
    # VENDOR NAME (Seller / From / Company name)
    # This is tricky - usually appears at the top of the invoice
    # =========================================================================
    "vendor_name": [
        # Explicit label: "From:", "Vendor:", "Seller:", "Supplier:"
        r"(?:from|vendor|seller|supplier|sold\s*by|billed\s*by)\s*[:\-]?\s*(.+?)(?:\n|$)",
        # "Company Name:" or "Firm Name:"  
        r"(?:company\s*name|firm\s*name)\s*[:\-]?\s*(.+?)(?:\n|$)",
        # "M/s" prefix (common in Indian invoices)
        r"(?:M/s\.?\s*)(.+?)(?:\n|$)",
    ],

    # =========================================================================
    # VENDOR ADDRESS
    # =========================================================================
    "vendor_address": [
        r"(?:vendor\s*address|seller\s*address|from\s*address|our\s*address)\s*[:\-]?\s*(.+?)(?:\n\n|\n(?=[A-Z]))",
        r"(?:address)\s*[:\-]?\s*(.+?\d{6})(?:\n|$)",  # Indian PIN code
    ],

    # =========================================================================
    # VENDOR EMAIL
    # =========================================================================
    "vendor_email": [
        # Standard email pattern
        r"(?:email|e-mail|mail)\s*[:\-]?\s*([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})",
        # Standalone email on a line
        r"([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})",
    ],

    # =========================================================================
    # VENDOR PHONE
    # =========================================================================
    "vendor_phone": [
        # Labeled phone: "Phone:", "Tel:", "Mobile:", "Contact:"
        r"(?:phone|tel(?:ephone)?|mobile|contact|ph\.?)\s*[:\-]?\s*(\+?[\d\s\-\(\)]{8,20})",
        # Indian mobile number pattern: +91 XXXXX XXXXX
        r"(\+91[\s\-]?\d{5}[\s\-]?\d{5})",
    ],

    # =========================================================================
    # VENDOR GSTIN (Indian GST Identification Number)
    # Format: 2 digits (state) + 10 chars PAN + 1 digit + Z + 1 check digit
    # Example: 27AABCU9603R1ZM
    # =========================================================================
    "vendor_gstin": [
        # Labeled GSTIN
        r"(?:GSTIN|GST\s*(?:No\.?|IN|Number|Reg(?:istration)?\s*(?:No\.?)?))\s*[:\-]?\s*(\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9][Z][A-Z0-9])",
        # Standalone GSTIN pattern (15 characters)
        r"\b(\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9][Z][A-Z0-9])\b",
    ],

    # =========================================================================
    # CUSTOMER NAME (Buyer / Bill To / Ship To)
    # =========================================================================
    "customer_name": [
        r"(?:bill\s*to|sold\s*to|customer|buyer|ship\s*to|billed\s*to|invoice\s*to|consignee)\s*[:\-]?\s*(?:name\s*[:\-]?\s*)?(.+?)(?:\n|$)",
        r"(?:party\s*name|party)\s*[:\-]?\s*(.+?)(?:\n|$)",
        r"(?:client\s*name|client)\s*[:\-]?\s*(.+?)(?:\n|$)",
    ],

    # =========================================================================
    # CUSTOMER ADDRESS
    # =========================================================================
    "customer_address": [
        r"(?:bill\s*to|sold\s*to|customer|buyer|ship\s*to)\s*[:\-]?\s*(?:.*?\n)\s*(.+?\d{6})",
        r"(?:delivery\s*address|shipping\s*address)\s*[:\-]?\s*(.+?)(?:\n\n|$)",
    ],

    # =========================================================================
    # CUSTOMER GSTIN
    # =========================================================================
    "customer_gstin": [
        # After finding vendor GSTIN, the second GSTIN is usually the customer's
        # This is handled in _extract_second_gstin() as a post-processing step
    ],

    # =========================================================================
    # SUBTOTAL (Before tax)
    # =========================================================================
    "subtotal": [
        r"(?:sub\s*total|subtotal|taxable\s*(?:amount|value)|amount\s*before\s*tax)\s*[:\-]?\s*[\$€£¥₹]?\s*([\d,]+\.?\d*)",
        r"(?:basic\s*(?:amount|value))\s*[:\-]?\s*[\$€£¥₹]?\s*([\d,]+\.?\d*)",
    ],

    # =========================================================================
    # TAX AMOUNT (GST, VAT, Sales Tax, etc.)
    # =========================================================================
    "tax_amount": [
        # Total tax
        r"(?:total\s*tax|tax\s*total|total\s*gst|gst\s*total)\s*[:\-]?\s*[\$€£¥₹]?\s*([\d,]+\.?\d*)",
        # CGST + SGST (Indian GST: split into Central + State)
        # We'll handle this in post-processing by summing CGST + SGST
        r"(?:igst|integrated\s*gst)\s*[:\-]?\s*[\$€£¥₹]?\s*([\d,]+\.?\d*)",
        # Generic tax
        r"(?:tax\s*amount|vat|sales\s*tax|output\s*tax)\s*[:\-]?\s*[\$€£¥₹]?\s*([\d,]+\.?\d*)",
    ],

    # =========================================================================
    # TOTAL AMOUNT (Final total)
    # =========================================================================
    "total_amount": [
        # Explicit "Grand Total" or "Total Amount"
        r"(?:grand\s*total|total\s*amount|amount\s*(?:due|payable)|net\s*(?:amount|payable)|invoice\s*total)\s*[:\-]?\s*[\$€£¥₹]?\s*([\d,]+\.?\d*)",
        # "Balance Due"
        r"(?:balance\s*(?:due|amount))\s*[:\-]?\s*[\$€£¥₹]?\s*([\d,]+\.?\d*)",
        # "Total" at end of document (common)
        # Match "Total" but NOT "Subtotal" or "Sub Total"
        r"(?<![Ss]ub\s)(?:[Tt]otal)\s*[:\-]?\s*[\$€£¥₹]?\s*([\d,]+\.?\d*)",
        # "Amount in Words" nearby (Indian invoices often have this)
        r"(?:total\s*(?:in\s*words|amount\s*in\s*words))\s*[:\-]?\s*.*?[\$€£¥₹]?\s*([\d,]+\.?\d*)",
    ],
}


# =============================================================================
# FIELD EXTRACTOR CLASS
# =============================================================================

class FieldExtractor:
    """
    Extracts header fields from invoice text.

    Usage:
        extractor = FieldExtractor()
        result = InvoiceResult()
        extractor.extract_fields(result, full_text="Invoice No: INV-001...", image=pil_image)
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {}
        # Whether to use LayoutLM model for QA extraction
        self.use_layoutlm = config.get("use_layoutlm", True)
        # LayoutLM model reference (loaded lazily)
        self._layoutlm_pipeline = None
        self._layoutlm_available = None

    # =========================================================================
    # MAIN EXTRACTION METHOD
    # =========================================================================

    def extract_fields(
        self,
        result: InvoiceResult,
        full_text: str,
        image: Optional[Image.Image] = None,
    ) -> None:
        """
        Extract all header fields from invoice text and image.

        Runs both regex and LayoutLM strategies, then merges results.
        Higher confidence wins when both strategies find the same field.

        Args:
            result: InvoiceResult to populate with extracted fields.
            full_text: Full text of the invoice (from pdfplumber or OCR).
            image: Optional PIL Image (for LayoutLM QA extraction).
        """
        start_time = time.time()

        # Strategy 1: Regex Pattern Matching
        logger.info("Running regex field extraction...")
        self._extract_with_regex(result, full_text)

        # Special handling: extract GSTIN pairs (vendor + customer)
        self._extract_gstin_pair(result, full_text)

        # Special handling: extract CGST + SGST as total tax
        self._extract_gst_components(result, full_text)

        # Strategy 2: LayoutLM Document QA (if image available)
        if image is not None and self.use_layoutlm:
            logger.info("Running LayoutLM Document QA extraction...")
            self._extract_with_layoutlm(result, image)

        # Calculate time
        extraction_time = int((time.time() - start_time) * 1000)
        result.metadata.field_extraction_time_ms = extraction_time

        # Log summary
        extracted_count = sum(
            1 for name in HEADER_FIELD_NAMES
            if name in result.headers and result.headers[name].value is not None
        )
        logger.info(
            f"Field extraction: {extracted_count}/{len(HEADER_FIELD_NAMES)} fields "
            f"found in {extraction_time}ms"
        )

    # =========================================================================
    # STRATEGY 1: REGEX EXTRACTION
    # =========================================================================

    def _extract_with_regex(self, result: InvoiceResult, full_text: str) -> None:
        """
        Extract fields using regex pattern matching.

        For each field, tries patterns in order. First match wins.
        Confidence is based on pattern specificity and context.
        """
        if not full_text.strip():
            return

        for field_name, patterns in FIELD_PATTERNS.items():
            for pattern in patterns:
                try:
                    match = re.search(pattern, full_text, re.IGNORECASE | re.MULTILINE)
                    if match:
                        value = match.group(1).strip()
                        if value:
                            # Clean up the value
                            value = self._clean_field_value(field_name, value)
                            if value:
                                # Assign confidence based on field type
                                confidence = self._regex_confidence(field_name, value, full_text)
                                result.set_header(
                                    field_name,
                                    value=value,
                                    confidence=confidence,
                                    source="regex",
                                    uncertain=(confidence < 70),
                                )
                                break  # Stop trying patterns for this field
                except re.error as e:
                    logger.debug(f"Regex error for {field_name}: {e}")

    def _clean_field_value(self, field_name: str, value: str) -> Optional[str]:
        """
        Clean up an extracted field value.

        Removes extra whitespace, trailing punctuation, etc.
        Returns None if the value is invalid after cleaning.
        """
        # Remove leading/trailing whitespace and common punctuation
        value = value.strip().rstrip(".,;:|")

        # For amount fields, clean and validate
        if field_name in ("subtotal", "tax_amount", "total_amount"):
            # Remove currency symbols
            value = re.sub(r"[\$€£¥₹]", "", value).strip()
            # Remove commas (thousands separators) and validate as number
            clean_value = value.replace(",", "")
            try:
                num = float(clean_value)
                if num <= 0:
                    return None
                return clean_value
            except ValueError:
                return None

        # For GSTIN, validate format
        if field_name in ("vendor_gstin", "customer_gstin"):
            if not re.match(r"^\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9][Z][A-Z0-9]$", value):
                return None

        # For email, validate format
        if field_name == "vendor_email":
            if not re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", value):
                return None

        # Remove very short values (likely noise)
        if len(value) < 2 and field_name not in ("subtotal", "tax_amount", "total_amount"):
            return None

        return value

    def _regex_confidence(self, field_name: str, value: str, full_text: str) -> float:
        """
        Calculate confidence score for a regex match.

        Confidence is based on:
        - Whether the value format matches expected patterns
        - Whether the match has clear label context
        - Length and specificity of the match
        """
        base_confidence = 75.0  # Regex matches are generally reliable

        # Boost for structured fields with clear formats
        if field_name == "invoice_number":
            # Invoice numbers with alphanumeric patterns are more reliable
            if re.match(r"^[A-Z]{2,}", value):
                base_confidence = 90.0
            elif re.match(r"^\d+$", value) and len(value) >= 3:
                base_confidence = 80.0

        elif field_name in ("invoice_date", "due_date"):
            # Date patterns are very reliable when matched
            base_confidence = 85.0

        elif field_name in ("vendor_gstin", "customer_gstin"):
            # GSTIN has a very specific 15-char format - highly reliable
            base_confidence = 95.0

        elif field_name == "vendor_email":
            base_confidence = 90.0

        elif field_name in ("subtotal", "tax_amount", "total_amount"):
            # Amount patterns are reliable but context matters
            base_confidence = 80.0
            # Boost if amount looks reasonable (not too small or too large)
            try:
                amount = float(value.replace(",", ""))
                if 1.0 <= amount <= 10000000.0:
                    base_confidence = 85.0
            except ValueError:
                base_confidence = 60.0

        elif field_name in ("vendor_name", "customer_name"):
            # Names are trickier - regex is less reliable here
            base_confidence = 65.0
            if len(value) > 5:
                base_confidence = 70.0

        return base_confidence

    def _extract_gstin_pair(self, result: InvoiceResult, full_text: str) -> None:
        """
        Extract GSTIN pair for vendor and customer.

        Indian GST invoices often have two GSTINs:
        - The first one is typically the vendor's
        - The second one (often under "Bill To") is the customer's
        """
        # Find ALL GSTIN numbers in the text
        gstin_pattern = r"\b(\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9][Z][A-Z0-9])\b"
        all_gstins = re.findall(gstin_pattern, full_text)

        if len(all_gstins) >= 1:
            # First GSTIN → vendor (if not already set)
            result.set_header(
                "vendor_gstin", all_gstins[0],
                confidence=92.0, source="regex",
            )

        if len(all_gstins) >= 2:
            # Second GSTIN → customer
            result.set_header(
                "customer_gstin", all_gstins[1],
                confidence=88.0, source="regex",
            )

    def _extract_gst_components(self, result: InvoiceResult, full_text: str) -> None:
        """
        Extract CGST + SGST tax components and sum them.

        Indian GST splits tax into:
        - CGST (Central GST) - typically 9%
        - SGST (State GST) - typically 9%
        OR
        - IGST (Integrated GST) - for inter-state, typically 18%

        If we find CGST + SGST, we sum them for total tax.
        """
        cgst_pattern = r"(?:CGST|C\.G\.S\.T)\s*.*?[\$€£¥₹]?\s*([\d,]+\.?\d*)"
        sgst_pattern = r"(?:SGST|S\.G\.S\.T)\s*.*?[\$€£¥₹]?\s*([\d,]+\.?\d*)"

        cgst_match = re.search(cgst_pattern, full_text, re.IGNORECASE)
        sgst_match = re.search(sgst_pattern, full_text, re.IGNORECASE)

        if cgst_match and sgst_match:
            try:
                cgst = float(cgst_match.group(1).replace(",", ""))
                sgst = float(sgst_match.group(1).replace(",", ""))
                total_tax = round(cgst + sgst, 2)

                # Only set if we don't already have a higher-confidence tax
                current_tax = result.get_header("tax_amount")
                if current_tax is None or current_tax.confidence < 85:
                    result.set_header(
                        "tax_amount",
                        value=str(total_tax),
                        confidence=88.0,
                        source="regex",
                    )
                    logger.debug(
                        f"Calculated tax from CGST({cgst}) + SGST({sgst}) = {total_tax}"
                    )
            except ValueError:
                pass

    # =========================================================================
    # STRATEGY 2: LAYOUTLM DOCUMENT QA EXTRACTION
    # =========================================================================

    def _extract_with_layoutlm(
        self,
        result: InvoiceResult,
        image: Image.Image,
    ) -> None:
        """
        Extract fields using LayoutLMv3 Document QA model.

        This model takes an image and a question, then finds the answer
        in the document. Example:
          Question: "What is the invoice number?"
          Answer: "INV-2026-001" (with score 0.95)

        The model understands document layout - it knows that the answer
        to "What is the total amount?" is likely near the bottom of the page,
        in a larger font, near the word "Total".
        """
        if not self._check_layoutlm_available():
            return

        # Questions to ask the model for each field
        # We only ask about fields that weren't already found with high confidence
        questions = {
            "invoice_number": "What is the invoice number?",
            "invoice_date": "What is the invoice date?",
            "due_date": "What is the payment due date?",
            "vendor_name": "What is the seller or vendor company name?",
            "customer_name": "What is the buyer or customer name?",
            "total_amount": "What is the total amount or grand total?",
            "subtotal": "What is the subtotal before tax?",
            "tax_amount": "What is the total tax amount?",
            "vendor_address": "What is the vendor or seller address?",
            "customer_address": "What is the buyer or customer address?",
            "vendor_email": "What is the email address?",
            "vendor_phone": "What is the phone number?",
        }

        for field_name, question in questions.items():
            # Skip if already found with high confidence
            existing = result.get_header(field_name)
            if existing and existing.confidence >= 85:
                continue

            try:
                answer, score = self._ask_layoutlm(image, question)
                if answer and score > 0.1:
                    # Scale score from [0,1] to [0,100]
                    confidence = min(95.0, score * 100)

                    # Clean the answer
                    clean_answer = self._clean_field_value(field_name, answer)
                    if clean_answer:
                        result.set_header(
                            field_name,
                            value=clean_answer,
                            confidence=confidence,
                            source="layoutlm",
                            uncertain=(confidence < 60),
                        )
                        logger.debug(
                            f"LayoutLM: {field_name} = '{clean_answer}' "
                            f"(score={score:.3f})"
                        )
            except Exception as e:
                logger.debug(f"LayoutLM failed for {field_name}: {e}")

    def _check_layoutlm_available(self) -> bool:
        """Check if LayoutLM model is available and load it."""
        if self._layoutlm_available is not None:
            return self._layoutlm_available

        try:
            from transformers import pipeline
            logger.info("Loading LayoutLMv3 Document QA model...")
            self._layoutlm_pipeline = pipeline(
                "document-question-answering",
                model="impira/layoutlm-document-qa",
            )
            self._layoutlm_available = True
            logger.info("LayoutLMv3 model loaded successfully")
            return True
        except ImportError:
            logger.warning("transformers not installed. LayoutLM unavailable.")
            self._layoutlm_available = False
            return False
        except Exception as e:
            logger.warning(f"LayoutLM model failed to load: {e}")
            self._layoutlm_available = False
            return False

    def _ask_layoutlm(
        self,
        image: Image.Image,
        question: str,
    ) -> Tuple[Optional[str], float]:
        """
        Ask the LayoutLM model a question about the document.

        Args:
            image: Document image.
            question: Question to ask (e.g., "What is the invoice number?").

        Returns:
            Tuple of (answer_text, confidence_score).
            answer_text is None if no answer found.
            confidence_score is between 0.0 and 1.0.
        """
        if self._layoutlm_pipeline is None:
            return None, 0.0

        try:
            # The pipeline expects an image and a question
            result = self._layoutlm_pipeline(
                image=image,
                question=question,
            )

            if result:
                # Result is a list of dicts with 'score' and 'answer'
                if isinstance(result, list):
                    best = result[0]
                else:
                    best = result

                answer = best.get("answer", "")
                score = best.get("score", 0.0)
                return answer, score

        except Exception as e:
            logger.debug(f"LayoutLM inference error: {e}")

        return None, 0.0


# =============================================================================
# STANDALONE HELPER: Extract fields from raw text (no model)
# =============================================================================

def extract_fields_regex_only(full_text: str) -> Dict[str, Tuple[str, float]]:
    """
    Quick regex-only field extraction. No ML model needed.

    Args:
        full_text: Full text of the invoice.

    Returns:
        Dictionary of field_name → (value, confidence) tuples.
    """
    results = {}
    for field_name, patterns in FIELD_PATTERNS.items():
        for pattern in patterns:
            try:
                match = re.search(pattern, full_text, re.IGNORECASE | re.MULTILINE)
                if match:
                    value = match.group(1).strip()
                    if value:
                        results[field_name] = (value, 75.0)
                        break
            except re.error:
                pass
    return results
