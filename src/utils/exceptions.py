"""
Custom Exceptions Module.

This module defines all custom exceptions used throughout the invoice
extraction system. Using specific exceptions allows for better error
handling and more informative error messages.

Exception Hierarchy:
    InvoiceExtractionError (base)
    ├── InputError
    │   ├── UnsupportedFileTypeError
    │   ├── FileNotFoundError
    │   └── CorruptedFileError
    ├── OCRError
    │   ├── OCREngineNotAvailableError
    │   └── OCRProcessingError
    ├── ModelError
    │   ├── ModelLoadError
    │   └── InferenceError
    ├── PostProcessingError
    │   └── ValidationError
    └── OutputError
        ├── DatabaseError
        └── ExcelExportError
"""


class InvoiceExtractionError(Exception):
    """
    Base exception for all invoice extraction errors.
    
    All custom exceptions in this system inherit from this class,
    allowing for easy catching of all system-specific errors.
    
    Attributes:
        message: Human-readable error message.
        details: Optional dictionary with additional error details.
    """
    
    def __init__(self, message: str, details: dict = None):
        """
        Initialize the exception.
        
        Args:
            message: Human-readable error message.
            details: Optional dictionary with additional context.
        """
        self.message = message
        self.details = details or {}
        super().__init__(self.message)
    
    def __str__(self) -> str:
        """Return string representation of the error."""
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


# =============================================================================
# INPUT ERRORS
# =============================================================================

class InputError(InvoiceExtractionError):
    """Base exception for input handling errors."""
    pass


class UnsupportedFileTypeError(InputError):
    """
    Raised when an unsupported file type is provided.
    
    Example:
        >>> raise UnsupportedFileTypeError(".doc", [".pdf", ".jpg"])
    """
    
    def __init__(self, file_type: str, supported_types: list):
        message = f"Unsupported file type: '{file_type}'"
        details = {"file_type": file_type, "supported_types": supported_types}
        super().__init__(message, details)


class FileNotFoundError(InputError):
    """Raised when input file cannot be found."""
    
    def __init__(self, filepath: str):
        message = f"File not found: {filepath}"
        details = {"filepath": filepath}
        super().__init__(message, details)


class CorruptedFileError(InputError):
    """Raised when a file appears to be corrupted or unreadable."""
    
    def __init__(self, filepath: str, reason: str = None):
        message = f"Corrupted or unreadable file: {filepath}"
        details = {"filepath": filepath, "reason": reason}
        super().__init__(message, details)


# =============================================================================
# OCR ERRORS
# =============================================================================

class OCRError(InvoiceExtractionError):
    """Base exception for OCR-related errors."""
    pass


class OCREngineNotAvailableError(OCRError):
    """Raised when the configured OCR engine is not available."""
    
    def __init__(self, engine_name: str):
        message = f"OCR engine not available: {engine_name}"
        details = {"engine": engine_name}
        super().__init__(message, details)


class OCRProcessingError(OCRError):
    """Raised when OCR processing fails."""
    
    def __init__(self, filepath: str, reason: str = None):
        message = f"OCR processing failed for: {filepath}"
        details = {"filepath": filepath, "reason": reason}
        super().__init__(message, details)


# =============================================================================
# MODEL ERRORS
# =============================================================================

class ModelError(InvoiceExtractionError):
    """Base exception for model-related errors."""
    pass


class ModelLoadError(ModelError):
    """Raised when model fails to load."""
    
    def __init__(self, model_name: str, reason: str = None):
        message = f"Failed to load model: {model_name}"
        details = {"model": model_name, "reason": reason}
        super().__init__(message, details)


class InferenceError(ModelError):
    """Raised when model inference fails."""
    
    def __init__(self, reason: str = None):
        message = "Model inference failed"
        details = {"reason": reason}
        super().__init__(message, details)


# =============================================================================
# POST-PROCESSING ERRORS
# =============================================================================

class PostProcessingError(InvoiceExtractionError):
    """Base exception for post-processing errors."""
    pass


class ValidationError(PostProcessingError):
    """Raised when data validation fails."""
    
    def __init__(self, field: str, value: str, reason: str = None):
        message = f"Validation failed for field '{field}'"
        details = {"field": field, "value": value, "reason": reason}
        super().__init__(message, details)


# =============================================================================
# OUTPUT ERRORS
# =============================================================================

class OutputError(InvoiceExtractionError):
    """Base exception for output handling errors."""
    pass


class DatabaseError(OutputError):
    """Raised when database operations fail."""
    
    def __init__(self, operation: str, reason: str = None):
        message = f"Database operation failed: {operation}"
        details = {"operation": operation, "reason": reason}
        super().__init__(message, details)


class ExcelExportError(OutputError):
    """Raised when Excel export fails."""
    
    def __init__(self, filepath: str, reason: str = None):
        message = f"Failed to export Excel file: {filepath}"
        details = {"filepath": filepath, "reason": reason}
        super().__init__(message, details)


# Export all exceptions
__all__ = [
    'InvoiceExtractionError',
    'InputError',
    'UnsupportedFileTypeError',
    'FileNotFoundError',
    'CorruptedFileError',
    'OCRError',
    'OCREngineNotAvailableError',
    'OCRProcessingError',
    'ModelError',
    'ModelLoadError',
    'InferenceError',
    'PostProcessingError',
    'ValidationError',
    'OutputError',
    'DatabaseError',
    'ExcelExportError',
]
