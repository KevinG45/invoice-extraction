"""
Data Normalizers Module.

This module provides normalization functions for:
    - Date formats
    - Currency/amount values
    - Text cleaning

Author: ML Engineering Team
"""

import re
from datetime import datetime
from typing import Optional, List, Tuple
from dateutil import parser as date_parser

from config import get_config
from src.utils.logger import get_logger

# Initialize module logger
logger = get_logger(__name__)


class DateNormalizer:
    """
    Normalizes date strings to a standard format.
    
    Handles various input date formats and converts them to
    ISO format (YYYY-MM-DD) or a configured output format.
    
    Attributes:
        output_format: Target date format string
        input_formats: List of recognized input format strings
        
    Example:
        >>> normalizer = DateNormalizer()
        >>> normalizer.normalize("01/15/2026")
        "2026-01-15"
        >>> normalizer.normalize("January 15, 2026")
        "2026-01-15"
    """
    
    # Common date patterns for extraction
    DATE_PATTERNS = [
        # MM/DD/YYYY or DD/MM/YYYY
        r'\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})\b',
        # YYYY-MM-DD
        r'\b(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})\b',
        # Month DD, YYYY
        r'\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{2,4})\b',
        # DD Month YYYY
        r'\b(\d{1,2})(?:st|nd|rd|th)?\s+((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*)\s+(\d{2,4})\b',
    ]
    
    def __init__(self) -> None:
        """Initialize the date normalizer with configuration."""
        self.output_format = get_config(
            "postprocessing.date.output_format", 
            "%Y-%m-%d"
        )
        self.input_formats = get_config(
            "postprocessing.date.input_formats",
            [
                "%m/%d/%Y",
                "%d/%m/%Y",
                "%Y-%m-%d",
                "%B %d, %Y",
                "%b %d, %Y",
                "%d %B %Y",
                "%d-%m-%Y",
                "%m-%d-%Y",
                "%d.%m.%Y"
            ]
        )
        
        logger.debug(f"DateNormalizer initialized (output: {self.output_format})")
    
    def normalize(self, date_str: str) -> Optional[str]:
        """
        Normalize a date string to the configured output format.
        
        Args:
            date_str: Input date string in any recognized format.
            
        Returns:
            Normalized date string, or None if parsing fails.
            
        Example:
            >>> normalizer.normalize("01/15/2026")
            "2026-01-15"
        """
        if not date_str:
            return None
        
        # Clean the input
        date_str = self._clean_date_string(date_str)
        
        # Try explicit formats first
        parsed_date = self._try_explicit_formats(date_str)
        
        # If explicit formats fail, try dateutil parser
        if parsed_date is None:
            parsed_date = self._try_dateutil_parser(date_str)
        
        # Format output
        if parsed_date:
            try:
                return parsed_date.strftime(self.output_format)
            except Exception as e:
                logger.debug(f"Date formatting failed: {e}")
                return None
        
        logger.debug(f"Could not parse date: {date_str}")
        return None
    
    def _clean_date_string(self, date_str: str) -> str:
        """
        Clean and prepare date string for parsing.
        
        Args:
            date_str: Raw date string.
            
        Returns:
            Cleaned date string.
        """
        # Remove extra whitespace
        date_str = ' '.join(date_str.split())
        
        # Remove common prefixes
        prefixes = ['date:', 'dated:', 'invoice date:', 'due date:', 'on']
        for prefix in prefixes:
            if date_str.lower().startswith(prefix):
                date_str = date_str[len(prefix):].strip()
        
        # Remove ordinal suffixes (1st, 2nd, 3rd, 4th, etc.)
        date_str = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str, flags=re.IGNORECASE)
        
        return date_str.strip()
    
    def _try_explicit_formats(self, date_str: str) -> Optional[datetime]:
        """
        Try to parse date using explicit format strings.
        
        Args:
            date_str: Date string to parse.
            
        Returns:
            Parsed datetime or None.
        """
        for fmt in self.input_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None
    
    def _try_dateutil_parser(self, date_str: str) -> Optional[datetime]:
        """
        Try to parse date using dateutil's fuzzy parser.
        
        Args:
            date_str: Date string to parse.
            
        Returns:
            Parsed datetime or None.
        """
        try:
            # Use dateutil parser with dayfirst=False (US format default)
            return date_parser.parse(date_str, dayfirst=False, fuzzy=True)
        except Exception:
            try:
                # Try with dayfirst=True (European format)
                return date_parser.parse(date_str, dayfirst=True, fuzzy=True)
            except Exception:
                return None
    
    def extract_date(self, text: str) -> Optional[str]:
        """
        Extract and normalize a date from text.
        
        Searches text for date patterns and normalizes the first match.
        
        Args:
            text: Text that may contain a date.
            
        Returns:
            Normalized date string or None.
        """
        for pattern in self.DATE_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_str = match.group(0)
                normalized = self.normalize(date_str)
                if normalized:
                    return normalized
        
        # Try normalizing the entire text
        return self.normalize(text)
    
    def is_valid_date(self, date_str: str) -> bool:
        """
        Check if a string represents a valid date.
        
        Args:
            date_str: String to validate.
            
        Returns:
            True if valid date, False otherwise.
        """
        return self.normalize(date_str) is not None


