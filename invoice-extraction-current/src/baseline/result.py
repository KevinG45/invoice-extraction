"""
Result Data Structures for Baseline Invoice Extraction.

This module defines all the data classes used to represent extraction results.
Every extracted value carries a confidence score (0-100) and metadata about
how it was extracted, enabling downstream validation and quality assessment.

DATA FLOW:
  Raw text → Field Extraction → HeaderField / LineItem objects
  → Collected into InvoiceResult → Exported as JSON/Excel/CSV

GLOSSARY:
  - HeaderField: A single key-value pair from the invoice header
    (e.g., invoice_number = "INV-001", confidence = 95.0)
  - LineItem: A single row from the invoice's item table
    (e.g., description="Widget", qty=10, price=5.00, total=50.00)
  - InvoiceResult: The complete extraction for one invoice document
  - ExtractionMetadata: Processing info (time, method, quality scores)

Author: ML Engineering Team
Date: 2026-02-19
Version: 3.0.0 (Baseline)
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


# =============================================================================
# HEADER FIELD: A single extracted field with confidence and source info
# =============================================================================

@dataclass
class HeaderField:
    """
    Represents a single extracted header field from an invoice.

    Attributes:
        value: The extracted value (string, number, or None if not found).
        confidence: How confident we are in this extraction (0-100 scale).
            0   = not found / no confidence
            1-49 = low confidence (regex fallback, partial match)
            50-79 = medium confidence (OCR extraction, single source)
            80-100 = high confidence (multiple sources agree, exact match)
        source: How this value was extracted. One of:
            "pdfplumber" - Direct text extraction from digital PDF
            "tesseract"  - OCR extraction from image
            "regex"      - Pattern matching on extracted text
            "layoutlm"   - LayoutLMv3 Document QA model
            "merged"     - Combined from multiple sources
            "validated"  - Confirmed by cross-validation
        uncertain: Whether this field should be flagged for human review.
    """
    value: Any = None
    confidence: float = 0.0
    source: str = ""
    uncertain: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON export."""
        return {
            "value": self.value,
            "confidence": round(self.confidence, 1),
            "source": self.source,
            "uncertain": self.uncertain,
        }

    def __repr__(self) -> str:
        val_str = str(self.value)[:40] if self.value else "None"
        return f"HeaderField(value='{val_str}', conf={self.confidence:.0f}%, src='{self.source}')"


# =============================================================================
# LINE ITEM: A single row from the invoice's item table
# =============================================================================

@dataclass
class LineItem:
    """
    Represents one row from the invoice's line item table.

    A typical invoice table looks like:
    ┌────┬──────────────┬─────┬──────────┬──────────┐
    │ #  │ Description  │ Qty │ Price    │ Total    │
    ├────┼──────────────┼─────┼──────────┼──────────┤
    │ 1  │ Widget A     │ 10  │ 5.00     │ 50.00    │
    │ 2  │ Widget B     │ 5   │ 12.00    │ 60.00    │
    └────┴──────────────┴─────┴──────────┴──────────┘

    Fields:
        line_number: Row number in the table (1-indexed).
        item_code: Product/SKU code (e.g., "SKU-001").
        description: Item description text.
        hsn_sac: HSN/SAC code (Indian GST classification).
        quantity: Number of units.
        unit_price: Price per unit.
        discount: Discount amount for this line.
        tax_rate: Tax percentage (e.g., 18.0 for 18% GST).
        tax_amount: Tax amount in currency.
        line_total: Total for this line (qty × price - discount + tax).
        confidence: Average confidence across all fields in this line item.
    """
    line_number: int = 0
    item_code: Optional[str] = None
    description: Optional[str] = None
    hsn_sac: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    discount: Optional[float] = None
    tax_rate: Optional[float] = None
    tax_amount: Optional[float] = None
    line_total: Optional[float] = None
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON export."""
        return {
            "line_number": self.line_number,
            "item_code": self.item_code,
            "description": self.description,
            "hsn_sac": self.hsn_sac,
            "quantity": self.quantity,
            "unit_price": self.unit_price,
            "discount": self.discount,
            "tax_rate": self.tax_rate,
            "tax_amount": self.tax_amount,
            "line_total": self.line_total,
            "confidence": round(self.confidence, 1),
        }

    @property
    def is_valid(self) -> bool:
        """Check if this line item has minimum required data."""
        has_description = bool(self.description and str(self.description).strip())
        has_financial = (
            self.quantity is not None
            or self.unit_price is not None
            or self.line_total is not None
        )
        return has_description or has_financial

    @property
    def calculated_total(self) -> Optional[float]:
        """Calculate expected total: quantity × unit_price."""
        if self.quantity is not None and self.unit_price is not None:
            try:
                return round(float(self.quantity) * float(self.unit_price), 2)
            except (ValueError, TypeError):
                return None
        return None

    def __repr__(self) -> str:
        desc = (self.description[:30] + "...") if self.description and len(self.description) > 30 else self.description
        return (
            f"LineItem(#{self.line_number}, desc='{desc}', "
            f"qty={self.quantity}, price={self.unit_price}, total={self.line_total})"
        )


# =============================================================================
# EXTRACTION METADATA: Processing information
# =============================================================================

@dataclass
class ExtractionMetadata:
    """
    Processing metadata for an extraction run.

    Tracks how the document was processed, what methods were used,
    and timing information for performance analysis.
    """
    # Document info
    source_file: str = ""
    document_type: str = ""  # "digital_pdf", "scanned_pdf", "image"
    page_count: int = 1
    page_number: int = 1

    # Processing info
    text_extraction_method: str = ""  # "pdfplumber", "tesseract", "both"
    field_extraction_method: str = ""  # "regex", "layoutlm", "merged"
    table_extraction_method: str = ""  # "pdfplumber_table", "regex_table", "both"

    # Timing (in milliseconds)
    total_time_ms: int = 0
    total_extraction_time_ms: int = 0   # Alias used by pipeline
    text_extraction_time_ms: int = 0
    field_extraction_time_ms: int = 0
    table_extraction_time_ms: int = 0
    postprocessing_time_ms: int = 0

    # Quality metrics
    image_quality_score: float = 0.0
    ocr_confidence: float = 0.0
    average_text_confidence: float = 0.0  # Avg OCR confidence across text blocks
    extraction_timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON export."""
        return {
            "source_file": self.source_file,
            "document_type": self.document_type,
            "page_count": self.page_count,
            "page_number": self.page_number,
            "text_extraction_method": self.text_extraction_method,
            "field_extraction_method": self.field_extraction_method,
            "table_extraction_method": self.table_extraction_method,
            "total_time_ms": self.total_time_ms,
            "total_extraction_time_ms": self.total_extraction_time_ms,
            "text_extraction_time_ms": self.text_extraction_time_ms,
            "field_extraction_time_ms": self.field_extraction_time_ms,
            "table_extraction_time_ms": self.table_extraction_time_ms,
            "postprocessing_time_ms": self.postprocessing_time_ms,
            "image_quality_score": round(self.image_quality_score, 3),
            "ocr_confidence": round(self.ocr_confidence, 1),
            "average_text_confidence": round(self.average_text_confidence, 1),
            "extraction_timestamp": self.extraction_timestamp,
        }


