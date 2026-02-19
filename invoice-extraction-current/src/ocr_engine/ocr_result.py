"""
OCR Result Data Classes.

This module defines data structures for OCR output, providing
a standardized format for text and bounding box information.

Classes:
    OCRWord: Individual word with bounding box
    OCRLine: Line of text containing multiple words
    OCRResult: Complete OCR output for an image

Author: ML Engineering Team
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import json


@dataclass
class OCRWord:
    """
    Represents a single word/token extracted by OCR.
    
    Attributes:
        text: The recognized text content
        bbox: Bounding box as (x1, y1, x2, y2) in pixels
        confidence: OCR confidence score (0-100)
        normalized_bbox: Bounding box normalized to 0-1000 range
        word_index: Index of word in the document
        line_index: Index of the line this word belongs to
        
    Example:
        >>> word = OCRWord(
        ...     text="Invoice",
        ...     bbox=(100, 50, 200, 80),
        ...     confidence=95.5
        ... )
    """
    text: str
    bbox: Tuple[int, int, int, int]  # (x1, y1, x2, y2)
    confidence: float = 0.0
    normalized_bbox: Optional[Tuple[int, int, int, int]] = None
    word_index: int = 0
    line_index: int = 0
    
    @property
    def x1(self) -> int:
        """Left coordinate."""
        return self.bbox[0]
    
    @property
    def y1(self) -> int:
        """Top coordinate."""
        return self.bbox[1]
    
    @property
    def x2(self) -> int:
        """Right coordinate."""
        return self.bbox[2]
    
    @property
    def y2(self) -> int:
        """Bottom coordinate."""
        return self.bbox[3]
    
    @property
    def width(self) -> int:
        """Width of bounding box."""
        return self.x2 - self.x1
    
    @property
    def height(self) -> int:
        """Height of bounding box."""
        return self.y2 - self.y1
    
    @property
    def center(self) -> Tuple[int, int]:
        """Center point of bounding box."""
        return ((self.x1 + self.x2) // 2, (self.y1 + self.y2) // 2)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            'text': self.text,
            'bbox': list(self.bbox),
            'normalized_bbox': list(self.normalized_bbox) if self.normalized_bbox else None,
            'confidence': self.confidence,
            'word_index': self.word_index,
            'line_index': self.line_index
        }
    
    def __repr__(self) -> str:
        return f"OCRWord('{self.text}', bbox={self.bbox}, conf={self.confidence:.1f})"


@dataclass
class OCRLine:
    """
    Represents a line of text containing multiple words.
    
    Attributes:
        words: List of OCRWord objects in the line
        bbox: Bounding box encompassing the entire line
        line_index: Index of this line in the document
        
    Example:
        >>> line = OCRLine(words=[word1, word2, word3])
        >>> print(line.text)
        "Invoice Number: 12345"
    """
    words: List[OCRWord] = field(default_factory=list)
    bbox: Optional[Tuple[int, int, int, int]] = None
    line_index: int = 0
    
    @property
    def text(self) -> str:
        """Get the full text of the line."""
        return ' '.join(word.text for word in self.words)
    
    @property
    def average_confidence(self) -> float:
        """Calculate average confidence of words in line."""
        if not self.words:
            return 0.0
        return sum(w.confidence for w in self.words) / len(self.words)
    
    def compute_bbox(self) -> Tuple[int, int, int, int]:
        """Compute bounding box from words."""
        if not self.words:
            return (0, 0, 0, 0)
        
        x1 = min(w.x1 for w in self.words)
        y1 = min(w.y1 for w in self.words)
        x2 = max(w.x2 for w in self.words)
        y2 = max(w.y2 for w in self.words)
        
        self.bbox = (x1, y1, x2, y2)
        return self.bbox
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            'text': self.text,
            'words': [w.to_dict() for w in self.words],
            'bbox': list(self.bbox) if self.bbox else None,
            'line_index': self.line_index,
            'average_confidence': self.average_confidence
        }


@dataclass
class OCRResult:
    """
    Complete OCR result for a single image/page.
    
    This class encapsulates all OCR output including text, words,
    lines, and bounding boxes. It provides methods for accessing
    and exporting the data in various formats.
    
    Attributes:
        words: List of all words with bounding boxes
        lines: List of text lines (grouped words)
        image_width: Width of the source image in pixels
        image_height: Height of the source image in pixels
        language: OCR language used
        engine: OCR engine name
        processing_time: Time taken for OCR in seconds
        metadata: Additional metadata dictionary
        
    Example:
        >>> result = ocr_engine.extract(image)
        >>> print(f"Found {len(result.words)} words")
        >>> print(f"Full text: {result.text}")
    """
    words: List[OCRWord] = field(default_factory=list)
    lines: List[OCRLine] = field(default_factory=list)
    image_width: int = 0
    image_height: int = 0
    language: str = "eng"
    engine: str = "unknown"
    processing_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def text(self) -> str:
        """
        Get the full text content.
        
        Returns:
            All text joined with newlines between lines.
        """
        if self.lines:
            return '\n'.join(line.text for line in self.lines)
        return ' '.join(word.text for word in self.words)
    
    @property
    def word_count(self) -> int:
        """Get total number of words."""
        return len(self.words)
    
    @property
    def line_count(self) -> int:
        """Get total number of lines."""
        return len(self.lines)
    
    @property
    def average_confidence(self) -> float:
        """Calculate average confidence across all words."""
        if not self.words:
            return 0.0
        return sum(w.confidence for w in self.words) / len(self.words)
    
    def get_words_as_list(self) -> List[str]:
        """Get list of word texts only."""
        return [word.text for word in self.words]
    
    def get_bboxes_as_list(self) -> List[List[int]]:
        """Get list of bounding boxes only."""
        return [list(word.bbox) for word in self.words]
    
    def get_normalized_bboxes(self) -> List[List[int]]:
        """Get list of normalized bounding boxes."""
        return [
            list(word.normalized_bbox) if word.normalized_bbox else [0, 0, 0, 0]
            for word in self.words
        ]
    
    def normalize_bboxes(self, scale: int = 1000) -> None:
        """
        Normalize all bounding boxes to 0-scale range.
        
        This is required for LayoutLM models which expect
        normalized coordinates.
        
        Args:
            scale: Maximum value for normalized coordinates (default 1000).
        """
        if self.image_width == 0 or self.image_height == 0:
            return
        
        for word in self.words:
            x1 = int(word.x1 * scale / self.image_width)
            y1 = int(word.y1 * scale / self.image_height)
            x2 = int(word.x2 * scale / self.image_width)
            y2 = int(word.y2 * scale / self.image_height)
            
            # Clamp to valid range
            x1 = max(0, min(scale, x1))
            y1 = max(0, min(scale, y1))
            x2 = max(0, min(scale, x2))
            y2 = max(0, min(scale, y2))
            
            word.normalized_bbox = (x1, y1, x2, y2)
    
    def filter_by_confidence(self, min_confidence: float) -> 'OCRResult':
        """
        Create new result with only words above confidence threshold.
        
        Args:
            min_confidence: Minimum confidence score (0-100).
            
        Returns:
            New OCRResult with filtered words.
        """
        filtered_words = [w for w in self.words if w.confidence >= min_confidence]
        
        return OCRResult(
            words=filtered_words,
            lines=[],  # Lines would need to be reconstructed
            image_width=self.image_width,
            image_height=self.image_height,
            language=self.language,
            engine=self.engine,
            processing_time=self.processing_time,
            metadata=self.metadata.copy()
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for serialization."""
        return {
            'text': self.text,
            'word_count': self.word_count,
            'line_count': self.line_count,
            'average_confidence': self.average_confidence,
            'image_width': self.image_width,
            'image_height': self.image_height,
            'language': self.language,
            'engine': self.engine,
            'processing_time': self.processing_time,
            'words': [w.to_dict() for w in self.words],
            'lines': [l.to_dict() for l in self.lines],
            'metadata': self.metadata
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)
    
    def to_layoutlm_format(self) -> Dict[str, Any]:
        """
        Convert to format expected by LayoutLM models.
        
        Returns:
            Dictionary with 'words' and 'boxes' keys.
        """
        # Ensure bboxes are normalized
        if not self.words or self.words[0].normalized_bbox is None:
            self.normalize_bboxes()
        
        return {
            'words': [word.text for word in self.words],
            'boxes': [list(word.normalized_bbox) for word in self.words]
        }
    
    def is_empty(self) -> bool:
        """Check if OCR result is empty."""
        return len(self.words) == 0
    
    def __repr__(self) -> str:
        return (
            f"OCRResult(words={self.word_count}, lines={self.line_count}, "
            f"confidence={self.average_confidence:.1f}%)"
        )
