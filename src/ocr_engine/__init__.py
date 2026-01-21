"""
OCR Engine Module for Invoice Extraction System.

This module provides OCR functionality including:
    - Text extraction from images
    - Bounding box detection for each word/token
    - Coordinate normalization for model input
    - Structured OCR output format

Supports multiple OCR backends:
    - Tesseract (primary)
    - EasyOCR (alternative)
    - PaddleOCR (alternative)

Author: ML Engineering Team
"""

from .engine import OCREngine
from .tesseract_backend import TesseractBackend
from .ocr_result import OCRResult, OCRWord, OCRLine

__all__ = ['OCREngine', 'TesseractBackend', 'OCRResult', 'OCRWord', 'OCRLine']