# =============================================================================
# INVOICE RESULT: Complete extraction result for one invoice
# =============================================================================

# Header field names - the 14 standard fields we extract from every invoice.
# These are the "columns" in our output spreadsheet.
HEADER_FIELD_NAMES = [
    "invoice_number",    # e.g., "INV-2026-001" or "GST/24/001"
    "invoice_date",      # e.g., "2026-01-15" (normalized to YYYY-MM-DD)
    "due_date",          # e.g., "2026-02-15" (payment due date)
    "vendor_name",       # e.g., "ABC Supplies Ltd."
    "vendor_address",    # e.g., "123 Main St, Mumbai, MH 400001"
    "vendor_email",      # e.g., "sales@abc.com"
    "vendor_phone",      # e.g., "+91 9876543210"
    "vendor_gstin",      # e.g., "27AABCU9603R1ZM" (Indian GST ID)
    "customer_name",     # e.g., "XYZ Corporation"
    "customer_address",  # e.g., "456 Oak Ave, Delhi"
    "customer_gstin",    # e.g., "07AAACC1206D1ZM"
    "subtotal",          # e.g., 1000.00 (before tax)
    "tax_amount",        # e.g., 180.00 (GST/VAT amount)
    "total_amount",      # e.g., 1180.00 (final total)
]


