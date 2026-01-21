"""
Tesseract OCR Backend.

This module provides OCR functionality using Tesseract (pytesseract).
It extracts text and bounding boxes from images.

Features:
    - Word-level bounding box extraction
    - Confidence scores for each word
    - Line grouping
    - Configurable Tesseract parameters

Requirements:
    - Tesseract OCR installed on the system
    - pytesseract Python package

Author: ML Engineering Team
"""

import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image
import re

from config import get_config
from src.utils.logger import get_logger
from src.utils.exceptions import OCREngineNotAvailableError, OCRProcessingError
from .ocr_result import OCRResult, OCRWord, OCRLine

# Initialize module logger
logger = get_logger(__name__)


class TesseractBackend:
    """
    Tesseract OCR backend implementation.
    
    Uses pytesseract to extract text and bounding boxes from images.
    Tesseract must be installed on the system for this to work.
    
    Attributes:
        language: Tesseract language code (e.g., "eng")
        psm: Page Segmentation Mode (1-13)
        oem: OCR Engine Mode (0-3)
        config: Additional Tesseract configuration
        
    Example:
        >>> backend = TesseractBackend()
        >>> result = backend.extract(image)
        >>> print(f"Found {result.word_count} words")
    """
    
    def __init__(self) -> None:
        """Initialize the Tesseract backend with configuration."""
        # Load configuration
        self.language = get_config("ocr.tesseract.lang", "eng")
        self.psm = get_config("ocr.tesseract.psm", 3)
        self.oem = get_config("ocr.tesseract.oem", 3)
        self.extra_config = get_config("ocr.tesseract.config", "")
        self.normalize_scale = get_config("ocr.bbox.scale_factor", 1000)
        
        # Check for pytesseract
        self._check_dependencies()
        
        logger.debug(
            f"TesseractBackend initialized (lang={self.language}, "
            f"psm={self.psm}, oem={self.oem})"
        )
    
    def _check_dependencies(self) -> None:
        """
        Check if Tesseract is available.
        
        Raises:
            OCREngineNotAvailableError: If Tesseract is not installed.
        """
        try:
            import pytesseract
            self._pytesseract = pytesseract
            
            # Test Tesseract is accessible
            version = pytesseract.get_tesseract_version()
            logger.info(f"Tesseract version: {version}")
            
        except ImportError:
            raise OCREngineNotAvailableError(
                "pytesseract (install with: pip install pytesseract)"
            )
        except Exception as e:
            raise OCREngineNotAvailableError(
                f"Tesseract OCR (not installed or not in PATH): {e}"
            )
    
    def _build_config(self) -> str:
        """
        Build Tesseract configuration string.
        
        Returns:
            Configuration string for Tesseract.
        """
        config_parts = [
            f"--psm {self.psm}",
            f"--oem {self.oem}"
        ]
        
        if self.extra_config:
            config_parts.append(self.extra_config)
        
        return ' '.join(config_parts)
    
    def extract(self, image: Image.Image) -> OCRResult:
        """
        Extract text and bounding boxes from an image.
        
        Args:
            image: PIL Image to process.
            
        Returns:
            OCRResult containing words, lines, and bounding boxes.
            
        Raises:
            OCRProcessingError: If OCR processing fails.
        """
        start_time = time.time()
        
        try:
            # Ensure image is in correct format
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Get image dimensions
            image_width, image_height = image.size
            
            # Build config
            config = self._build_config()
            
            # Extract data using Tesseract
            logger.debug(f"Running Tesseract OCR (config: {config})")
            
            data = self._pytesseract.image_to_data(
                image,
                lang=self.language,
                config=config,
                output_type=self._pytesseract.Output.DICT
            )
            
            # Parse Tesseract output
            words = self._parse_tesseract_output(data)
            
            # Group words into lines
            lines = self._group_into_lines(words)
            
            # Calculate processing time
            processing_time = time.time() - start_time
            
            # Create result
            result = OCRResult(
                words=words,
                lines=lines,
                image_width=image_width,
                image_height=image_height,
                language=self.language,
                engine="tesseract",
                processing_time=processing_time,
                metadata={
                    'psm': self.psm,
                    'oem': self.oem,
                    'tesseract_version': str(self._pytesseract.get_tesseract_version())
                }
            )
            
            # Normalize bounding boxes
            result.normalize_bboxes(self.normalize_scale)
            
            logger.info(
                f"OCR completed: {result.word_count} words, "
                f"{result.line_count} lines, "
                f"avg confidence: {result.average_confidence:.1f}% "
                f"({processing_time:.2f}s)"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"OCR processing failed: {e}")
            raise OCRProcessingError("image", str(e))
    
    def _parse_tesseract_output(self, data: Dict[str, List]) -> List[OCRWord]:
        """
        Parse Tesseract output into OCRWord objects.
        
        Args:
            data: Dictionary output from image_to_data.
            
        Returns:
            List of OCRWord objects.
        """
        words = []
        word_index = 0
        
        n_boxes = len(data['text'])
        
        for i in range(n_boxes):
            text = data['text'][i]
            
            # Skip empty text
            if not text or not text.strip():
                continue
            
            # Clean text
            text = text.strip()
            
            # Get bounding box
            x = data['left'][i]
            y = data['top'][i]
            w = data['width'][i]
            h = data['height'][i]
            
            # Skip invalid boxes
            if w <= 0 or h <= 0:
                continue
            
            # Calculate box coordinates
            x1 = x
            y1 = y
            x2 = x + w
            y2 = y + h
            
            # Get confidence
            conf = float(data['conf'][i])
            if conf < 0:
                conf = 0.0  # Tesseract returns -1 for some elements
            
            # Get line/block info
            block_num = data['block_num'][i]
            par_num = data['par_num'][i]
            line_num = data['line_num'][i]
            
            # Create word object
            word = OCRWord(
                text=text,
                bbox=(x1, y1, x2, y2),
                confidence=conf,
                word_index=word_index,
                line_index=line_num
            )
            
            words.append(word)
            word_index += 1
        
        return words
    
    def _group_into_lines(self, words: List[OCRWord]) -> List[OCRLine]:
        """
        Group words into lines based on vertical position.
        
        Args:
            words: List of OCRWord objects.
            
        Returns:
            List of OCRLine objects.
        """
        if not words:
            return []
        
        # Group by line_index assigned by Tesseract
        line_groups: Dict[int, List[OCRWord]] = {}
        
        for word in words:
            line_idx = word.line_index
            if line_idx not in line_groups:
                line_groups[line_idx] = []
            line_groups[line_idx].append(word)
        
        # Create line objects
        lines = []
        for line_idx in sorted(line_groups.keys()):
            line_words = line_groups[line_idx]
            
            # Sort words by x position
            line_words.sort(key=lambda w: w.x1)
            
            line = OCRLine(
                words=line_words,
                line_index=line_idx
            )
            line.compute_bbox()
            
            lines.append(line)
        
        return lines
    
    def get_raw_text(self, image: Image.Image) -> str:
        """
        Extract only the text content (no bounding boxes).
        
        This is faster than full extraction when only text is needed.
        
        Args:
            image: PIL Image to process.
            
        Returns:
            Extracted text as string.
        """
        try:
            config = self._build_config()
            text = self._pytesseract.image_to_string(
                image,
                lang=self.language,
                config=config
            )
            return text.strip()
        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            return ""
    
    def detect_orientation(self, image: Image.Image) -> Dict[str, Any]:
        """
        Detect image orientation and script.
        
        Args:
            image: PIL Image to analyze.
            
        Returns:
            Dictionary with orientation, rotation, and confidence.
        """
        try:
            osd = self._pytesseract.image_to_osd(image, output_type=self._pytesseract.Output.DICT)
            return {
                'orientation': osd.get('orientation', 0),
                'rotate': osd.get('rotate', 0),
                'orientation_conf': osd.get('orientation_conf', 0),
                'script': osd.get('script', 'unknown'),
                'script_conf': osd.get('script_conf', 0)
            }
        except Exception as e:
            logger.debug(f"Orientation detection failed: {e}")
            return {
                'orientation': 0,
                'rotate': 0,
                'orientation_conf': 0,
                'script': 'unknown',
                'script_conf': 0
            }
    
    def get_available_languages(self) -> List[str]:
        """
        Get list of available Tesseract languages.
        
        Returns:
            List of language codes.
        """
        try:
            langs = self._pytesseract.get_languages()
            return [l for l in langs if l != 'osd']
        except Exception as e:
            logger.debug(f"Could not get languages: {e}")
            return ['eng']
