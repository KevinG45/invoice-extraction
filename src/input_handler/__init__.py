"""
Input Handler Module for Invoice Extraction System.

This module provides functionality for:
    - Detecting file types (PDF vs Image)
    - Loading and validating input files
    - Converting PDFs to images
    - Normalizing images for OCR processing

Supported formats:
    - PDF (digital and scanned)
    - Images: JPG, JPEG, PNG, TIFF, BMP

Author: ML Engineering Team
"""

from .handler import InputHandler
from .pdf_processor import PDFProcessor
from .image_processor import ImageProcessor

__all__ = ['InputHandler', 'PDFProcessor', 'ImageProcessor']
