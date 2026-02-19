"""
Main OCR Engine Module.

This module provides the main OCREngine class that serves as the
unified interface for OCR operations. It supports multiple backends
and provides a consistent API regardless of the underlying OCR engine.

Usage:
    from src.ocr_engine import OCREngine
    
    engine = OCREngine()
    result = engine.extract(image)
    
    # Access extracted data
    print(result.text)
    print(result.words)
    print(result.get_normalized_bboxes())

Author: ML Engineering Team
"""

import time
from typing import Union, Optional, Dict, Any, List
from PIL import Image
from pathlib import Path

from config import get_config
from src.utils.logger import get_logger
from src.utils.exceptions import OCREngineNotAvailableError, OCRProcessingError
from .ocr_result import OCRResult, OCRWord, OCRLine
from .tesseract_backend import TesseractBackend

# Initialize module logger
logger = get_logger(__name__)


class OCREngine:
    """
    Main OCR engine providing unified interface for text extraction.
    
    This class abstracts the underlying OCR backend and provides
    consistent methods for extracting text and bounding boxes from
    images. It supports multiple backends with automatic fallback.
    
    Supported Backends:
        - tesseract: Tesseract OCR (default, recommended)
        - easyocr: EasyOCR (alternative)
        - paddleocr: PaddleOCR (alternative)
    
    Attributes:
        backend_name: Name of the active OCR backend
        backend: The active OCR backend instance
        
    Example:
        >>> engine = OCREngine()
        >>> result = engine.extract(image)
        >>> 
        >>> # Get text only
        >>> print(result.text)
        >>> 
        >>> # Get words with bounding boxes
        >>> for word in result.words:
        ...     print(f"{word.text}: {word.bbox}")
        >>> 
        >>> # Get in LayoutLM format
        >>> layoutlm_data = result.to_layoutlm_format()
    """
    
    # Supported backend engines
    SUPPORTED_BACKENDS = ['tesseract', 'easyocr', 'paddleocr']
    
    def __init__(self, backend: Optional[str] = None) -> None:
        """
        Initialize the OCR engine.
        
        Args:
            backend: OCR backend to use. If None, uses configuration
                    or falls back to tesseract.
        """
        # Determine backend from config or parameter
        self.backend_name = backend or get_config("ocr.engine", "pytesseract")
        
        # Normalize backend name
        if self.backend_name == "pytesseract":
            self.backend_name = "tesseract"
        
        # Initialize the backend
        self.backend = self._initialize_backend()
        
        # Get normalization scale from config
        self.normalize_scale = get_config("ocr.bbox.scale_factor", 1000)
        
        logger.info(f"OCR Engine initialized with backend: {self.backend_name}")
    
    def _initialize_backend(self):
        """
        Initialize the selected OCR backend.
        
        Returns:
            Initialized backend instance.
            
        Raises:
            OCREngineNotAvailableError: If backend cannot be initialized.
        """
        if self.backend_name == "tesseract":
            return TesseractBackend()
        
        elif self.backend_name == "easyocr":
            return self._init_easyocr_backend()
        
        elif self.backend_name == "paddleocr":
            return self._init_paddleocr_backend()
        
        else:
            logger.warning(
                f"Unknown backend '{self.backend_name}', falling back to tesseract"
            )
            self.backend_name = "tesseract"
            return TesseractBackend()
    
    def _init_easyocr_backend(self):
        """Initialize EasyOCR backend (if available)."""
        try:
            import easyocr
            
            languages = get_config("ocr.easyocr.languages", ["en"])
            gpu = get_config("ocr.easyocr.gpu", False)
            
            reader = easyocr.Reader(languages, gpu=gpu)
            
            # Return wrapper that implements extract method
            return EasyOCRWrapper(reader)
            
        except ImportError:
            logger.warning("EasyOCR not available, falling back to Tesseract")
            self.backend_name = "tesseract"
            return TesseractBackend()
    
    def _init_paddleocr_backend(self):
        """Initialize PaddleOCR backend (if available)."""
        try:
            from paddleocr import PaddleOCR
            
            ocr = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
            
            # Return wrapper that implements extract method
            return PaddleOCRWrapper(ocr)
            
        except ImportError:
            logger.warning("PaddleOCR not available, falling back to Tesseract")
            self.backend_name = "tesseract"
            return TesseractBackend()
    
    def extract(self, image: Union[Image.Image, str, Path]) -> OCRResult:
        """
        Extract text and bounding boxes from an image.
        
        This is the main extraction method. It accepts either a PIL Image
        or a path to an image file.
        
        Args:
            image: PIL Image or path to image file.
            
        Returns:
            OCRResult containing words, lines, and bounding boxes.
            
        Raises:
            OCRProcessingError: If extraction fails.
            
        Example:
            >>> result = engine.extract("invoice.png")
            >>> print(f"Extracted {result.word_count} words")
            >>> print(f"Average confidence: {result.average_confidence:.1f}%")
        """
        # Load image if path is provided
        if isinstance(image, (str, Path)):
            image_path = str(image)
            logger.debug(f"Loading image from: {image_path}")
            try:
                image = Image.open(image_path)
            except Exception as e:
                raise OCRProcessingError(image_path, f"Failed to load image: {e}")
        
        # Validate image
        if not isinstance(image, Image.Image):
            raise OCRProcessingError("unknown", "Invalid image input")
        
        # Extract using backend
        logger.debug(f"Extracting text using {self.backend_name} backend")
        result = self.backend.extract(image)
        
        # Ensure bounding boxes are normalized
        if result.words and result.words[0].normalized_bbox is None:
            result.normalize_bboxes(self.normalize_scale)
        
        return result
    
    def extract_text_only(self, image: Union[Image.Image, str, Path]) -> str:
        """
        Extract only text content (faster, no bounding boxes).
        
        Use this when you don't need spatial information.
        
        Args:
            image: PIL Image or path to image file.
            
        Returns:
            Extracted text as string.
        """
        # Load image if path is provided
        if isinstance(image, (str, Path)):
            try:
                image = Image.open(str(image))
            except Exception as e:
                logger.error(f"Failed to load image: {e}")
                return ""
        
        if hasattr(self.backend, 'get_raw_text'):
            return self.backend.get_raw_text(image)
        else:
            result = self.extract(image)
            return result.text
    
    def extract_batch(
        self,
        images: List[Union[Image.Image, str, Path]]
    ) -> List[OCRResult]:
        """
        Extract from multiple images.
        
        Args:
            images: List of PIL Images or paths.
            
        Returns:
            List of OCRResult objects.
        """
        results = []
        
        for i, image in enumerate(images):
            logger.debug(f"Processing image {i+1}/{len(images)}")
            try:
                result = self.extract(image)
                results.append(result)
            except OCRProcessingError as e:
                logger.error(f"Failed to process image {i+1}: {e}")
                # Add empty result for failed images
                results.append(OCRResult())
        
        return results
    
    def get_backend_info(self) -> Dict[str, Any]:
        """
        Get information about the current OCR backend.
        
        Returns:
            Dictionary with backend details.
        """
        info = {
            'backend': self.backend_name,
            'normalize_scale': self.normalize_scale
        }
        
        if hasattr(self.backend, 'get_available_languages'):
            info['languages'] = self.backend.get_available_languages()
        
        return info


