"""
Base Extractor - Abstract interface for all 2026 model extractors.

Defines the common interface and data structures for extraction results
with confidence scores and validation metadata.

Author: ML Engineering Team
Version: 2.0.0
"""

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from PIL import Image

logger = logging.getLogger("invoice_extraction.models.base")


@dataclass
class FieldValue:
    """A single extracted field with confidence and metadata."""
    value: Any = None
    confidence: float = 0.0
    uncertain: bool = False
    verified: bool = False
    validation_method: str = ""
    source_model: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "confidence": self.confidence,
            "uncertain": self.uncertain,
            "verified": self.verified,
            "validation_method": self.validation_method,
            "source_model": self.source_model,
        }


@dataclass
class LineItemOutput:
    """A single line item extracted from an invoice."""
    line_number: int = 0
    item_code: FieldValue = field(default_factory=FieldValue)
    description: FieldValue = field(default_factory=FieldValue)
    quantity: FieldValue = field(default_factory=FieldValue)
    unit_price: FieldValue = field(default_factory=FieldValue)
    tax_rate: FieldValue = field(default_factory=FieldValue)
    tax_amount: FieldValue = field(default_factory=FieldValue)
    discount: FieldValue = field(default_factory=FieldValue)
    line_total: FieldValue = field(default_factory=FieldValue)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "line_number": self.line_number,
            "item_code": self.item_code.to_dict(),
            "description": self.description.to_dict(),
            "quantity": self.quantity.to_dict(),
            "unit_price": self.unit_price.to_dict(),
            "tax_rate": self.tax_rate.to_dict(),
            "tax_amount": self.tax_amount.to_dict(),
            "discount": self.discount.to_dict(),
            "line_total": self.line_total.to_dict(),
        }

    @property
    def calculated_total(self) -> Optional[float]:
        """Calculate line total from quantity * unit_price."""
        qty = self.quantity.value
        price = self.unit_price.value
        if qty is not None and price is not None:
            try:
                return round(float(qty) * float(price), 2)
            except (ValueError, TypeError):
                return None
        return None

    @property
    def is_valid(self) -> bool:
        """Check if line item has minimum required data."""
        has_description = (
            self.description.value is not None
            and str(self.description.value).strip()
        )
        has_financial = (
            self.quantity.value is not None
            or self.unit_price.value is not None
            or self.line_total.value is not None
        )
        return has_description or has_financial


