"""
Image Processor Module.

This module handles image file processing including:
    - Image loading and validation
    - Resolution normalization
    - Orientation correction
    - Image enhancement for OCR

Supports: JPG, JPEG, PNG, TIFF, BMP

Author: ML Engineering Team
"""

from pathlib import Path
from typing import Union, List, Tuple, Dict, Any, Optional
from PIL import Image, ImageOps, ImageEnhance, ExifTags
import io

from config import get_config
from src.utils.logger import get_logger
from src.utils.exceptions import CorruptedFileError

# Initialize module logger
logger = get_logger(__name__)


class ImageProcessor:
    """
    Processor for image files (JPG, PNG, TIFF, BMP).
    
    Handles image loading, normalization, and enhancement to ensure
    consistent quality for OCR processing.
    
    Attributes:
        target_dpi: Target DPI for normalization
        max_width: Maximum image width in pixels
        max_height: Maximum image height in pixels
        auto_orient: Whether to auto-correct orientation
        enhance_contrast: Whether to apply contrast enhancement
        
    Example:
        >>> processor = ImageProcessor()
        >>> images, metadata = processor.process("invoice.jpg")
        >>> image = images[0]  # Single image
    """
    
    def __init__(self) -> None:
        """Initialize the image processor with configuration."""
        # Load configuration
        self.target_dpi = get_config("input.image.target_dpi", 300)
        self.max_width = get_config("input.image.max_width", 2480)
        self.max_height = get_config("input.image.max_height", 3508)
        self.min_width = get_config("input.image.min_width", 500)
        self.min_height = get_config("input.image.min_height", 500)
        self.auto_orient = get_config("input.image.auto_orient", True)
        self.enhance_contrast = get_config("input.image.enhance_contrast", True)
        
        logger.debug(
            f"ImageProcessor initialized (DPI={self.target_dpi}, "
            f"max_size={self.max_width}x{self.max_height})"
        )
    
    def process(self, filepath: Union[str, Path]) -> Tuple[List[Image.Image], Dict[str, Any]]:
        """
        Process an image file for OCR.
        
        Args:
            filepath: Path to the image file.
            
        Returns:
            Tuple of (list containing single PIL Image, metadata dictionary).
            
        Raises:
            CorruptedFileError: If image cannot be read.
        """
        filepath = Path(filepath)
        logger.info(f"Processing image: {filepath.name}")
        
        try:
            # Load image
            image = Image.open(filepath)
            
            # Extract metadata before processing
            metadata = self._extract_metadata(filepath, image)
            
            # Apply processing pipeline
            image = self._process_image(image)
            
            # Update metadata with processed info
            metadata['processed_width'] = image.width
            metadata['processed_height'] = image.height
            
            logger.info(
                f"Processed image: {image.width}x{image.height} "
                f"(original: {metadata['original_width']}x{metadata['original_height']})"
            )
            
            return [image], metadata
            
        except Exception as e:
            logger.error(f"Failed to process image {filepath}: {e}")
            raise CorruptedFileError(str(filepath), str(e))
    
    def _process_image(self, image: Image.Image) -> Image.Image:
        """
        Apply full processing pipeline to an image.
        
        Processing steps:
            1. Fix orientation from EXIF data
            2. Convert to RGB
            3. Resize if too large
            4. Enhance contrast (optional)
            5. Validate minimum size
        
        Args:
            image: Input PIL Image.
            
        Returns:
            Processed PIL Image.
        """
        # Step 1: Fix orientation from EXIF
        if self.auto_orient:
            image = self._fix_orientation(image)
        
        # Step 2: Convert to RGB (required for most OCR)
        image = self._convert_to_rgb(image)
        
        # Step 3: Resize if too large
        image = self._resize_if_needed(image)
        
        # Step 4: Enhance contrast (optional)
        if self.enhance_contrast:
            image = self._enhance_image(image)
        
        # Step 5: Validate size
        self._validate_size(image)
        
        return image
    
    def _fix_orientation(self, image: Image.Image) -> Image.Image:
        """
        Fix image orientation based on EXIF data.
        
        Many cameras store rotation information in EXIF metadata
        rather than actually rotating the image. This fixes that.
        
        Args:
            image: Input PIL Image.
            
        Returns:
            Correctly oriented image.
        """
        try:
            # Get EXIF data
            exif = image.getexif()
            if not exif:
                return image
            
            # Find orientation tag
            orientation_tag = None
            for tag, name in ExifTags.TAGS.items():
                if name == 'Orientation':
                    orientation_tag = tag
                    break
            
            if orientation_tag is None or orientation_tag not in exif:
                return image
            
            orientation = exif[orientation_tag]
            
            # Apply transformation based on orientation
            if orientation == 2:
                image = image.transpose(Image.FLIP_LEFT_RIGHT)
            elif orientation == 3:
                image = image.rotate(180, expand=True)
            elif orientation == 4:
                image = image.transpose(Image.FLIP_TOP_BOTTOM)
            elif orientation == 5:
                image = image.transpose(Image.FLIP_LEFT_RIGHT)
                image = image.rotate(270, expand=True)
            elif orientation == 6:
                image = image.rotate(270, expand=True)
            elif orientation == 7:
                image = image.transpose(Image.FLIP_LEFT_RIGHT)
                image = image.rotate(90, expand=True)
            elif orientation == 8:
                image = image.rotate(90, expand=True)
            
            logger.debug(f"Fixed image orientation (EXIF orientation={orientation})")
            
        except Exception as e:
            logger.debug(f"Could not fix orientation: {e}")
        
        return image
    
    def _convert_to_rgb(self, image: Image.Image) -> Image.Image:
        """
        Convert image to RGB mode.
        
        Handles various input modes:
            - RGBA: Remove alpha channel
            - L (grayscale): Convert to RGB
            - P (palette): Convert to RGB
            - CMYK: Convert to RGB
        
        Args:
            image: Input PIL Image.
            
        Returns:
            RGB image.
        """
        if image.mode == 'RGB':
            return image
        
        original_mode = image.mode
        
        if image.mode == 'RGBA':
            # Create white background and paste image
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[3])
            image = background
        else:
            image = image.convert('RGB')
        
        logger.debug(f"Converted image from {original_mode} to RGB")
        return image
    
    def _resize_if_needed(self, image: Image.Image) -> Image.Image:
        """
        Resize image if it exceeds maximum dimensions.
        
        Maintains aspect ratio during resize.
        
        Args:
            image: Input PIL Image.
            
        Returns:
            Resized image (or original if within limits).
        """
        width, height = image.size
        
        # Check if resize is needed
        if width <= self.max_width and height <= self.max_height:
            return image
        
        # Calculate new size maintaining aspect ratio
        width_ratio = self.max_width / width
        height_ratio = self.max_height / height
        ratio = min(width_ratio, height_ratio)
        
        new_width = int(width * ratio)
        new_height = int(height * ratio)
        
        # Use LANCZOS for high-quality downscaling
        image = image.resize((new_width, new_height), Image.LANCZOS)
        
        logger.debug(f"Resized image from {width}x{height} to {new_width}x{new_height}")
        return image
    
    def _enhance_image(self, image: Image.Image) -> Image.Image:
        """
        Apply image enhancements for better OCR quality.
        
        Enhancements:
            - Slight contrast increase
            - Slight sharpness increase
        
        Args:
            image: Input PIL Image.
            
        Returns:
            Enhanced image.
        """
        try:
            # Increase contrast slightly
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.2)  # 20% increase
            
            # Increase sharpness slightly
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(1.1)  # 10% increase
            
            logger.debug("Applied image enhancements")
            
        except Exception as e:
            logger.debug(f"Could not enhance image: {e}")
        
        return image
    
    def _validate_size(self, image: Image.Image) -> None:
        """
        Validate that image meets minimum size requirements.
        
        Args:
            image: Image to validate.
            
        Raises:
            CorruptedFileError: If image is too small.
        """
        width, height = image.size
        
        if width < self.min_width or height < self.min_height:
            logger.warning(
                f"Image size {width}x{height} below minimum "
                f"{self.min_width}x{self.min_height}"
            )
            # Don't raise error, just warn - small images may still work
    
    def _extract_metadata(
        self,
        filepath: Path,
        image: Image.Image
    ) -> Dict[str, Any]:
        """
        Extract metadata from image file.
        
        Args:
            filepath: Path to image file.
            image: Loaded PIL Image.
            
        Returns:
            Dictionary of metadata.
        """
        metadata = {
            'original_filename': filepath.name,
            'file_size_bytes': filepath.stat().st_size,
            'file_type': 'image',
            'original_width': image.width,
            'original_height': image.height,
            'original_mode': image.mode,
            'format': image.format,
            'page_count': 1
        }
        
        # Try to get DPI from image
        try:
            dpi = image.info.get('dpi', (self.target_dpi, self.target_dpi))
            if isinstance(dpi, tuple):
                metadata['original_dpi'] = dpi[0]
            else:
                metadata['original_dpi'] = dpi
        except:
            metadata['original_dpi'] = self.target_dpi
        
        return metadata
    
    def preprocess_for_ocr(
        self,
        image: Image.Image,
        binarize: bool = False,
        denoise: bool = False
    ) -> Image.Image:
        """
        Apply additional preprocessing specifically for OCR.
        
        This is an optional step that can improve OCR accuracy
        for challenging images.
        
        Args:
            image: Input image.
            binarize: Convert to black and white.
            denoise: Apply noise reduction.
            
        Returns:
            Preprocessed image.
        """
        if binarize:
            # Convert to grayscale then threshold
            gray = image.convert('L')
            # Use adaptive thresholding (simple version)
            threshold = 128
            image = gray.point(lambda x: 255 if x > threshold else 0, 'L')
            image = image.convert('RGB')
            logger.debug("Applied binarization")
        
        if denoise:
            # Simple median filter for noise reduction
            try:
                from PIL import ImageFilter
                image = image.filter(ImageFilter.MedianFilter(size=3))
                logger.debug("Applied noise reduction")
            except:
                pass
        
        return image
