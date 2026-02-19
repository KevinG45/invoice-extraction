"""
PDF Processor Module.

This module handles PDF file processing including:
    - Digital PDF text extraction
    - Scanned PDF to image conversion
    - Multi-page PDF handling
    - PDF metadata extraction

Uses pdf2image for PDF to image conversion and pdfplumber for
digital PDF analysis.

Author: ML Engineering Team
"""

import io
from pathlib import Path
from typing import Union, List, Tuple, Dict, Any, Optional
from PIL import Image

from config import get_config
from src.utils.logger import get_logger
from src.utils.exceptions import CorruptedFileError, InputError

# Initialize module logger
logger = get_logger(__name__)


class PDFProcessor:
    """
    Processor for PDF files.
    
    Handles both digital PDFs (with embedded text) and scanned PDFs
    (image-only). Converts PDF pages to images for OCR processing.
    
    Attributes:
        dpi: Resolution for PDF to image conversion
        first_page_only: Whether to process only the first page
        max_pages: Maximum number of pages to process
        
    Example:
        >>> processor = PDFProcessor()
        >>> images, metadata = processor.process("invoice.pdf")
        >>> print(f"Extracted {len(images)} pages")
    """
    
    def __init__(self) -> None:
        """Initialize the PDF processor with configuration."""
        # Load configuration
        self.dpi = get_config("input.pdf.dpi", 300)
        self.first_page_only = get_config("input.pdf.first_page_only", True)
        self.max_pages = get_config("input.pdf.max_pages", 10)
        
        # Check for required libraries
        self._check_dependencies()
        
        logger.debug(f"PDFProcessor initialized (DPI={self.dpi}, first_page_only={self.first_page_only})")
    
    def _check_dependencies(self) -> None:
        """
        Check if required PDF processing libraries are available.
        
        Raises:
            ImportError: If required libraries are not installed.
        """
        try:
            import pdf2image
            self._pdf2image = pdf2image
        except ImportError:
            logger.warning("pdf2image not available. Install with: pip install pdf2image")
            self._pdf2image = None
        
        try:
            import fitz  # PyMuPDF
            self._pymupdf = fitz
        except ImportError:
            logger.debug("PyMuPDF not available. Using pdf2image as primary.")
            self._pymupdf = None
        
        try:
            import pdfplumber
            self._pdfplumber = pdfplumber
        except ImportError:
            logger.debug("pdfplumber not available. PDF text extraction limited.")
            self._pdfplumber = None
    
    def process(self, filepath: Union[str, Path]) -> Tuple[List[Image.Image], Dict[str, Any]]:
        """
        Process a PDF file and convert to images.
        
        Args:
            filepath: Path to the PDF file.
            
        Returns:
            Tuple of (list of PIL Images, metadata dictionary).
            
        Raises:
            CorruptedFileError: If PDF cannot be read.
            InputError: If no PDF processing library is available.
        """
        filepath = Path(filepath)
        logger.info(f"Processing PDF: {filepath.name}")
        
        # Extract metadata
        metadata = self._extract_metadata(filepath)
        
        # Convert PDF to images
        if self._pymupdf is not None:
            images = self._convert_with_pymupdf(filepath)
        elif self._pdf2image is not None:
            images = self._convert_with_pdf2image(filepath)
        else:
            raise InputError(
                "No PDF processing library available. "
                "Install pdf2image or PyMuPDF."
            )
        
        # Limit pages if configured
        if self.first_page_only and images:
            images = images[:1]
        elif len(images) > self.max_pages:
            logger.warning(
                f"PDF has {len(images)} pages, limiting to {self.max_pages}"
            )
            images = images[:self.max_pages]
        
        metadata['page_count'] = len(images)
        logger.info(f"Converted PDF to {len(images)} image(s)")
        
        return images, metadata
    
    def _convert_with_pymupdf(self, filepath: Path) -> List[Image.Image]:
        """
        Convert PDF to images using PyMuPDF (faster method).
        
        Args:
            filepath: Path to PDF file.
            
        Returns:
            List of PIL Image objects.
        """
        logger.debug("Using PyMuPDF for PDF conversion")
        images = []
        
        try:
            doc = self._pymupdf.open(filepath)
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                
                # Calculate zoom factor based on DPI
                # Default PDF resolution is 72 DPI
                zoom = self.dpi / 72.0
                matrix = self._pymupdf.Matrix(zoom, zoom)
                
                # Render page to pixmap
                pix = page.get_pixmap(matrix=matrix)
                
                # Convert to PIL Image
                img_data = pix.tobytes("png")
                image = Image.open(io.BytesIO(img_data))
                
                # Convert to RGB if necessary
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                
                images.append(image)
                
                # Check if we only need first page
                if self.first_page_only:
                    break
            
            doc.close()
            
        except Exception as e:
            logger.error(f"PyMuPDF conversion failed: {e}")
            raise CorruptedFileError(str(filepath), str(e))
        
        return images
    
    def _convert_with_pdf2image(self, filepath: Path) -> List[Image.Image]:
        """
        Convert PDF to images using pdf2image (Poppler-based).
        
        Args:
            filepath: Path to PDF file.
            
        Returns:
            List of PIL Image objects.
        """
        logger.debug("Using pdf2image for PDF conversion")
        
        try:
            # Determine pages to convert
            if self.first_page_only:
                first_page = 1
                last_page = 1
            else:
                first_page = 1
                last_page = self.max_pages
            
            # Convert PDF to images
            images = self._pdf2image.convert_from_path(
                filepath,
                dpi=self.dpi,
                first_page=first_page,
                last_page=last_page,
                fmt='png'
            )
            
            # Ensure RGB mode
            images = [
                img.convert('RGB') if img.mode != 'RGB' else img
                for img in images
            ]
            
            return images
            
        except Exception as e:
            logger.error(f"pdf2image conversion failed: {e}")
            raise CorruptedFileError(str(filepath), str(e))
    
    def _extract_metadata(self, filepath: Path) -> Dict[str, Any]:
        """
        Extract metadata from PDF file.
        
        Args:
            filepath: Path to PDF file.
            
        Returns:
            Dictionary of metadata.
        """
        metadata = {
            'original_filename': filepath.name,
            'file_size_bytes': filepath.stat().st_size,
            'file_type': 'pdf',
            'source_dpi': self.dpi
        }
        
        # Try to extract PDF-specific metadata
        if self._pymupdf is not None:
            try:
                doc = self._pymupdf.open(filepath)
                pdf_metadata = doc.metadata
                
                if pdf_metadata:
                    metadata['pdf_title'] = pdf_metadata.get('title', '')
                    metadata['pdf_author'] = pdf_metadata.get('author', '')
                    metadata['pdf_creator'] = pdf_metadata.get('creator', '')
                    metadata['pdf_creation_date'] = pdf_metadata.get('creationDate', '')
                
                metadata['total_pages'] = len(doc)
                doc.close()
                
            except Exception as e:
                logger.debug(f"Could not extract PDF metadata: {e}")
        
        return metadata
    
    def is_scanned_pdf(self, filepath: Union[str, Path]) -> bool:
        """
        Detect if a PDF is scanned (image-only) or digital (text-based).
        
        Args:
            filepath: Path to PDF file.
            
        Returns:
            True if PDF appears to be scanned, False if digital.
        """
        if self._pdfplumber is None:
            # Cannot determine without pdfplumber
            return True  # Assume scanned to be safe
        
        try:
            with self._pdfplumber.open(filepath) as pdf:
                if not pdf.pages:
                    return True
                
                # Check first page for text
                first_page = pdf.pages[0]
                text = first_page.extract_text() or ""
                
                # If minimal text found, likely scanned
                if len(text.strip()) < 50:
                    logger.debug(f"PDF appears to be scanned (minimal text found)")
                    return True
                
                logger.debug(f"PDF appears to be digital (text found)")
                return False
                
        except Exception as e:
            logger.debug(f"Error checking PDF type: {e}")
            return True  # Assume scanned to be safe
    
    def get_page_count(self, filepath: Union[str, Path]) -> int:
        """
        Get the total number of pages in a PDF.
        
        Args:
            filepath: Path to PDF file.
            
        Returns:
            Number of pages in the PDF.
        """
        if self._pymupdf is not None:
            try:
                doc = self._pymupdf.open(filepath)
                count = len(doc)
                doc.close()
                return count
            except:
                pass
        
        if self._pdfplumber is not None:
            try:
                with self._pdfplumber.open(filepath) as pdf:
                    return len(pdf.pages)
            except:
                pass
        
        # Fallback: use pdf2image to count pages
        if self._pdf2image is not None:
            try:
                info = self._pdf2image.pdfinfo_from_path(filepath)
                return info.get('Pages', 1)
            except:
                pass
        
        return 1  # Default to 1 if cannot determine
