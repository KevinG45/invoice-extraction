"""
Extraction Result Data Class.

This module defines the data structure for invoice extraction results,
providing a standardized format for extracted fields.

Author: ML Engineering Team
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import json
from datetime import datetime


@dataclass
class ExtractionResult:
    """
    Represents the result of invoice field extraction.
    
    This class holds all extracted invoice header fields along with
    metadata about the extraction process.
    
    Attributes:
        invoice_number: Unique invoice identifier
        invoice_date: Date the invoice was issued
        vendor_name: Name of the seller/vendor
        customer_name: Name of the buyer/customer
        total_amount: Total amount due
        payment_due_date: Payment due date
        confidence_scores: Confidence for each field (0-1)
        raw_extractions: Original model outputs before processing
        source_file: Source filename
        extraction_timestamp: When extraction was performed
        model_name: Name of the model used
        success: Whether extraction was successful
        errors: List of errors encountered
        
    Example:
        >>> result = ExtractionResult(
        ...     invoice_number="INV-2026-001",
        ...     invoice_date="2026-01-21",
        ...     vendor_name="ABC Corp",
        ...     total_amount="1500.00"
        ... )
        >>> print(result.to_json())
    """
    # Core invoice fields
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    vendor_name: Optional[str] = None
    customer_name: Optional[str] = None
    total_amount: Optional[str] = None
    payment_due_date: Optional[str] = None
    
    # Confidence scores for each field (0.0 to 1.0)
    confidence_scores: Dict[str, float] = field(default_factory=dict)
    
    # Raw model outputs (before post-processing)
    raw_extractions: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    source_file: Optional[str] = None
    extraction_timestamp: Optional[str] = None
    model_name: Optional[str] = None
    processing_time: float = 0.0
    
    # Status
    success: bool = True
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    
    def __post_init__(self):
        """Initialize timestamp if not provided."""
        if self.extraction_timestamp is None:
            self.extraction_timestamp = datetime.now().isoformat()
    
    @property
    def fields(self) -> Dict[str, Optional[str]]:
        """
        Get all extracted fields as a dictionary.
        
        Returns:
            Dictionary of field names to values.
        """
        return {
            'invoice_number': self.invoice_number,
            'invoice_date': self.invoice_date,
            'vendor_name': self.vendor_name,
            'customer_name': self.customer_name,
            'total_amount': self.total_amount,
            'payment_due_date': self.payment_due_date
        }
    
    @property
    def missing_fields(self) -> list:
        """
        Get list of fields that were not extracted.
        
        Returns:
            List of missing field names.
        """
        return [k for k, v in self.fields.items() if v is None or v == ""]
    
    @property
    def extracted_fields(self) -> Dict[str, str]:
        """
        Get only fields that have values.
        
        Returns:
            Dictionary of extracted field names to values.
        """
        return {k: v for k, v in self.fields.items() if v is not None and v != ""}
    
    @property
    def extraction_rate(self) -> float:
        """
        Calculate the percentage of fields successfully extracted.
        
        Returns:
            Extraction rate as a percentage (0-100).
        """
        total = len(self.fields)
        extracted = len(self.extracted_fields)
        return (extracted / total) * 100 if total > 0 else 0
    
    @property
    def average_confidence(self) -> float:
        """
        Calculate average confidence across extracted fields.
        
        Returns:
            Average confidence score (0-1).
        """
        if not self.confidence_scores:
            return 0.0
        
        # Only consider fields that were extracted
        relevant_scores = [
            self.confidence_scores.get(field, 0)
            for field in self.extracted_fields.keys()
            if field in self.confidence_scores
        ]
        
        if not relevant_scores:
            return 0.0
        
        return sum(relevant_scores) / len(relevant_scores)
    
    def get_confidence(self, field_name: str) -> float:
        """
        Get confidence score for a specific field.
        
        Args:
            field_name: Name of the field.
            
        Returns:
            Confidence score (0-1) or 0 if not available.
        """
        return self.confidence_scores.get(field_name, 0.0)
    
    def set_field(self, field_name: str, value: str, confidence: float = 0.0) -> None:
        """
        Set a field value with optional confidence.
        
        Args:
            field_name: Name of the field.
            value: Extracted value.
            confidence: Confidence score (0-1).
        """
        if hasattr(self, field_name):
            setattr(self, field_name, value)
            if confidence > 0:
                self.confidence_scores[field_name] = confidence
    
    def add_error(self, error: str) -> None:
        """Add an error message."""
        self.errors.append(error)
        self.success = False
    
    def add_warning(self, warning: str) -> None:
        """Add a warning message."""
        self.warnings.append(warning)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary format.
        
        Returns:
            Dictionary representation of the extraction result.
        """
        return {
            'invoice_number': self.invoice_number,
            'invoice_date': self.invoice_date,
            'vendor_name': self.vendor_name,
            'customer_name': self.customer_name,
            'total_amount': self.total_amount,
            'payment_due_date': self.payment_due_date,
            'confidence_scores': self.confidence_scores,
            'source_file': self.source_file,
            'extraction_timestamp': self.extraction_timestamp,
            'model_name': self.model_name,
            'processing_time': self.processing_time,
            'success': self.success,
            'errors': self.errors,
            'warnings': self.warnings,
            'extraction_rate': self.extraction_rate,
            'average_confidence': self.average_confidence
        }
    
    def to_json(self, indent: int = 2) -> str:
        """
        Convert to JSON string.
        
        Args:
            indent: JSON indentation level.
            
        Returns:
            JSON string representation.
        """
        return json.dumps(self.to_dict(), indent=indent)
    
    def to_flat_dict(self) -> Dict[str, Any]:
        """
        Convert to flat dictionary suitable for database/Excel.
        
        Returns:
            Flat dictionary with no nested structures.
        """
        result = {
            'invoice_number': self.invoice_number or '',
            'invoice_date': self.invoice_date or '',
            'vendor_name': self.vendor_name or '',
            'customer_name': self.customer_name or '',
            'total_amount': self.total_amount or '',
            'payment_due_date': self.payment_due_date or '',
            'source_file': self.source_file or '',
            'extraction_timestamp': self.extraction_timestamp or '',
            'model_name': self.model_name or '',
            'processing_time': self.processing_time,
            'success': self.success,
            'extraction_rate': self.extraction_rate,
            'average_confidence': self.average_confidence
        }
        
        # Add individual confidence scores
        for field in self.fields.keys():
            result[f'{field}_confidence'] = self.confidence_scores.get(field, 0.0)
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExtractionResult':
        """
        Create ExtractionResult from dictionary.
        
        Args:
            data: Dictionary with extraction data.
            
        Returns:
            ExtractionResult instance.
        """
        return cls(
            invoice_number=data.get('invoice_number'),
            invoice_date=data.get('invoice_date'),
            vendor_name=data.get('vendor_name'),
            customer_name=data.get('customer_name'),
            total_amount=data.get('total_amount'),
            payment_due_date=data.get('payment_due_date'),
            confidence_scores=data.get('confidence_scores', {}),
            source_file=data.get('source_file'),
            extraction_timestamp=data.get('extraction_timestamp'),
            model_name=data.get('model_name'),
            processing_time=data.get('processing_time', 0.0),
            success=data.get('success', True),
            errors=data.get('errors', []),
            warnings=data.get('warnings', [])
        )
    
    def __repr__(self) -> str:
        return (
            f"ExtractionResult("
            f"invoice={self.invoice_number}, "
            f"vendor={self.vendor_name}, "
            f"total={self.total_amount}, "
            f"rate={self.extraction_rate:.0f}%)"
        )