@dataclass
class ExtractionOutput:
    """Complete extraction result from a 2026 model."""
    # Source information
    source_file: str = ""
    page_number: int = 1
    total_pages: int = 1

    # Model metadata
    model_name: str = ""
    model_version: str = ""
    extraction_timestamp: str = ""
    processing_time_seconds: float = 0.0

    # Header fields
    invoice_number: FieldValue = field(default_factory=FieldValue)
    invoice_date: FieldValue = field(default_factory=FieldValue)
    due_date: FieldValue = field(default_factory=FieldValue)
    vendor_name: FieldValue = field(default_factory=FieldValue)
    vendor_address: FieldValue = field(default_factory=FieldValue)
    vendor_email: FieldValue = field(default_factory=FieldValue)
    vendor_phone: FieldValue = field(default_factory=FieldValue)
    customer_name: FieldValue = field(default_factory=FieldValue)
    customer_address: FieldValue = field(default_factory=FieldValue)
    currency: FieldValue = field(default_factory=FieldValue)
    subtotal: FieldValue = field(default_factory=FieldValue)
    tax_amount: FieldValue = field(default_factory=FieldValue)
    shipping: FieldValue = field(default_factory=FieldValue)
    total_amount: FieldValue = field(default_factory=FieldValue)

    # Line items
    line_items: List[LineItemOutput] = field(default_factory=list)

    # Quality metadata
    image_quality_score: float = 0.0
    overall_confidence: float = 0.0
    hallucination_risk: float = 0.0

    # Errors and warnings
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # Raw model output
    raw_output: str = ""

    # Validation results (populated by validation framework)
    validation_results: Dict[str, Any] = field(default_factory=dict)

    HEADER_FIELDS = [
        "invoice_number", "invoice_date", "due_date",
        "vendor_name", "vendor_address", "vendor_email", "vendor_phone",
        "customer_name", "customer_address", "currency",
        "subtotal", "tax_amount", "shipping", "total_amount",
    ]

    def get_field(self, name: str) -> Optional[FieldValue]:
        """Get a header field by name."""
        if name in self.HEADER_FIELDS:
            return getattr(self, name, None)
        return None

    def set_field(self, name: str, field_value: FieldValue) -> None:
        """Set a header field by name."""
        if name in self.HEADER_FIELDS:
            setattr(self, name, field_value)

    @property
    def extracted_fields(self) -> Dict[str, FieldValue]:
        """Return all header fields that have non-null values."""
        result = {}
        for name in self.HEADER_FIELDS:
            fv = getattr(self, name)
            if fv.value is not None:
                result[name] = fv
        return result

    @property
    def missing_fields(self) -> List[str]:
        """Return names of fields with null values."""
        return [
            name for name in self.HEADER_FIELDS
            if getattr(self, name).value is None
        ]

    @property
    def extraction_rate(self) -> float:
        """Fraction of fields successfully extracted."""
        extracted = len(self.extracted_fields)
        total = len(self.HEADER_FIELDS)
        return extracted / total if total > 0 else 0.0

    @property
    def average_confidence(self) -> float:
        """Average confidence across all extracted fields."""
        fields = self.extracted_fields
        if not fields:
            return 0.0
        return sum(fv.confidence for fv in fields.values()) / len(fields)

    def calculate_overall_confidence(self) -> float:
        """Calculate and set overall confidence score."""
        header_conf = self.average_confidence
        if self.line_items:
            item_confs = []
            for item in self.line_items:
                for fv in [item.description, item.quantity, item.unit_price, item.line_total]:
                    if fv.value is not None:
                        item_confs.append(fv.confidence)
            item_conf = sum(item_confs) / len(item_confs) if item_confs else 0.0
            self.overall_confidence = (header_conf * 0.6 + item_conf * 0.4) / 100.0
        else:
            self.overall_confidence = header_conf / 100.0
        return self.overall_confidence

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with full metadata."""
        return {
            "metadata": {
                "source_file": self.source_file,
                "page_number": self.page_number,
                "total_pages": self.total_pages,
                "model_name": self.model_name,
                "model_version": self.model_version,
                "extraction_timestamp": self.extraction_timestamp,
                "processing_time_seconds": self.processing_time_seconds,
                "image_quality_score": self.image_quality_score,
                "overall_confidence": self.overall_confidence,
                "hallucination_risk": self.hallucination_risk,
                "extraction_rate": self.extraction_rate,
            },
            "header": {
                name: getattr(self, name).to_dict()
                for name in self.HEADER_FIELDS
            },
            "line_items": [item.to_dict() for item in self.line_items],
            "summary": {
                "subtotal": self.subtotal.to_dict(),
                "tax_total": self.tax_amount.to_dict(),
                "shipping": self.shipping.to_dict(),
                "total": self.total_amount.to_dict(),
            },
            "validation_report": self.validation_results,
            "errors": self.errors,
            "warnings": self.warnings,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def to_flat_dict(self) -> Dict[str, Any]:
        """Flatten to a single-level dict for DataFrame/CSV export."""
        flat = {
            "source_file": self.source_file,
            "page_number": self.page_number,
            "model_name": self.model_name,
            "extraction_timestamp": self.extraction_timestamp,
            "processing_time_seconds": self.processing_time_seconds,
            "image_quality_score": self.image_quality_score,
            "overall_confidence": self.overall_confidence,
            "hallucination_risk": self.hallucination_risk,
        }
        for name in self.HEADER_FIELDS:
            fv = getattr(self, name)
            flat[name] = fv.value
            flat[f"{name}_confidence"] = fv.confidence
            flat[f"{name}_verified"] = fv.verified
        return flat

    @classmethod
    def from_raw_json(cls, raw: Dict[str, Any], model_name: str = "") -> "ExtractionOutput":
        """Parse a raw JSON extraction result into an ExtractionOutput."""
        output = cls()
        output.model_name = model_name
        output.extraction_timestamp = datetime.now().isoformat()

        # Parse header
        header = raw.get("header", {})
        for field_name in cls.HEADER_FIELDS:
            if field_name in header:
                field_data = header[field_name]
                if isinstance(field_data, dict):
                    fv = FieldValue(
                        value=field_data.get("value"),
                        confidence=float(field_data.get("confidence", 0)),
                        uncertain=field_data.get("uncertain", False),
                        source_model=model_name,
                    )
                else:
                    fv = FieldValue(value=field_data, confidence=50.0, source_model=model_name)
                output.set_field(field_name, fv)

        # Parse line items
        items = raw.get("line_items", [])
        for i, item_data in enumerate(items):
            item = LineItemOutput(line_number=i + 1)
            for attr_name in ["item_code", "description", "quantity", "unit_price",
                              "tax_rate", "tax_amount", "discount", "line_total"]:
                if attr_name in item_data:
                    fd = item_data[attr_name]
                    if isinstance(fd, dict):
                        fv = FieldValue(
                            value=fd.get("value"),
                            confidence=float(fd.get("confidence", 0)),
                            uncertain=fd.get("uncertain", False),
                            source_model=model_name,
                        )
                    else:
                        fv = FieldValue(value=fd, confidence=50.0, source_model=model_name)
                    setattr(item, attr_name, fv)
            if item.is_valid:
                output.line_items.append(item)

        output.calculate_overall_confidence()
        return output


class BaseExtractor(ABC):
    """
    Abstract base class for all 2026 model extractors.

    Subclasses must implement:
    - extract(): Process an image and return ExtractionOutput
    - is_available(): Check if the model is loadable/accessible
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.model_name = config.get("model_name", self.__class__.__name__)
        self.logger = logging.getLogger(
            f"invoice_extraction.models.{self.__class__.__name__}"
        )
        self._loaded = False

    @abstractmethod
    def extract(self, image: Image.Image, **kwargs) -> ExtractionOutput:
        """
        Extract invoice data from an image.

        Args:
            image: PIL Image of the invoice page.
            **kwargs: Additional model-specific parameters.

        Returns:
            ExtractionOutput with all extracted fields and metadata.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this model is available and loadable."""
        pass

    def extract_batch(
        self, images: List[Image.Image], **kwargs
    ) -> List[ExtractionOutput]:
        """
        Extract from multiple images sequentially.

        Override in subclasses for batch-optimized processing.
        """
        results = []
        for i, image in enumerate(images):
            self.logger.info(f"Processing image {i + 1}/{len(images)}")
            result = self.extract(image, **kwargs)
            results.append(result)
        return results

    def answer_question(
        self, image: Image.Image, question: str
    ) -> Optional[str]:
        """
        Answer a specific question about an image (for Q-A-E validation).

        Override in subclasses that support VQA.
        """
        self.logger.warning(
            f"{self.model_name} does not support question answering"
        )
        return None

    def _create_output(self, **kwargs) -> ExtractionOutput:
        """Create an ExtractionOutput with default metadata."""
        output = ExtractionOutput(
            model_name=self.model_name,
            extraction_timestamp=datetime.now().isoformat(),
            **kwargs,
        )
        return output

    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse a JSON response from a model, handling common issues.

        Tries to extract JSON from markdown code blocks, partial JSON, etc.
        """
        text = response_text.strip()

        # Remove markdown code blocks
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to find JSON object in the text
        start_idx = text.find("{")
        if start_idx == -1:
            self.logger.error("No JSON object found in response")
            return {}

        # Find matching closing brace
        depth = 0
        end_idx = start_idx
        for i in range(start_idx, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    end_idx = i + 1
                    break

        try:
            return json.loads(text[start_idx:end_idx])
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON: {e}")
            return {}
