"""
Main Post-Processor Module.

This module provides the PostProcessor class that orchestrates
all post-processing operations on extracted invoice data.

Operations:
    - Normalize dates and amounts
    - Validate all fields
    - Handle missing fields
    - Clean and standardize data
    - Log all transformations

Author: ML Engineering Team
"""

from typing import Optional, Dict, Any, List
from copy import deepcopy

from config import get_config
from src.utils.logger import get_logger
from src.model_inference.extraction_result import ExtractionResult
from src.model_inference.line_item import LineItem
from .normalizers import DateNormalizer, AmountNormalizer
from .validators import FieldValidator, DateValidator, AmountValidator, ValidationResult

# Initialize module logger
logger = get_logger(__name__)


class PostProcessor:
    """
    Main post-processor for invoice extraction results.
    
    This class coordinates all post-processing operations including
    normalization, validation, and data cleaning.
    
    Attributes:
        date_normalizer: DateNormalizer instance
        amount_normalizer: AmountNormalizer instance
        field_validator: FieldValidator instance
        
    Example:
        >>> processor = PostProcessor()
        >>> cleaned_result = processor.process(extraction_result)
        >>> print(cleaned_result.invoice_date)  # Normalized date
        >>> print(cleaned_result.total_amount)  # Normalized amount
    """
    
    def __init__(self) -> None:
        """Initialize the post-processor with all sub-components."""
        # Initialize normalizers
        self.date_normalizer = DateNormalizer()
        self.amount_normalizer = AmountNormalizer()
        
        # Initialize validators
        self.field_validator = FieldValidator()
        self.date_validator = DateValidator()
        self.amount_validator = AmountValidator()
        
        # Load configuration
        self.flag_missing = get_config(
            "postprocessing.validation.flag_missing",
            True
        )
        self.required_fields = get_config(
            "postprocessing.validation.required_fields",
            ["invoice_number", "total_amount"]
        )
        
        logger.info("PostProcessor initialized")
    
    def process(self, result: ExtractionResult) -> ExtractionResult:
        """
        Process an extraction result with full normalization and validation.
        
        This is the main entry point for post-processing. It:
        1. Normalizes date fields
        2. Normalizes amount fields
        3. Validates all fields
        4. Handles missing fields
        5. Logs all transformations
        
        Args:
            result: ExtractionResult from model inference.
            
        Returns:
            Processed ExtractionResult with normalized data.
            
        Example:
            >>> processed = processor.process(raw_result)
            >>> if processed.success:
            ...     save_to_database(processed)
        """
        logger.info(f"Processing extraction result for: {result.source_file}")
        
        # Create a copy to avoid modifying the original
        processed = self._copy_result(result)
        
        # Step 1: Normalize dates
        processed = self._normalize_dates(processed)
        
        # Step 2: Normalize amounts
        processed = self._normalize_amounts(processed)
        
        # Step 3: Clean text fields
        processed = self._clean_text_fields(processed)
        
        # Step 4: Normalize line items (if present)
        processed = self._normalize_line_items(processed)
        
        # Step 5: Validate all fields
        validation = self._validate_all(processed)
        
        # Step 6: Handle missing required fields
        if self.flag_missing:
            self._handle_missing_fields(processed, validation)
        
        # Log summary
        self._log_processing_summary(result, processed, validation)
        
        return processed
    
    def _copy_result(self, result: ExtractionResult) -> ExtractionResult:
        """Create a deep copy of the extraction result, preserving type."""
        from src.model_inference.hybrid_extractor import HybridExtractionResult
        
        if isinstance(result, HybridExtractionResult):
            copied = HybridExtractionResult(
                source_file=result.source_file,
                model_name=result.model_name
            )
            # Copy line items and validation info
            copied.line_items = list(result.line_items) if result.line_items else []
            copied.total_validation = deepcopy(result.total_validation) if result.total_validation else {}
        else:
            copied = ExtractionResult(
                source_file=result.source_file,
                model_name=result.model_name
            )
        
        # Copy common fields
        copied.invoice_number = result.invoice_number
        copied.invoice_date = result.invoice_date
        copied.vendor_name = result.vendor_name
        copied.customer_name = result.customer_name
        copied.total_amount = result.total_amount
        copied.payment_due_date = result.payment_due_date
        copied.confidence_scores = deepcopy(result.confidence_scores)
        copied.raw_extractions = deepcopy(result.raw_extractions)
        copied.extraction_timestamp = result.extraction_timestamp
        copied.processing_time = result.processing_time
        copied.success = result.success
        copied.errors = list(result.errors)
        copied.warnings = list(result.warnings)
        
        return copied
    
    def _normalize_dates(self, result: ExtractionResult) -> ExtractionResult:
        """
        Normalize all date fields.
        
        Args:
            result: ExtractionResult to process.
            
        Returns:
            Result with normalized dates.
        """
        # Normalize invoice date
        if result.invoice_date:
            original = result.invoice_date
            normalized = self.date_normalizer.normalize(original)
            
            if normalized:
                result.invoice_date = normalized
                if normalized != original:
                    logger.debug(f"Normalized invoice_date: '{original}' -> '{normalized}'")
            else:
                result.add_warning(f"Could not normalize invoice_date: '{original}'")
        
        # Normalize payment due date
        if result.payment_due_date:
            original = result.payment_due_date
            normalized = self.date_normalizer.normalize(original)
            
            if normalized:
                result.payment_due_date = normalized
                if normalized != original:
                    logger.debug(f"Normalized payment_due_date: '{original}' -> '{normalized}'")
            else:
                result.add_warning(f"Could not normalize payment_due_date: '{original}'")
        
        return result
    
    def _normalize_amounts(self, result: ExtractionResult) -> ExtractionResult:
        """
        Normalize all amount fields.
        
        Args:
            result: ExtractionResult to process.
            
        Returns:
            Result with normalized amounts.
        """
        if result.total_amount:
            original = result.total_amount
            normalized = self.amount_normalizer.normalize(original)
            
            if normalized:
                result.total_amount = normalized
                if normalized != original:
                    logger.debug(f"Normalized total_amount: '{original}' -> '{normalized}'")
            else:
                result.add_warning(f"Could not normalize total_amount: '{original}'")
        
        return result
    
    def _normalize_line_items(self, result: ExtractionResult) -> ExtractionResult:
        """
        Normalize amounts and descriptions within line items.
        
        Args:
            result: ExtractionResult (potentially HybridExtractionResult).
            
        Returns:
            Result with normalized line items.
        """
        from src.model_inference.hybrid_extractor import HybridExtractionResult
        from decimal import Decimal, InvalidOperation
        
        if not isinstance(result, HybridExtractionResult):
            return result
        
        if not result.line_items:
            return result
        
        normalized_items = []
        for idx, item in enumerate(result.line_items):
            try:
                # Normalize unit_price
                if item.unit_price is not None:
                    raw_price = str(item.unit_price)
                    norm_price = self.amount_normalizer.normalize(raw_price)
                    if norm_price:
                        item.unit_price = Decimal(norm_price)
                
                # Normalize total
                if item.total is not None:
                    raw_total = str(item.total)
                    norm_total = self.amount_normalizer.normalize(raw_total)
                    if norm_total:
                        item.total = Decimal(norm_total)
                
                # Normalize tax_amount
                if item.tax_amount is not None:
                    raw_tax = str(item.tax_amount)
                    norm_tax = self.amount_normalizer.normalize(raw_tax)
                    if norm_tax:
                        item.tax_amount = Decimal(norm_tax)
                
                # Normalize discount
                if item.discount is not None:
                    raw_disc = str(item.discount)
                    norm_disc = self.amount_normalizer.normalize(raw_disc)
                    if norm_disc:
                        item.discount = Decimal(norm_disc)
                
                # Clean description text
                if item.description:
                    item.description = self._clean_text(item.description)
                
                # Recalculate total if missing but qty and unit_price exist
                if item.total is None and item.quantity is not None and item.unit_price is not None:
                    item.total = Decimal(str(item.quantity)) * item.unit_price
                    logger.debug(f"Calculated total for line item {idx}: {item.total}")
                
                normalized_items.append(item)
                
            except (InvalidOperation, ValueError, TypeError) as e:
                logger.warning(f"Error normalizing line item {idx}: {e}")
                normalized_items.append(item)  # Keep original on error
        
        result.line_items = normalized_items
        
        valid_count = sum(1 for item in normalized_items if item.is_valid)
        logger.info(
            f"Normalized {len(normalized_items)} line items "
            f"({valid_count} valid)"
        )
        
        return result
    
    def _clean_text_fields(self, result: ExtractionResult) -> ExtractionResult:
        """
        Clean text fields (vendor name, customer name, invoice number).
        
        Args:
            result: ExtractionResult to process.
            
        Returns:
            Result with cleaned text fields.
        """
        # Clean invoice number
        if result.invoice_number:
            result.invoice_number = self._clean_text(result.invoice_number)
        
        # Clean vendor name
        if result.vendor_name:
            result.vendor_name = self._clean_name(result.vendor_name)
        
        # Clean customer name
        if result.customer_name:
            result.customer_name = self._clean_name(result.customer_name)
        
        return result
    
    def _clean_text(self, text: str) -> str:
        """
        Clean a general text field.
        
        Args:
            text: Text to clean.
            
        Returns:
            Cleaned text.
        """
        if not text:
            return text
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        # Remove leading/trailing punctuation (except for invoice numbers)
        text = text.strip('.,;:')
        
        return text
    
    def _clean_name(self, name: str) -> str:
        """
        Clean a name field (vendor or customer).
        
        Args:
            name: Name to clean.
            
        Returns:
            Cleaned name.
        """
        if not name:
            return name
        
        # Remove extra whitespace
        name = ' '.join(name.split())
        
        # Remove common prefixes
        prefixes = ['vendor:', 'customer:', 'bill to:', 'ship to:', 'from:', 'to:']
        name_lower = name.lower()
        for prefix in prefixes:
            if name_lower.startswith(prefix):
                name = name[len(prefix):].strip()
                break
        
        # Proper case for names
        # Don't apply to all-caps company names that might be acronyms
        if name.isupper() and len(name) > 5:
            name = name.title()
        
        return name
    
    def _validate_all(self, result: ExtractionResult) -> ValidationResult:
        """
        Validate all fields in the result.
        
        Args:
            result: ExtractionResult to validate.
            
        Returns:
            ValidationResult with all validation outcomes.
        """
        validation = ValidationResult()
        
        # Validate each field
        for field_name, value in result.fields.items():
            if value:
                is_valid, message = self.field_validator.validate_field(field_name, value)
                validation.add_field_result(field_name, is_valid, message)
        
        # Check required fields
        all_present, missing = self.field_validator.check_required_fields(result.fields)
        if not all_present:
            for field in missing:
                validation.add_error(f"Required field missing: {field}")
        
        # Check confidence levels
        if result.confidence_scores:
            all_confident, low_conf = self.field_validator.check_confidence(
                result.confidence_scores
            )
            if not all_confident:
                for field_info in low_conf:
                    validation.add_warning(f"Low confidence: {field_info}")
        
        # Cross-validate dates
        if result.invoice_date and result.payment_due_date:
            is_valid, message = self.date_validator.is_due_after_invoice(
                result.invoice_date,
                result.payment_due_date
            )
            if not is_valid:
                validation.add_warning(message)
        
        return validation
    
    def _handle_missing_fields(
        self,
        result: ExtractionResult,
        validation: ValidationResult
    ) -> None:
        """
        Handle missing required fields.
        
        Args:
            result: ExtractionResult to update.
            validation: Validation result with missing field info.
        """
        _, missing = self.field_validator.check_required_fields(result.fields)
        
        for field in missing:
            result.add_warning(f"Missing required field: {field}")
    
    def _log_processing_summary(
        self,
        original: ExtractionResult,
        processed: ExtractionResult,
        validation: ValidationResult
    ) -> None:
        """
        Log a summary of processing operations.
        
        Args:
            original: Original extraction result.
            processed: Processed extraction result.
            validation: Validation results.
        """
        # Count changes
        changes = []
        
        if original.invoice_date != processed.invoice_date:
            changes.append("invoice_date")
        if original.total_amount != processed.total_amount:
            changes.append("total_amount")
        if original.payment_due_date != processed.payment_due_date:
            changes.append("payment_due_date")
        
        # Log summary
        logger.info(
            f"Post-processing complete: "
            f"{len(changes)} normalizations, "
            f"{len(validation.errors)} errors, "
            f"{len(validation.warnings)} warnings"
        )
        
        if validation.errors:
            for error in validation.errors:
                logger.warning(f"Validation error: {error}")
        
        if validation.warnings:
            for warning in validation.warnings[:5]:  # Limit logging
                logger.debug(f"Validation warning: {warning}")
    
    def normalize_date(self, date_str: str) -> Optional[str]:
        """
        Convenience method to normalize a single date.
        
        Args:
            date_str: Date string to normalize.
            
        Returns:
            Normalized date or None.
        """
        return self.date_normalizer.normalize(date_str)
    
    def normalize_amount(self, amount_str: str) -> Optional[str]:
        """
        Convenience method to normalize a single amount.
        
        Args:
            amount_str: Amount string to normalize.
            
        Returns:
            Normalized amount or None.
        """
        return self.amount_normalizer.normalize(amount_str)
    
    def validate_result(self, result: ExtractionResult) -> ValidationResult:
        """
        Validate an extraction result without modifying it.
        
        Args:
            result: ExtractionResult to validate.
            
        Returns:
            ValidationResult with validation outcomes.
        """
        return self._validate_all(result)