class AmountNormalizer:
    """
    Normalizes currency/amount strings to standard numeric format.
    
    Handles various currency symbols, thousand separators, and
    decimal formats.
    
    Attributes:
        currencies: List of recognized currency symbols
        decimal_separator: Character used as decimal separator
        output_format: Output format ('float' or 'string')
        
    Example:
        >>> normalizer = AmountNormalizer()
        >>> normalizer.normalize("$1,234.56")
        "1234.56"
        >>> normalizer.normalize("€ 1.234,56")
        "1234.56"
    """
    
    # Currency symbols and codes to remove
    CURRENCY_SYMBOLS = ['$', '€', '£', '¥', '₹', '₽', '₿', '฿', '₫', '₴', '₦']
    CURRENCY_CODES = ['USD', 'EUR', 'GBP', 'JPY', 'INR', 'CAD', 'AUD', 'CNY', 'RUB']
    
    def __init__(self) -> None:
        """Initialize the amount normalizer with configuration."""
        self.currencies = get_config(
            "postprocessing.amount.currencies",
            self.CURRENCY_SYMBOLS + self.CURRENCY_CODES
        )
        self.decimal_separator = get_config(
            "postprocessing.amount.decimal_separator",
            "."
        )
        self.thousands_separator = get_config(
            "postprocessing.amount.thousands_separator",
            ","
        )
        self.output_format = get_config(
            "postprocessing.amount.output_format",
            "float"
        )
        
        logger.debug("AmountNormalizer initialized")
    
    def normalize(self, amount_str: str) -> Optional[str]:
        """
        Normalize an amount string to standard format.
        
        Args:
            amount_str: Input amount string (e.g., "$1,234.56").
            
        Returns:
            Normalized amount string (e.g., "1234.56") or None.
            
        Example:
            >>> normalizer.normalize("$1,234.56")
            "1234.56"
        """
        if not amount_str:
            return None
        
        # Clean the input
        amount_str = self._clean_amount_string(amount_str)
        
        if not amount_str:
            return None
        
        # Handle European format (comma as decimal)
        amount_str = self._handle_european_format(amount_str)
        
        # Remove thousand separators
        amount_str = amount_str.replace(',', '')
        
        # Validate it's a number
        try:
            value = float(amount_str)
            
            # Format output
            if self.output_format == 'float':
                return f"{value:.2f}"
            else:
                return amount_str
                
        except ValueError:
            logger.debug(f"Could not parse amount: {amount_str}")
            return None
    
    def _clean_amount_string(self, amount_str: str) -> str:
        """
        Clean and prepare amount string for parsing.
        
        Args:
            amount_str: Raw amount string.
            
        Returns:
            Cleaned amount string.
        """
        # Remove extra whitespace
        amount_str = ' '.join(amount_str.split())
        
        # Remove currency symbols
        for symbol in self.CURRENCY_SYMBOLS:
            amount_str = amount_str.replace(symbol, '')
        
        # Remove currency codes (case-insensitive)
        for code in self.CURRENCY_CODES:
            amount_str = re.sub(rf'\b{code}\b', '', amount_str, flags=re.IGNORECASE)
        
        # Remove common prefixes
        prefixes = ['total:', 'amount:', 'total amount:', 'due:', 'balance:']
        for prefix in prefixes:
            if amount_str.lower().startswith(prefix):
                amount_str = amount_str[len(prefix):]
        
        # Keep only digits, comma, dot, and minus
        amount_str = re.sub(r'[^\d,.\-]', '', amount_str)
        
        return amount_str.strip()
    
    def _handle_european_format(self, amount_str: str) -> str:
        """
        Convert European format (comma decimal) to US format (dot decimal).
        
        Args:
            amount_str: Amount string.
            
        Returns:
            Amount string in US format.
        """
        # Count dots and commas
        dot_count = amount_str.count('.')
        comma_count = amount_str.count(',')
        
        # If comma is after the last dot, or there's a comma but no dot,
        # comma might be the decimal separator
        if comma_count == 1:
            comma_pos = amount_str.rfind(',')
            dot_pos = amount_str.rfind('.')
            
            # Comma is after dot - likely European format
            if comma_pos > dot_pos:
                # Also check if digits after comma <= 2 (typical for decimal)
                after_comma = amount_str[comma_pos + 1:]
                if len(after_comma) <= 2 and after_comma.isdigit():
                    # European format: replace dot (thousand sep) and comma (decimal sep)
                    amount_str = amount_str.replace('.', '')
                    amount_str = amount_str.replace(',', '.')
        
        return amount_str
    
    def extract_amount(self, text: str) -> Optional[str]:
        """
        Extract and normalize an amount from text.
        
        Args:
            text: Text that may contain an amount.
            
        Returns:
            Normalized amount string or None.
        """
        # Pattern to match amounts with optional currency
        patterns = [
            r'[\$€£¥₹]?\s*[\d,]+\.?\d*',
            r'[\d,]+\.?\d*\s*(?:USD|EUR|GBP|INR)?'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                normalized = self.normalize(match)
                if normalized:
                    try:
                        value = float(normalized)
                        # Skip very small numbers (likely not amounts)
                        if value > 0:
                            return normalized
                    except ValueError:
                        continue
        
        # Try normalizing the entire text
        return self.normalize(text)
    
    def is_valid_amount(self, amount_str: str) -> bool:
        """
        Check if a string represents a valid amount.
        
        Args:
            amount_str: String to validate.
            
        Returns:
            True if valid amount, False otherwise.
        """
        normalized = self.normalize(amount_str)
        if normalized is None:
            return False
        
        try:
            value = float(normalized)
            return value >= 0
        except ValueError:
            return False
    
    def to_float(self, amount_str: str) -> Optional[float]:
        """
        Convert amount string to float.
        
        Args:
            amount_str: Amount string to convert.
            
        Returns:
            Float value or None.
        """
        normalized = self.normalize(amount_str)
        if normalized:
            try:
                return float(normalized)
            except ValueError:
                pass
        return None
