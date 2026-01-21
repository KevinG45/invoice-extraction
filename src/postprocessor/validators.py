"""
Data Validators Module.

This module provides validation functions for:
    - Date fields
    - Amount fields
    - General field validation

Author: ML Engineering Team
"""

import re
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

from config import get_config
from src.utils.logger import get_logger

# Initialize module logger
logger = get_logger(__name__)


class DateValidator:
    """
    Validates date fields.
    
    Checks for:
        - Valid date format
        - Reasonable date range
        - Logical date relationships (e.g., due date after invoice date)
    
    Example:
        >>> validator = DateValidator()
        >>> validator.is_valid("2026-01-15")
        True
        >>> validator.validate("invalid")
        (False, "Could not parse date")
    """
    
    # Reasonable date range for invoices
    MIN_YEAR = 2000
    MAX_YEAR = 2100
    
    def __init__(self) -> None:
        """Initialize the date validator."""
        self.date_format = get_config(
            "postprocessing.date.output_format",
            "%Y-%m-%d"
        )
        logger.debug("DateValidator initialized")
    
    def is_valid(self, date_str: str) -> bool:
        """
        Check if date string is valid.
        
        Args:
            date_str: Date string to validate.
            
        Returns:
            True if valid, False otherwise.
        """
        valid, _ = self.validate(date_str)
        return valid
    
    def validate(self, date_str: str) -> Tuple[bool, str]:
        """
        Validate a date string with detailed feedback.
        
        Args:
            date_str: Date string to validate.
            
        Returns:
            Tuple of (is_valid, message).
        """
        if not date_str:
            return False, "Date is empty"
        
        try:
            # Try to parse with expected format
            parsed = datetime.strptime(date_str, self.date_format)
            
            # Check year range
            if parsed.year < self.MIN_YEAR:
                return False, f"Year {parsed.year} is too old"
            if parsed.year > self.MAX_YEAR:
                return False, f"Year {parsed.year} is too far in future"
            
            return True, "Valid date"
            
        except ValueError as e:
            return False, f"Invalid date format: {str(e)}"
    
    def is_future_date(self, date_str: str) -> bool:
        """Check if date is in the future."""
        try:
            parsed = datetime.strptime(date_str, self.date_format)
            return parsed > datetime.now()
        except ValueError:
            return False
    
    def is_past_date(self, date_str: str) -> bool:
        """Check if date is in the past."""
        try:
            parsed = datetime.strptime(date_str, self.date_format)
            return parsed < datetime.now()
        except ValueError:
            return False
    
    def is_due_after_invoice(
        self,
        invoice_date: str,
        due_date: str
    ) -> Tuple[bool, str]:
        """
        Check if due date is after or equal to invoice date.
        
        Args:
            invoice_date: Invoice date string.
            due_date: Payment due date string.
            
        Returns:
            Tuple of (is_valid, message).
        """
        try:
            inv_parsed = datetime.strptime(invoice_date, self.date_format)
            due_parsed = datetime.strptime(due_date, self.date_format)
            
            if due_parsed < inv_parsed:
                return False, "Due date is before invoice date"
            
            return True, "Valid date relationship"
            
        except ValueError:
            return True, "Could not validate date relationship"


class AmountValidator:
    """
    Validates amount/currency fields.
    
    Checks for:
        - Valid numeric format
        - Reasonable value range
        - Non-negative values
    
    Example:
        >>> validator = AmountValidator()
        >>> validator.is_valid("1234.56")
        True
        >>> validator.validate("-100")
        (False, "Amount cannot be negative")
    """
    
    # Reasonable amount range
    MIN_AMOUNT = 0.0
    MAX_AMOUNT = 1_000_000_000  # 1 billion
    
    def __init__(self) -> None:
        """Initialize the amount validator."""
        logger.debug("AmountValidator initialized")
    
    def is_valid(self, amount_str: str) -> bool:
        """
        Check if amount string is valid.
        
        Args:
            amount_str: Amount string to validate.
            
        Returns:
            True if valid, False otherwise.
        """
        valid, _ = self.validate(amount_str)
        return valid
    
    def validate(self, amount_str: str) -> Tuple[bool, str]:
        """
        Validate an amount string with detailed feedback.
        
        Args:
            amount_str: Amount string to validate.
            
        Returns:
            Tuple of (is_valid, message).
        """
        if not amount_str:
            return False, "Amount is empty"
        
        try:
            value = float(amount_str)
            
            if value < self.MIN_AMOUNT:
                return False, "Amount cannot be negative"
            
            if value > self.MAX_AMOUNT:
                return False, f"Amount {value} exceeds maximum"
            
            return True, "Valid amount"
            
        except ValueError:
            return False, f"Could not parse amount: {amount_str}"
    
    def is_reasonable_total(self, amount: float) -> bool:
        """
        Check if amount is a reasonable invoice total.
        
        Args:
            amount: Amount value.
            
        Returns:
            True if reasonable, False otherwise.
        """
        # Most invoices are between $10 and $1 million
        return 10 <= amount <= 1_000_000


