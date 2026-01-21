"""
Main Input Handler Module.

This module provides the primary InputHandler class that serves as the
main interface for loading and processing invoice files. It automatically
detects file types and delegates to appropriate processors.

Usage:
    from src.input_handler import InputHandler
    
    handler = InputHandler()
    result = handler.load("invoice.pdf")
    
    # Process batch
    results = handler.load_batch("./invoices/")

Classes:
    InputHandler: Main class for file input handling
"""

import os
from pathlib import Path
from typing import Union, List, Optional, Dict, Any, Tuple
from dataclasses import dataclass
from PIL import Image

from config import get_config
from src.utils.logger import get_logger
from src.utils.helpers import get_file_extension, validate_file_exists
from src.utils.exceptions import (
    InputError,
    UnsupportedFileTypeError,
    FileNotFoundError,
    CorruptedFileError
)

from .pdf_processor import PDFProcessor
from .image_processor import ImageProcessor


# Initialize module logger
logger = get_logger(__name__)


@dataclass
class InputResult:
    """
    Data class representing the result of input processing.
    
    Attributes:
        filepath: Original file path
        filename: Original filename
        file_type: Detected file type ('pdf' or 'image')
        images: List of processed PIL Images (one per page)
        page_count: Number of pages processed
        metadata: Additional file metadata
        success: Whether processing was successful
        error: Error message if processing failed
    """
    filepath: str
    filename: str
    file_type: str
    images: List[Image.Image]
    page_count: int
    metadata: Dict[str, Any]
    success: bool = True
    error: Optional[str] = None
    
    def __repr__(self) -> str:
        return (
            f"InputResult(filename='{self.filename}', "
            f"type='{self.file_type}', "
            f"pages={self.page_count}, "
            f"success={self.success})"
        )