@dataclass
class InvoiceResult:
    """
    Complete extraction result for a single invoice document.

    Contains all extracted header fields, all line items, metadata,
    and validation results. This is the main output object.

    Usage Example:
        result = InvoiceResult()
        result.set_header("invoice_number", "INV-001", confidence=95.0, source="regex")
        result.add_line_item(LineItem(description="Widget", quantity=10, ...))
        result.calculate_overall_confidence()
        json_data = result.to_dict()
    """

    # Header fields stored as name → HeaderField mapping
    headers: Dict[str, HeaderField] = field(default_factory=dict)

    # Line items extracted from the invoice table
    line_items: List[LineItem] = field(default_factory=list)

    # Processing metadata
    metadata: ExtractionMetadata = field(default_factory=ExtractionMetadata)

    # Overall quality scores
    overall_confidence: float = 0.0
    extraction_rate: float = 0.0  # Fraction of fields extracted (0.0 to 1.0)

    # Validation results
    validation_warnings: List[str] = field(default_factory=list)
    validation_results: Optional[List[Dict[str, str]]] = field(default_factory=list)
    validation_passed: bool = True

    # -------------------------------------------------------------------------
    # Header field access helpers
    # -------------------------------------------------------------------------

    def set_header(
        self,
        field_name: str,
        value: Any,
        confidence: float = 0.0,
        source: str = "",
        uncertain: bool = False,
    ) -> None:
        """
        Set a header field value with confidence and source info.

        Only updates if the new confidence is higher than existing,
        or if the field hasn't been set yet.

        Args:
            field_name: One of the 14 standard field names (see HEADER_FIELD_NAMES).
            value: The extracted value (string, float, or None).
            confidence: Confidence score 0-100.
            source: Extraction method ("regex", "pdfplumber", "layoutlm", etc).
            uncertain: Whether to flag for human review.
        """
        existing = self.headers.get(field_name)

        # Only update if new confidence is higher, or field is empty
        if existing is None or existing.value is None or confidence > existing.confidence:
            self.headers[field_name] = HeaderField(
                value=value,
                confidence=confidence,
                source=source,
                uncertain=uncertain,
            )

    def get_header(self, field_name: str) -> Optional[HeaderField]:
        """Get a header field by name. Returns None if not set."""
        return self.headers.get(field_name)

    def get_header_value(self, field_name: str) -> Any:
        """Get just the value of a header field. Returns None if not set."""
        hf = self.headers.get(field_name)
        return hf.value if hf else None

    # -------------------------------------------------------------------------
    # Line item helpers
    # -------------------------------------------------------------------------

    def add_line_item(self, item: LineItem) -> None:
        """Add a line item to the results."""
        if item.line_number == 0:
            item.line_number = len(self.line_items) + 1
        self.line_items.append(item)

    # -------------------------------------------------------------------------
    # Confidence & validation calculation
    # -------------------------------------------------------------------------

    def calculate_overall_confidence(self) -> float:
        """
        Calculate overall confidence as weighted average of all extracted fields.

        Header fields get 60% weight, line items get 40% weight.
        Returns a score from 0.0 to 100.0.
        """
        # Header confidence: average of all non-None fields
        header_confidences = [
            hf.confidence for hf in self.headers.values()
            if hf.value is not None
        ]
        header_avg = (
            sum(header_confidences) / len(header_confidences)
            if header_confidences else 0.0
        )

        # Line item confidence: average of all line items
        item_confidences = [
            item.confidence for item in self.line_items
            if item.is_valid
        ]
        item_avg = (
            sum(item_confidences) / len(item_confidences)
            if item_confidences else 0.0
        )

        # Weighted combination
        if self.line_items:
            self.overall_confidence = header_avg * 0.6 + item_avg * 0.4
        else:
            self.overall_confidence = header_avg

        # Calculate extraction rate: how many of the 14 fields were found
        extracted_count = sum(
            1 for name in HEADER_FIELD_NAMES
            if name in self.headers and self.headers[name].value is not None
        )
        self.extraction_rate = extracted_count / len(HEADER_FIELD_NAMES)

        return self.overall_confidence

    # -------------------------------------------------------------------------
    # Serialization
    # -------------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to a complete dictionary for JSON export.

        Structure:
        {
            "metadata": { ... },
            "headers": { "invoice_number": {"value": ..., "confidence": ...}, ... },
            "line_items": [ { "description": ..., "quantity": ..., ... }, ... ],
            "summary": { "overall_confidence": ..., "extraction_rate": ..., ... },
            "validation": { "passed": ..., "warnings": [...] }
        }
        """
        return {
            "metadata": self.metadata.to_dict(),
            "headers": {
                name: self.headers[name].to_dict() if name in self.headers else HeaderField().to_dict()
                for name in HEADER_FIELD_NAMES
            },
            "line_items": [item.to_dict() for item in self.line_items],
            "summary": {
                "overall_confidence": round(self.overall_confidence, 1),
                "extraction_rate": round(self.extraction_rate, 3),
                "fields_extracted": sum(
                    1 for n in HEADER_FIELD_NAMES
                    if n in self.headers and self.headers[n].value is not None
                ),
                "total_fields": len(HEADER_FIELD_NAMES),
                "line_items_count": len(self.line_items),
            },
            "validation": {
                "passed": self.validation_passed,
                "warnings": self.validation_warnings,
            },
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str, ensure_ascii=False)

    def to_flat_dict(self) -> Dict[str, Any]:
        """
        Flatten to a single-level dict for DataFrame/CSV export.

        Each header field becomes a column. Useful for creating
        a pandas DataFrame where each row = one invoice.
        """
        flat = {
            "source_file": self.metadata.source_file,
            "document_type": self.metadata.document_type,
            "page_number": self.metadata.page_number,
            "overall_confidence": round(self.overall_confidence, 1),
            "extraction_rate": round(self.extraction_rate, 3),
            "line_items_count": len(self.line_items),
        }
        for name in HEADER_FIELD_NAMES:
            hf = self.headers.get(name)
            flat[name] = hf.value if hf else None
            flat[f"{name}_confidence"] = round(hf.confidence, 1) if hf else 0.0
        return flat

    def __repr__(self) -> str:
        inv_num = self.get_header_value("invoice_number") or "N/A"
        n_fields = sum(
            1 for n in HEADER_FIELD_NAMES
            if n in self.headers and self.headers[n].value is not None
        )
        return (
            f"InvoiceResult(invoice='{inv_num}', "
            f"fields={n_fields}/{len(HEADER_FIELD_NAMES)}, "
            f"line_items={len(self.line_items)}, "
            f"confidence={self.overall_confidence:.1f}%)"
        )