class FieldValidator:
    """
    General field validation for invoice data.
    
    Validates:
        - Required fields presence
        - Field format patterns
        - Cross-field validation
    
    Example:
        >>> validator = FieldValidator()
        >>> result = validator.validate_all(extraction_result)
        >>> print(result.is_valid)
        >>> print(result.errors)
    """
    
    def __init__(self) -> None:
        """Initialize the field validator."""
        self.required_fields = get_config(
            "postprocessing.validation.required_fields",
            ["invoice_number", "total_amount"]
        )
        self.confidence_threshold = get_config(
            "postprocessing.validation.confidence_threshold",
            0.5
        )
        
        # Initialize sub-validators
        self.date_validator = DateValidator()
        self.amount_validator = AmountValidator()
        
        logger.debug(f"FieldValidator initialized (required: {self.required_fields})")
    
    def validate_invoice_number(self, value: str) -> Tuple[bool, str]:
        """
        Validate invoice number format.
        
        Args:
            value: Invoice number to validate.
            
        Returns:
            Tuple of (is_valid, message).
        """
        if not value:
            return False, "Invoice number is empty"
        
        # Invoice numbers should have at least some alphanumeric content
        if len(value.strip()) < 2:
            return False, "Invoice number too short"
        
        # Check for at least one alphanumeric character
        if not re.search(r'[A-Za-z0-9]', value):
            return False, "Invoice number must contain alphanumeric characters"
        
        return True, "Valid invoice number"
    
    def validate_vendor_name(self, value: str) -> Tuple[bool, str]:
        """
        Validate vendor name.
        
        Args:
            value: Vendor name to validate.
            
        Returns:
            Tuple of (is_valid, message).
        """
        if not value:
            return False, "Vendor name is empty"
        
        if len(value.strip()) < 2:
            return False, "Vendor name too short"
        
        return True, "Valid vendor name"
    
    def validate_customer_name(self, value: str) -> Tuple[bool, str]:
        """
        Validate customer name.
        
        Args:
            value: Customer name to validate.
            
        Returns:
            Tuple of (is_valid, message).
        """
        if not value:
            return False, "Customer name is empty"
        
        if len(value.strip()) < 2:
            return False, "Customer name too short"
        
        return True, "Valid customer name"
    
    def validate_field(
        self,
        field_name: str,
        value: str
    ) -> Tuple[bool, str]:
        """
        Validate a specific field by name.
        
        Args:
            field_name: Name of the field.
            value: Field value to validate.
            
        Returns:
            Tuple of (is_valid, message).
        """
        validators = {
            'invoice_number': self.validate_invoice_number,
            'invoice_date': self.date_validator.validate,
            'vendor_name': self.validate_vendor_name,
            'customer_name': self.validate_customer_name,
            'total_amount': self.amount_validator.validate,
            'payment_due_date': self.date_validator.validate
        }
        
        validator = validators.get(field_name)
        if validator:
            return validator(value)
        
        # Default validation: just check not empty
        if value:
            return True, "Field has value"
        return False, "Field is empty"
    
    def check_required_fields(
        self,
        fields: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """
        Check if all required fields are present.
        
        Args:
            fields: Dictionary of field names to values.
            
        Returns:
            Tuple of (all_present, list of missing fields).
        """
        missing = []
        
        for required in self.required_fields:
            value = fields.get(required)
            if not value or str(value).strip() == "":
                missing.append(required)
        
        return len(missing) == 0, missing
    
    def check_confidence(
        self,
        confidence_scores: Dict[str, float]
    ) -> Tuple[bool, List[str]]:
        """
        Check if all fields meet confidence threshold.
        
        Args:
            confidence_scores: Dictionary of field names to confidence.
            
        Returns:
            Tuple of (all_pass, list of low confidence fields).
        """
        low_confidence = []
        
        for field, confidence in confidence_scores.items():
            if confidence < self.confidence_threshold:
                low_confidence.append(f"{field} ({confidence:.2f})")
        
        return len(low_confidence) == 0, low_confidence


class ValidationResult:
    """
    Contains the result of validation checks.
    
    Attributes:
        is_valid: Overall validation result
        errors: List of error messages
        warnings: List of warning messages
        field_results: Per-field validation results
    """
    
    def __init__(self):
        self.is_valid = True
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.field_results: Dict[str, Tuple[bool, str]] = {}
    
    def add_error(self, message: str) -> None:
        """Add an error and mark as invalid."""
        self.errors.append(message)
        self.is_valid = False
    
    def add_warning(self, message: str) -> None:
        """Add a warning (doesn't affect validity)."""
        self.warnings.append(message)
    
    def add_field_result(
        self,
        field: str,
        is_valid: bool,
        message: str
    ) -> None:
        """Add a field-level validation result."""
        self.field_results[field] = (is_valid, message)
        if not is_valid:
            self.add_error(f"{field}: {message}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'is_valid': self.is_valid,
            'errors': self.errors,
            'warnings': self.warnings,
            'field_results': self.field_results
        }