class InputHandler:
    """
    Main input handler for invoice files.
    
    This class provides a unified interface for loading various invoice
    file formats. It automatically detects file types and delegates
    processing to specialized handlers.
    
    Attributes:
        supported_extensions: Set of supported file extensions
        pdf_processor: PDFProcessor instance for PDF files
        image_processor: ImageProcessor instance for image files
        
    Example:
        >>> handler = InputHandler()
        >>> result = handler.load("invoice.pdf")
        >>> print(f"Loaded {result.page_count} pages")
        
        >>> # Batch processing
        >>> results = handler.load_batch("./invoices/")
        >>> for r in results:
        ...     if r.success:
        ...         process(r.images[0])
    """
    
    # Supported file extensions
    PDF_EXTENSIONS = {'.pdf'}
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp'}
    
    def __init__(self, config: Optional[Dict] = None) -> None:
        """
        Initialize the InputHandler.
        
        Args:
            config: Optional configuration dictionary. If not provided,
                   configuration is loaded from settings.yaml.
        """
        self.config = config or {}
        
        # Load supported extensions from config
        self.supported_extensions = set(
            get_config("input.supported_extensions", 
                      list(self.PDF_EXTENSIONS | self.IMAGE_EXTENSIONS))
        )
        
        # Normalize extensions to lowercase
        self.supported_extensions = {ext.lower() for ext in self.supported_extensions}
        
        # Initialize processors
        self.pdf_processor = PDFProcessor()
        self.image_processor = ImageProcessor()
        
        logger.info(f"InputHandler initialized with extensions: {self.supported_extensions}")
    
    def detect_file_type(self, filepath: Union[str, Path]) -> str:
        """
        Detect the type of input file.
        
        Args:
            filepath: Path to the file to analyze.
            
        Returns:
            File type string: 'pdf' or 'image'.
            
        Raises:
            UnsupportedFileTypeError: If file type is not supported.
        """
        extension = get_file_extension(filepath)
        
        if extension in self.PDF_EXTENSIONS:
            logger.debug(f"Detected PDF file: {filepath}")
            return 'pdf'
        elif extension in self.IMAGE_EXTENSIONS:
            logger.debug(f"Detected image file: {filepath}")
            return 'image'
        else:
            raise UnsupportedFileTypeError(
                extension,
                list(self.supported_extensions)
            )
    
    def validate_file(self, filepath: Union[str, Path]) -> Path:
        """
        Validate that a file exists and is accessible.
        
        Args:
            filepath: Path to the file to validate.
            
        Returns:
            Path object pointing to the validated file.
            
        Raises:
            FileNotFoundError: If file doesn't exist.
            UnsupportedFileTypeError: If file type is not supported.
        """
        path = Path(filepath)
        
        # Check file exists
        if not path.exists():
            raise FileNotFoundError(str(filepath))
        
        if not path.is_file():
            raise InputError(f"Path is not a file: {filepath}")
        
        # Check file extension
        extension = get_file_extension(filepath)
        if extension not in self.supported_extensions:
            raise UnsupportedFileTypeError(
                extension,
                list(self.supported_extensions)
            )
        
        # Check file is not empty
        if path.stat().st_size == 0:
            raise CorruptedFileError(str(filepath), "File is empty")
        
        logger.debug(f"File validated: {filepath}")
        return path
    
    def load(self, filepath: Union[str, Path]) -> InputResult:
        """
        Load and process an input file.
        
        This method handles both PDF and image files, converting them
        to a standardized image format suitable for OCR processing.
        
        Args:
            filepath: Path to the invoice file.
            
        Returns:
            InputResult containing processed images and metadata.
            
        Example:
            >>> result = handler.load("invoice.pdf")
            >>> if result.success:
            ...     image = result.images[0]  # First page
            ...     process_image(image)
        """
        filepath = str(filepath)
        logger.info(f"Loading file: {filepath}")
        
        try:
            # Validate file
            validated_path = self.validate_file(filepath)
            filename = validated_path.name
            
            # Detect file type
            file_type = self.detect_file_type(validated_path)
            
            # Process based on file type
            if file_type == 'pdf':
                images, metadata = self.pdf_processor.process(validated_path)
            else:
                images, metadata = self.image_processor.process(validated_path)
            
            # Create result
            result = InputResult(
                filepath=filepath,
                filename=filename,
                file_type=file_type,
                images=images,
                page_count=len(images),
                metadata=metadata,
                success=True
            )
            
            logger.info(f"Successfully loaded: {filename} ({len(images)} page(s))")
            return result
            
        except (FileNotFoundError, UnsupportedFileTypeError, CorruptedFileError) as e:
            logger.error(f"Input error for {filepath}: {e}")
            return InputResult(
                filepath=filepath,
                filename=Path(filepath).name,
                file_type='unknown',
                images=[],
                page_count=0,
                metadata={},
                success=False,
                error=str(e)
            )
            
        except Exception as e:
            logger.exception(f"Unexpected error loading {filepath}: {e}")
            return InputResult(
                filepath=filepath,
                filename=Path(filepath).name,
                file_type='unknown',
                images=[],
                page_count=0,
                metadata={},
                success=False,
                error=f"Unexpected error: {str(e)}"
            )
    
    def load_batch(
        self,
        directory: Union[str, Path],
        recursive: bool = False
    ) -> List[InputResult]:
        """
        Load and process all supported files in a directory.
        
        Args:
            directory: Path to directory containing invoice files.
            recursive: Whether to search subdirectories.
            
        Returns:
            List of InputResult objects for each processed file.
            
        Example:
            >>> results = handler.load_batch("./invoices/")
            >>> successful = [r for r in results if r.success]
            >>> print(f"Processed {len(successful)} invoices successfully")
        """
        directory = Path(directory)
        
        if not directory.exists():
            raise FileNotFoundError(str(directory))
        
        if not directory.is_dir():
            raise InputError(f"Path is not a directory: {directory}")
        
        # Collect files
        files = []
        pattern = "**/*" if recursive else "*"
        
        for ext in self.supported_extensions:
            files.extend(directory.glob(f"{pattern}{ext}"))
            files.extend(directory.glob(f"{pattern}{ext.upper()}"))
        
        # Remove duplicates and sort
        files = sorted(set(files))
        
        logger.info(f"Found {len(files)} files to process in {directory}")
        
        # Process each file
        results = []
        for i, filepath in enumerate(files, 1):
            logger.info(f"Processing file {i}/{len(files)}: {filepath.name}")
            result = self.load(filepath)
            results.append(result)
        
        # Log summary
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        logger.info(f"Batch processing complete: {successful} successful, {failed} failed")
        
        return results
    
    def get_first_page(self, result: InputResult) -> Optional[Image.Image]:
        """
        Get the first page image from an InputResult.
        
        Args:
            result: InputResult from load() method.
            
        Returns:
            First page as PIL Image, or None if no pages.
        """
        if result.success and result.images:
            return result.images[0]
        return None