class EasyOCRWrapper:
    """Wrapper for EasyOCR to provide consistent interface."""
    
    def __init__(self, reader):
        self.reader = reader
    
    def extract(self, image: Image.Image) -> OCRResult:
        """Extract text using EasyOCR."""
        import numpy as np
        
        start_time = time.time()
        
        # Convert PIL to numpy
        img_array = np.array(image)
        
        # Get image dimensions
        image_height, image_width = img_array.shape[:2]
        
        # Run OCR
        results = self.reader.readtext(img_array)
        
        # Parse results
        words = []
        for i, (bbox, text, conf) in enumerate(results):
            # EasyOCR returns bbox as [[x1,y1], [x2,y1], [x2,y2], [x1,y2]]
            x_coords = [p[0] for p in bbox]
            y_coords = [p[1] for p in bbox]
            
            x1 = int(min(x_coords))
            y1 = int(min(y_coords))
            x2 = int(max(x_coords))
            y2 = int(max(y_coords))
            
            word = OCRWord(
                text=text,
                bbox=(x1, y1, x2, y2),
                confidence=conf * 100,  # Convert to percentage
                word_index=i
            )
            words.append(word)
        
        processing_time = time.time() - start_time
        
        return OCRResult(
            words=words,
            lines=[],
            image_width=image_width,
            image_height=image_height,
            engine="easyocr",
            processing_time=processing_time
        )


class PaddleOCRWrapper:
    """Wrapper for PaddleOCR to provide consistent interface."""
    
    def __init__(self, ocr):
        self.ocr = ocr
    
    def extract(self, image: Image.Image) -> OCRResult:
        """Extract text using PaddleOCR."""
        import numpy as np
        
        start_time = time.time()
        
        # Convert PIL to numpy
        img_array = np.array(image)
        
        # Get image dimensions
        image_height, image_width = img_array.shape[:2]
        
        # Run OCR
        results = self.ocr.ocr(img_array, cls=True)
        
        # Parse results
        words = []
        word_index = 0
        
        if results and results[0]:
            for line in results[0]:
                bbox, (text, conf) = line
                
                # PaddleOCR returns bbox as [[x1,y1], [x2,y1], [x2,y2], [x1,y2]]
                x_coords = [p[0] for p in bbox]
                y_coords = [p[1] for p in bbox]
                
                x1 = int(min(x_coords))
                y1 = int(min(y_coords))
                x2 = int(max(x_coords))
                y2 = int(max(y_coords))
                
                word = OCRWord(
                    text=text,
                    bbox=(x1, y1, x2, y2),
                    confidence=conf * 100,
                    word_index=word_index
                )
                words.append(word)
                word_index += 1
        
        processing_time = time.time() - start_time
        
        return OCRResult(
            words=words,
            lines=[],
            image_width=image_width,
            image_height=image_height,
            engine="paddleocr",
            processing_time=processing_time
        )
