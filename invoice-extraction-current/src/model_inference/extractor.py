"""
Invoice Extractor Module.

This module provides the main InvoiceExtractor class that uses
pre-trained Transformer models to extract invoice header fields.

Approach:
    Uses a Document Question Answering (DocQA) approach where
    specific questions are asked for each field (e.g., "What is
    the invoice number?").

Supported Models:
    - impira/layoutlm-document-qa (default, optimized for DocQA)
    - microsoft/layoutlmv3-base
    - microsoft/layoutlm-base-uncased

Author: ML Engineering Team
"""

import time
from typing import Optional, Dict, Any, List, Union
from pathlib import Path
from PIL import Image

from config import get_config
from src.utils.logger import get_logger
from src.utils.exceptions import ModelLoadError, InferenceError
from src.ocr_engine.ocr_result import OCRResult
from .extraction_result import ExtractionResult

# Initialize module logger
logger = get_logger(__name__)


class InvoiceExtractor:
    """
    Transformer-based invoice field extractor.
    
    Uses pre-trained Document Question Answering models to extract
    invoice header fields. No training or fine-tuning is required.
    
    The extractor uses a QA approach where it asks specific questions
    for each target field (e.g., "What is the invoice number?").
    
    Attributes:
        model_name: Name of the pre-trained model
        device: Device to run inference on (cpu/cuda)
        pipeline: Hugging Face pipeline instance
        field_questions: Mapping of fields to questions
        
    Example:
        >>> extractor = InvoiceExtractor()
        >>> result = extractor.extract(image, ocr_result)
        >>> print(result.invoice_number)
        >>> print(result.confidence_scores)
    """
    
    # Default model for document QA
    DEFAULT_MODEL = "impira/layoutlm-document-qa"
    
    # Fallback model if default not available
    FALLBACK_MODEL = "deepset/roberta-base-squad2"
    
    def __init__(
        self,
        model_name: Optional[str] = None,
        device: Optional[str] = None
    ) -> None:
        """
        Initialize the invoice extractor.
        
        Args:
            model_name: Pre-trained model name. If None, uses config.
            device: Device for inference ('cpu', 'cuda', 'mps').
                   If None, uses config or auto-detects.
        """
        # Load configuration
        self.model_name = model_name or get_config("model.name", self.DEFAULT_MODEL)
        self.device = device or get_config("model.inference.device", "cpu")
        self.max_length = get_config("model.inference.max_length", 512)
        
        # Load field questions from config
        self.field_questions = self._load_field_questions()
        
        # Initialize model pipeline
        self.pipeline = None
        self.use_document_qa = True
        self._initialize_model()
        
        logger.info(f"InvoiceExtractor initialized with model: {self.model_name}")
    
    def _load_field_questions(self) -> Dict[str, Dict[str, Any]]:
        """
        Load field extraction questions from configuration.
        
        Returns:
            Dictionary mapping field names to question configs.
        """
        default_questions = {
            'invoice_number': {
                'question': 'What is the invoice number?',
                'aliases': ['Invoice No', 'Invoice #', 'Inv No', 'Bill No']
            },
            'invoice_date': {
                'question': 'What is the invoice date?',
                'aliases': ['Date', 'Invoice Date', 'Bill Date']
            },
            'vendor_name': {
                'question': 'What is the vendor or seller company name?',
                'aliases': ['Vendor', 'Seller', 'From', 'Company']
            },
            'customer_name': {
                'question': 'What is the customer or buyer name?',
                'aliases': ['Customer', 'Buyer', 'Bill To', 'Ship To']
            },
            'total_amount': {
                'question': 'What is the total amount?',
                'aliases': ['Total', 'Grand Total', 'Amount Due', 'Total Due']
            },
            'payment_due_date': {
                'question': 'What is the payment due date?',
                'aliases': ['Due Date', 'Payment Due', 'Pay By']
            }
        }
        
        # Try to load from config
        config_fields = get_config("model.extraction_fields", {})
        
        if config_fields:
            for field, settings in config_fields.items():
                if field in default_questions:
                    default_questions[field].update(settings)
        
        return default_questions
    
    def _initialize_model(self) -> None:
        """
        Initialize the Transformer model pipeline.
        
        Tries to load the specified model, with fallback options
        if the primary model is not available.
        
        Raises:
            ModelLoadError: If no model can be loaded.
        """
        try:
            from transformers import pipeline
            
            logger.info(f"Loading model: {self.model_name}")
            
            # Try to load document-qa pipeline
            try:
                self.pipeline = pipeline(
                    "document-question-answering",
                    model=self.model_name,
                    device=0 if self.device == "cuda" else -1
                )
                self.use_document_qa = True
                logger.info(f"Loaded document-qa pipeline successfully")
                
            except Exception as e:
                logger.warning(f"Could not load document-qa pipeline: {e}")
                logger.info("Falling back to question-answering pipeline")
                
                # Fallback to regular QA pipeline
                try:
                    self.pipeline = pipeline(
                        "question-answering",
                        model=self.FALLBACK_MODEL,
                        device=0 if self.device == "cuda" else -1
                    )
                    self.use_document_qa = False
                    self.model_name = self.FALLBACK_MODEL
                    logger.info(f"Loaded QA pipeline with {self.FALLBACK_MODEL}")
                    
                except Exception as fallback_error:
                    raise ModelLoadError(
                        self.model_name,
                        f"Failed to load any model: {fallback_error}"
                    )
            
        except ImportError:
            raise ModelLoadError(
                self.model_name,
                "transformers package not installed. Install with: pip install transformers"
            )
    
    def extract(
        self,
        image: Image.Image,
        ocr_result: Optional[OCRResult] = None,
        source_file: Optional[str] = None
    ) -> ExtractionResult:
        """
        Extract invoice fields from an image.
        
        This is the main extraction method. It uses the pre-trained
        model to answer questions about invoice fields.
        
        Args:
            image: PIL Image of the invoice.
            ocr_result: Pre-computed OCR result (optional, used for
                       context in non-document-qa models).
            source_file: Original filename for metadata.
            
        Returns:
            ExtractionResult containing all extracted fields.
            
        Example:
            >>> result = extractor.extract(image)
            >>> print(f"Invoice: {result.invoice_number}")
            >>> print(f"Total: {result.total_amount}")
        """
        start_time = time.time()
        
        # Create result object
        result = ExtractionResult(
            source_file=source_file,
            model_name=self.model_name
        )
        
        try:
            # Ensure image is in correct format
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Extract each field
            for field_name, field_config in self.field_questions.items():
                question = field_config['question']
                
                try:
                    answer, confidence = self._extract_field(
                        image=image,
                        question=question,
                        ocr_result=ocr_result
                    )
                    
                    if answer:
                        result.set_field(field_name, answer, confidence)
                        result.raw_extractions[field_name] = {
                            'question': question,
                            'answer': answer,
                            'confidence': confidence
                        }
                        logger.debug(
                            f"Extracted {field_name}: '{answer}' "
                            f"(confidence: {confidence:.2f})"
                        )
                    else:
                        result.add_warning(f"Could not extract {field_name}")
                        
                except Exception as e:
                    logger.warning(f"Error extracting {field_name}: {e}")
                    result.add_warning(f"Error extracting {field_name}: {str(e)}")
            
            # Calculate processing time
            result.processing_time = time.time() - start_time
            
            logger.info(
                f"Extraction complete: {len(result.extracted_fields)}/6 fields, "
                f"avg confidence: {result.average_confidence:.2f}, "
                f"time: {result.processing_time:.2f}s"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            result.add_error(f"Extraction failed: {str(e)}")
            result.processing_time = time.time() - start_time
            return result
    
    def _extract_field(
        self,
        image: Image.Image,
        question: str,
        ocr_result: Optional[OCRResult] = None
    ) -> tuple:
        """
        Extract a single field using the QA model.
        
        Args:
            image: Invoice image.
            question: Question to ask about the field.
            ocr_result: Optional OCR result for context.
            
        Returns:
            Tuple of (answer, confidence).
        """
        if self.pipeline is None:
            return None, 0.0
        
        try:
            if self.use_document_qa:
                # Document QA - pass image directly
                result = self.pipeline(
                    image=image,
                    question=question
                )
                
                if isinstance(result, list) and len(result) > 0:
                    result = result[0]
                
                answer = result.get('answer', '')
                confidence = result.get('score', 0.0)
                
            else:
                # Regular QA - need text context
                if ocr_result is None or ocr_result.is_empty():
                    return None, 0.0
                
                context = ocr_result.text
                
                result = self.pipeline(
                    question=question,
                    context=context
                )
                
                answer = result.get('answer', '')
                confidence = result.get('score', 0.0)
            
            # Clean answer
            answer = self._clean_answer(answer)
            
            return answer, confidence
            
        except Exception as e:
            logger.debug(f"Field extraction error: {e}")
            return None, 0.0
    
    def _clean_answer(self, answer: str) -> str:
        """
        Clean and normalize extracted answer.
        
        Args:
            answer: Raw answer from model.
            
        Returns:
            Cleaned answer string.
        """
        if not answer:
            return ""
        
        # Strip whitespace
        answer = answer.strip()
        
        # Remove common prefixes/suffixes
        prefixes_to_remove = [':', '-', '.', ',']
        while answer and answer[0] in prefixes_to_remove:
            answer = answer[1:].strip()
        while answer and answer[-1] in prefixes_to_remove:
            answer = answer[:-1].strip()
        
        return answer
    
    def extract_with_fallback(
        self,
        image: Image.Image,
        ocr_result: OCRResult,
        source_file: Optional[str] = None
    ) -> ExtractionResult:
        """
        Extract fields with regex fallback for missing fields.
        
        First tries the model, then uses regex patterns on OCR text
        to find any missing fields.
        
        Args:
            image: Invoice image.
            ocr_result: OCR result with text.
            source_file: Original filename.
            
        Returns:
            ExtractionResult with model + regex extractions.
        """
        # First, try model extraction
        result = self.extract(image, ocr_result, source_file)
        
        # If some fields are missing, try regex fallback
        if result.missing_fields and ocr_result and not ocr_result.is_empty():
            self._apply_regex_fallback(result, ocr_result.text)
        
        return result
    
    def _apply_regex_fallback(self, result: ExtractionResult, text: str) -> None:
        """
        Apply regex patterns to find missing fields.
        
        Args:
            result: ExtractionResult to update.
            text: OCR text to search.
        """
        import re
        
        patterns = {
            'invoice_number': [
                r'Invoice\s*(?:#|No\.?|Number)?\s*[:\s]?\s*([A-Z0-9-]+)',
                r'INV[:\s-]?\s*([A-Z0-9-]+)',
                r'Bill\s*(?:#|No\.?)?\s*[:\s]?\s*([A-Z0-9-]+)'
            ],
            'total_amount': [
                r'Total\s*(?:Amount|Due)?\s*[:\s]?\s*\$?\s*([\d,]+\.?\d*)',
                r'Grand\s*Total\s*[:\s]?\s*\$?\s*([\d,]+\.?\d*)',
                r'Amount\s*Due\s*[:\s]?\s*\$?\s*([\d,]+\.?\d*)'
            ],
            'invoice_date': [
                r'(?:Invoice\s*)?Date\s*[:\s]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                r'Dated?\s*[:\s]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4})'
            ],
            'payment_due_date': [
                r'Due\s*Date\s*[:\s]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                r'Pay(?:ment)?\s*(?:Due\s*)?By\s*[:\s]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'
            ]
        }
        
        for field in result.missing_fields:
            if field not in patterns:
                continue
            
            for pattern in patterns[field]:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    value = match.group(1).strip()
                    if value:
                        result.set_field(field, value, 0.3)  # Low confidence for regex
                        result.add_warning(f"{field} extracted via regex fallback")
                        logger.debug(f"Regex fallback for {field}: {value}")
                        break
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the loaded model.
        
        Returns:
            Dictionary with model details.
        """
        return {
            'model_name': self.model_name,
            'device': self.device,
            'use_document_qa': self.use_document_qa,
            'max_length': self.max_length,
            'fields': list(self.field_questions.keys())
        }
