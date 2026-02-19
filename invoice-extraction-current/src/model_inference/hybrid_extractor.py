"""
Hybrid Document Extractor Module.

This module provides the HybridExtractor class that combines
LayoutLMv3 and Donut models for optimal extraction performance.

Hybrid Strategy:
    - LayoutLMv3: Best for header fields (invoice number, dates, names)
        - Excellent layout understanding
        - Good for sparse, structured information
        - Requires OCR but very accurate for headers
        
    - Donut: Best for line items and tables
        - OCR-free, faster for dense data
        - Better for repetitive structured data
        - Excellent for tables and line items

Combined Approach:
    1. Use LayoutLMv3 for header extraction (existing system)
    2. Use Donut for line item extraction
    3. Merge results with confidence-based selection
    4. Cross-validate totals between line items and header

Author: ML Engineering Team
"""

import time
from typing import Optional, Dict, Any, List, Tuple
from PIL import Image
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import get_config
from src.utils.logger import get_logger
from src.utils.exceptions import InferenceError
from src.ocr_engine.ocr_result import OCRResult
from .extraction_result import ExtractionResult
from .extractor import InvoiceExtractor
from .donut_extractor import DonutExtractor
from .line_item import LineItem

# Initialize module logger
logger = get_logger(__name__)


class HybridExtractor:
    """
    Hybrid document extractor combining LayoutLMv3 and Donut.
    
    This extractor leverages the strengths of both models:
    - LayoutLMv3 for accurate header field extraction
    - Donut for fast and accurate line item extraction
    
    The hybrid approach provides:
    - Better overall accuracy
    - Complete invoice extraction (headers + line items)
    - Cross-validation between models
    - Confidence-weighted result selection
    
    Attributes:
        layout_extractor: InvoiceExtractor (LayoutLMv3) instance
        donut_extractor: DonutExtractor instance
        parallel_mode: Whether to run models in parallel
        
    Example:
        >>> extractor = HybridExtractor()
        >>> result = extractor.extract(image)
        >>> print(f"Invoice: {result.invoice_number}")
        >>> for item in result.line_items:
        ...     print(f"  {item.description}: ${item.total}")
    """
    
    def __init__(
        self,
        use_layoutlm: bool = True,
        use_donut: bool = True,
        parallel_mode: bool = False,
        device: Optional[str] = None
    ) -> None:
        """
        Initialize the hybrid extractor.
        
        Args:
            use_layoutlm: Whether to use LayoutLMv3 for headers.
            use_donut: Whether to use Donut for line items.
            parallel_mode: Run both models in parallel (requires more memory).
            device: Device for inference ('cpu', 'cuda').
        """
        self.device = device or get_config("model.inference.device", "cpu")
        self.parallel_mode = parallel_mode
        self.use_layoutlm = use_layoutlm
        self.use_donut = use_donut
        
        # Initialize extractors (lazy loading)
        self._layout_extractor = None
        self._donut_extractor = None
        
        # Configuration
        self.confidence_threshold = get_config(
            "model.hybrid.confidence_threshold", 0.5
        )
        self.validate_totals = get_config(
            "model.hybrid.validate_totals", True
        )
        
        logger.info(
            f"HybridExtractor initialized: "
            f"LayoutLM={use_layoutlm}, Donut={use_donut}, "
            f"parallel={parallel_mode}, device={device}"
        )
    
    @property
    def layout_extractor(self) -> InvoiceExtractor:
        """Lazy-load LayoutLMv3 extractor."""
        if self._layout_extractor is None:
            logger.info("Loading LayoutLMv3 extractor...")
            self._layout_extractor = InvoiceExtractor(device=self.device)
        return self._layout_extractor
    
    @property
    def donut_extractor(self) -> DonutExtractor:
        """Lazy-load Donut extractor."""
        if self._donut_extractor is None:
            logger.info("Loading Donut extractor...")
            self._donut_extractor = DonutExtractor(device=self.device)
        return self._donut_extractor
    
    def extract(
        self,
        image: Image.Image,
        ocr_result: Optional[OCRResult] = None,
        source_file: Optional[str] = None,
        extract_line_items: bool = True
    ) -> 'HybridExtractionResult':
        """
        Extract complete invoice data using hybrid approach.
        
        This method:
        1. Uses LayoutLMv3 for header fields
        2. Uses Donut for line items
        3. Merges and validates results
        4. Cross-checks totals
        
        Args:
            image: PIL Image of the invoice.
            ocr_result: Optional pre-computed OCR result.
            source_file: Original filename for metadata.
            extract_line_items: Whether to extract line items.
            
        Returns:
            HybridExtractionResult with headers and line items.
        """
        start_time = time.time()
        
        # Ensure image is RGB
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Create result object
        result = HybridExtractionResult(
            source_file=source_file,
            model_name="hybrid_layoutlmv3_donut"
        )
        
        try:
            if self.parallel_mode and self.use_layoutlm and self.use_donut:
                # Run both models in parallel
                header_result, line_items = self._extract_parallel(
                    image, ocr_result, extract_line_items
                )
            else:
                # Sequential extraction
                header_result, line_items = self._extract_sequential(
                    image, ocr_result, extract_line_items
                )
            
            # Copy header fields from LayoutLMv3 result
            if header_result:
                result.invoice_number = header_result.invoice_number
                result.invoice_date = header_result.invoice_date
                result.vendor_name = header_result.vendor_name
                result.customer_name = header_result.customer_name
                result.total_amount = header_result.total_amount
                result.payment_due_date = header_result.payment_due_date
                result.confidence_scores = header_result.confidence_scores.copy()
                result.raw_extractions = header_result.raw_extractions.copy()
            
            # Add line items
            result.line_items = line_items
            
            # Cross-validate totals
            if self.validate_totals and line_items and result.total_amount:
                validation = self._validate_totals(result)
                result.total_validation = validation
                if not validation['is_valid']:
                    result.add_warning(
                        f"Total mismatch: header={result.total_amount}, "
                        f"line_items_sum={validation['line_items_sum']}"
                    )
            
            # Calculate processing time
            result.processing_time = time.time() - start_time
            
            # Log summary
            logger.info(
                f"Hybrid extraction complete: "
                f"{len(result.extracted_fields)}/6 header fields, "
                f"{len(line_items)} line items, "
                f"time: {result.processing_time:.2f}s"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Hybrid extraction failed: {e}")
            result.add_error(f"Extraction failed: {str(e)}")
            result.processing_time = time.time() - start_time
            return result
    
    def _extract_sequential(
        self,
        image: Image.Image,
        ocr_result: Optional[OCRResult],
        extract_line_items: bool
    ) -> Tuple[Optional[ExtractionResult], List[LineItem]]:
        """
        Sequential extraction: headers first, then line items.
        
        Args:
            image: Invoice image.
            ocr_result: Optional OCR result.
            extract_line_items: Whether to extract line items.
            
        Returns:
            Tuple of (header_result, line_items).
        """
        header_result = None
        line_items = []
        
        # Step 1: Header extraction with LayoutLMv3
        if self.use_layoutlm:
            try:
                logger.info("Extracting headers with LayoutLMv3...")
                header_result = self.layout_extractor.extract(
                    image, ocr_result
                )
            except Exception as e:
                logger.warning(f"LayoutLMv3 extraction failed: {e}")
        
        # Step 2: Line item extraction with Donut
        if self.use_donut and extract_line_items:
            try:
                logger.info("Extracting line items with Donut...")
                line_items = self.donut_extractor.extract_line_items(image)
            except Exception as e:
                logger.warning(f"Donut line item extraction failed: {e}")
        
        return header_result, line_items
    
    def _extract_parallel(
        self,
        image: Image.Image,
        ocr_result: Optional[OCRResult],
        extract_line_items: bool
    ) -> Tuple[Optional[ExtractionResult], List[LineItem]]:
        """
        Parallel extraction: run both models simultaneously.
        
        Note: Requires more memory but faster overall.
        
        Args:
            image: Invoice image.
            ocr_result: Optional OCR result.
            extract_line_items: Whether to extract line items.
            
        Returns:
            Tuple of (header_result, line_items).
        """
        header_result = None
        line_items = []
        
        def extract_headers():
            return self.layout_extractor.extract(image, ocr_result)
        
        def extract_items():
            return self.donut_extractor.extract_line_items(image)
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {}
            
            if self.use_layoutlm:
                futures['headers'] = executor.submit(extract_headers)
            
            if self.use_donut and extract_line_items:
                futures['line_items'] = executor.submit(extract_items)
            
            for key, future in futures.items():
                try:
                    result = future.result(timeout=60)  # 60s timeout
                    if key == 'headers':
                        header_result = result
                    elif key == 'line_items':
                        line_items = result
                except Exception as e:
                    logger.warning(f"Parallel extraction failed for {key}: {e}")
        
        return header_result, line_items
    
    def _validate_totals(
        self,
        result: 'HybridExtractionResult'
    ) -> Dict[str, Any]:
        """
        Cross-validate extracted total with sum of line items.
        
        Args:
            result: Extraction result to validate.
            
        Returns:
            Validation result dictionary.
        """
        validation = {
            'is_valid': False,
            'header_total': None,
            'line_items_sum': None,
            'difference': None,
            'difference_percent': None
        }
        
        try:
            # Parse header total
            header_total = self._parse_amount(result.total_amount)
            validation['header_total'] = float(header_total) if header_total else None
            
            # Sum line items
            line_items_sum = sum(
                item.total for item in result.line_items
                if item.total is not None
            )
            validation['line_items_sum'] = float(line_items_sum)
            
            if header_total and line_items_sum:
                # Calculate difference
                diff = abs(header_total - line_items_sum)
                validation['difference'] = float(diff)
                
                # Calculate percentage difference
                if header_total > 0:
                    validation['difference_percent'] = float(
                        (diff / header_total) * 100
                    )
                
                # Valid if within 5% tolerance (for taxes, rounding)
                tolerance = header_total * Decimal('0.05')
                validation['is_valid'] = diff <= tolerance
            
        except Exception as e:
            logger.warning(f"Total validation error: {e}")
        
        return validation
    
    def _parse_amount(self, amount_str: str) -> Optional[Decimal]:
        """Parse amount string to Decimal."""
        if not amount_str:
            return None
        try:
            cleaned = amount_str.replace('$', '').replace(',', '').strip()
            return Decimal(cleaned)
        except:
            return None
    
    def extract_with_donut_fallback(
        self,
        image: Image.Image,
        ocr_result: Optional[OCRResult] = None,
        source_file: Optional[str] = None
    ) -> 'HybridExtractionResult':
        """
        Extract with Donut as fallback for missing LayoutLMv3 fields.
        
        If LayoutLMv3 misses fields, use Donut's structured extraction
        to fill in the gaps.
        
        Args:
            image: Invoice image.
            ocr_result: Optional OCR result.
            source_file: Original filename.
            
        Returns:
            HybridExtractionResult with complete data.
        """
        # First, standard hybrid extraction
        result = self.extract(image, ocr_result, source_file)
        
        # Check for missing fields
        if result.missing_fields:
            logger.info(
                f"Attempting Donut fallback for missing fields: "
                f"{result.missing_fields}"
            )
            
            try:
                # Get Donut's structured extraction
                donut_data = self.donut_extractor.extract_structured(image)
                
                # Map Donut fields to our fields
                field_mapping = {
                    'invoice_number': ['invoice_no', 'receipt_no', 'bill_no'],
                    'invoice_date': ['date', 'receipt_date'],
                    'vendor_name': ['store_name', 'shop_name', 'company'],
                    'total_amount': ['total', 'total_price', 'grand_total']
                }
                
                for field in result.missing_fields:
                    if field in field_mapping:
                        for donut_field in field_mapping[field]:
                            if donut_field in donut_data and donut_data[donut_field]:
                                result.set_field(field, str(donut_data[donut_field]), 0.6)
                                result.add_warning(f"{field} extracted via Donut fallback")
                                logger.info(f"Donut fallback: {field} = {donut_data[donut_field]}")
                                break
                
            except Exception as e:
                logger.warning(f"Donut fallback failed: {e}")
        
        return result
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about loaded models.
        
        Returns:
            Dictionary with model details.
        """
        info = {
            'hybrid_mode': True,
            'parallel_mode': self.parallel_mode,
            'device': self.device,
            'use_layoutlm': self.use_layoutlm,
            'use_donut': self.use_donut,
            'confidence_threshold': self.confidence_threshold,
            'validate_totals': self.validate_totals
        }
        
        if self._layout_extractor:
            info['layoutlm'] = self._layout_extractor.get_model_info()
        
        if self._donut_extractor:
            info['donut'] = self._donut_extractor.get_model_info()
        
        return info


class HybridExtractionResult(ExtractionResult):
    """
    Extended extraction result with line items support.
    
    Inherits from ExtractionResult and adds line item support
    for hybrid extraction results.
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize with line items list."""
        super().__init__(*args, **kwargs)
        self.line_items: List[LineItem] = []
        self.total_validation: Dict[str, Any] = {}
    
    @property
    def line_items_total(self) -> Optional[Decimal]:
        """Calculate total from line items."""
        if not self.line_items:
            return None
        total = sum(
            item.total for item in self.line_items
            if item.total is not None
        )
        return total
    
    @property
    def line_items_count(self) -> int:
        """Get number of line items."""
        return len(self.line_items)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary including line items.
        
        Returns:
            Complete dictionary representation.
        """
        base_dict = super().to_dict()
        
        # Add line items
        base_dict['line_items'] = [
            item.to_dict() for item in self.line_items
        ]
        base_dict['line_items_count'] = self.line_items_count
        base_dict['line_items_total'] = (
            float(self.line_items_total) if self.line_items_total else None
        )
        base_dict['total_validation'] = self.total_validation
        
        return base_dict
    
    def to_flat_dict(self) -> Dict[str, Any]:
        """
        Convert to flat dictionary for database/Excel.
        
        Line items are excluded (stored separately).
        """
        base_dict = super().to_flat_dict()
        base_dict['line_items_count'] = self.line_items_count
        base_dict['line_items_total'] = (
            float(self.line_items_total) if self.line_items_total else None
        )
        return base_dict
    
    def get_line_items_dataframe(self):
        """
        Get line items as pandas DataFrame.
        
        Returns:
            pandas DataFrame with line items.
        """
        import pandas as pd
        
        if not self.line_items:
            return pd.DataFrame()
        
        return pd.DataFrame([
            item.to_dict() for item in self.line_items
        ])
    
    def __repr__(self) -> str:
        return (
            f"HybridExtractionResult("
            f"invoice={self.invoice_number}, "
            f"vendor={self.vendor_name}, "
            f"total={self.total_amount}, "
            f"line_items={self.line_items_count}, "
            f"rate={self.extraction_rate:.0f}%)"
        )
