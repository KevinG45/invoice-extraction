"""
Donut Extractor Module.

This module provides the DonutExtractor class for OCR-free document
understanding using the Donut (Document Understanding Transformer) model.

Donut Advantages:
    - OCR-free: No need for separate OCR pipeline
    - End-to-end: Single model for all extraction
    - Fast: No multi-stage processing
    - Excellent for structured data like line items

Supported Models:
    - naver-clova-ix/donut-base-finetuned-cord-v2 (receipts/invoices)
    - naver-clova-ix/donut-base-finetuned-docvqa (document QA)
    - naver-clova-ix/donut-base (base model for fine-tuning)

Author: ML Engineering Team
"""

import re
import json
import time
from typing import Optional, Dict, Any, List, Union
from pathlib import Path
from PIL import Image

from config import get_config
from src.utils.logger import get_logger
from src.utils.exceptions import ModelLoadError, InferenceError
from .line_item import LineItem

# Initialize module logger
logger = get_logger(__name__)


class DonutExtractor:
    """
    Donut-based document extractor for OCR-free extraction.
    
    Uses the Donut model for end-to-end document understanding,
    particularly effective for structured data like line items.
    
    Donut generates JSON-like output directly from images without
    requiring OCR preprocessing.
    
    Attributes:
        model_name: Name of the pre-trained Donut model
        device: Device for inference (cpu/cuda)
        processor: Donut processor for image preprocessing
        model: Donut model instance
        
    Example:
        >>> extractor = DonutExtractor()
        >>> line_items = extractor.extract_line_items(image)
        >>> for item in line_items:
        ...     print(f"{item.description}: ${item.total}")
    """
    
    # Pre-trained models
    CORD_MODEL = "naver-clova-ix/donut-base-finetuned-cord-v2"  # Best for receipts/invoices
    DOCVQA_MODEL = "naver-clova-ix/donut-base-finetuned-docvqa"  # For document QA
    BASE_MODEL = "naver-clova-ix/donut-base"  # Base model
    
    # Task prompts for Donut
    TASK_PROMPTS = {
        'cord': "<s_cord-v2>",  # CORD format extraction
        'docvqa': "<s_docvqa>",  # Document QA
        'parse': "<s_synthdog>"  # General parsing
    }
    
    def __init__(
        self,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
        task: str = "cord"
    ) -> None:
        """
        Initialize the Donut extractor.
        
        Args:
            model_name: Pre-trained model name. Defaults to CORD model.
            device: Device for inference ('cpu', 'cuda').
            task: Task type ('cord', 'docvqa', 'parse').
        """
        self.model_name = model_name or get_config(
            "model.donut.name", 
            self.CORD_MODEL
        )
        self.device = device or get_config("model.inference.device", "cpu")
        self.task = task
        self.task_prompt = self.TASK_PROMPTS.get(task, self.TASK_PROMPTS['cord'])
        
        # Model components
        self.processor = None
        self.model = None
        self._is_loaded = False
        
        # Lazy loading - don't load until first use
        logger.info(f"DonutExtractor initialized (lazy loading): {self.model_name}")
    
    def _ensure_loaded(self) -> None:
        """Load model if not already loaded (lazy loading)."""
        if self._is_loaded:
            return
        
        try:
            import torch
            from transformers import DonutProcessor, VisionEncoderDecoderModel
            
            logger.info(f"Loading Donut model: {self.model_name}")
            start_time = time.time()
            
            # Load processor
            self.processor = DonutProcessor.from_pretrained(self.model_name)
            
            # Load model
            self.model = VisionEncoderDecoderModel.from_pretrained(self.model_name)
            
            # Move to device
            if self.device == "cuda" and torch.cuda.is_available():
                self.model = self.model.cuda()
                logger.info("Donut model loaded on CUDA")
            else:
                self.device = "cpu"
                logger.info("Donut model loaded on CPU")
            
            # Set to evaluation mode
            self.model.eval()
            
            self._is_loaded = True
            load_time = time.time() - start_time
            logger.info(f"Donut model loaded in {load_time:.2f}s")
            
        except ImportError as e:
            raise ModelLoadError(
                self.model_name,
                f"Required packages not installed: {e}. "
                "Install with: pip install transformers torch"
            )
        except Exception as e:
            raise ModelLoadError(self.model_name, str(e))
    
    def extract_structured(
        self,
        image: Image.Image,
        prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract structured data from document image.
        
        Donut generates JSON-like output that is parsed into
        a Python dictionary.
        
        Args:
            image: PIL Image of the document.
            prompt: Optional custom prompt. Uses task prompt if None.
            
        Returns:
            Dictionary with extracted structured data.
            
        Example:
            >>> data = extractor.extract_structured(image)
            >>> print(data.get('menu', []))  # Line items
            >>> print(data.get('total', {}))  # Totals
        """
        self._ensure_loaded()
        
        import torch
        
        start_time = time.time()
        
        try:
            # Ensure RGB
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Prepare image
            pixel_values = self.processor(
                images=image,
                return_tensors="pt"
            ).pixel_values
            
            if self.device == "cuda":
                pixel_values = pixel_values.cuda()
            
            # Generate with task prompt
            task_prompt = prompt or self.task_prompt
            decoder_input_ids = self.processor.tokenizer(
                task_prompt,
                add_special_tokens=False,
                return_tensors="pt"
            ).input_ids
            
            if self.device == "cuda":
                decoder_input_ids = decoder_input_ids.cuda()
            
            # Generate output
            with torch.no_grad():
                outputs = self.model.generate(
                    pixel_values,
                    decoder_input_ids=decoder_input_ids,
                    max_length=self.model.decoder.config.max_position_embeddings,
                    early_stopping=True,
                    pad_token_id=self.processor.tokenizer.pad_token_id,
                    eos_token_id=self.processor.tokenizer.eos_token_id,
                    use_cache=True,
                    num_beams=1,  # Greedy for speed
                    bad_words_ids=[[self.processor.tokenizer.unk_token_id]],
                    return_dict_in_generate=True,
                )
            
            # Decode output
            sequence = self.processor.batch_decode(outputs.sequences)[0]
            
            # Parse the output
            result = self._parse_donut_output(sequence)
            
            processing_time = time.time() - start_time
            logger.info(f"Donut extraction completed in {processing_time:.2f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"Donut extraction failed: {e}")
            raise InferenceError(f"Donut extraction failed: {str(e)}")
    
    def _parse_donut_output(self, sequence: str) -> Dict[str, Any]:
        """
        Parse Donut's output sequence into structured data.
        
        Uses the processor's built-in token2json() method which correctly
        handles the nested XML-like token format from CORD v2.
        
        Args:
            sequence: Raw output from Donut model.
            
        Returns:
            Parsed dictionary with structured data.
        """
        # Clean up the sequence
        sequence = sequence.replace(self.processor.tokenizer.eos_token, "")
        sequence = sequence.replace(self.processor.tokenizer.pad_token, "")
        
        logger.debug(f"Raw Donut output: {sequence[:500]}")
        
        # Method 1: Use the processor's built-in token2json (preferred)
        try:
            parsed = self.processor.token2json(sequence)
            logger.debug(f"token2json parsed: {parsed}")
            
            if parsed and isinstance(parsed, dict):
                # Flatten nested structure for CORD format
                result = self._flatten_cord_output(parsed)
                return result
        except Exception as e:
            logger.warning(f"token2json parsing failed: {e}")
        
        # Method 2: Manual regex fallback
        try:
            result = self._manual_parse(sequence)
            if result:
                return result
        except Exception as e:
            logger.warning(f"Manual parsing also failed: {e}")
        
        return {'raw_output': sequence}
    
    def _flatten_cord_output(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        """
        Flatten CORD v2 output into a standardized format.
        
        CORD v2 outputs nested structures like:
        {"menu": [{"nm": ..., "cnt": ..., "price": ...}], "total": {"total_price": ...}}
        
        Args:
            parsed: Dictionary from token2json.
            
        Returns:
            Flattened dictionary with 'menu' list.
        """
        result = {}
        
        # Handle menu/line items
        menu_items = parsed.get('menu', [])
        if isinstance(menu_items, dict):
            menu_items = [menu_items]  # Single item, wrap in list
        
        if menu_items:
            result['menu'] = []
            for item in menu_items:
                if isinstance(item, dict):
                    result['menu'].append(item)
        
        # Handle totals
        total_data = parsed.get('total', {})
        if isinstance(total_data, dict):
            for key, val in total_data.items():
                result[key] = val
        elif isinstance(total_data, list):
            for entry in total_data:
                if isinstance(entry, dict):
                    for key, val in entry.items():
                        result[key] = val
        
        # Handle sub_total
        sub_total = parsed.get('sub_total', {})
        if isinstance(sub_total, dict):
            for key, val in sub_total.items():
                result[f'sub_{key}'] = val
        
        # Copy any other top-level fields
        for key, val in parsed.items():
            if key not in ('menu', 'total', 'sub_total') and not isinstance(val, (dict, list)):
                result[key] = val
        
        logger.debug(f"Flattened CORD output: {len(result.get('menu', []))} items")
        return result
    
    def _manual_parse(self, sequence: str) -> Dict[str, Any]:
        """
        Manual fallback parser for Donut output.
        
        Extracts key-value pairs from nested XML-like tokens.
        
        Args:
            sequence: Cleaned output string from Donut.
            
        Returns:
            Parsed dictionary.
        """
        result = {}
        current_items = []
        current_item = {}
        
        # Find all leaf-level key-value pairs: <s_key>value</s_key>
        pattern = r'<s_([^>]+)>([^<]+)</s_\1>'
        matches = re.findall(pattern, sequence)
        
        line_item_keys = {'nm', 'item_nm', 'prod_item_cd', 'cnt', 'num',
                          'price', 'unitprice', 'total_price', 'sub_nm',
                          'sub_cnt', 'sub_price', 'etc'}
        
        for key, value in matches:
            value = value.strip()
            if not value:
                continue
            
            if key in line_item_keys:
                current_item[key] = value
                # When we hit a price-like field, that usually ends an item
                if key in ('total_price', 'price', 'unitprice'):
                    if current_item:
                        current_items.append(current_item)
                        current_item = {}
            else:
                result[key] = value
        
        # Don't forget the last item
        if current_item and any(k in current_item for k in ('nm', 'item_nm', 'cnt', 'price')):
            current_items.append(current_item)
        
        if current_items:
            result['menu'] = current_items
        
        logger.debug(f"Manual parse found {len(current_items)} items")
        return result
    
    def extract_line_items(
        self,
        image: Image.Image
    ) -> List[LineItem]:
        """
        Extract line items from invoice/receipt image.
        
        This is a specialized method for extracting table rows
        as LineItem objects.
        
        Args:
            image: PIL Image of the invoice.
            
        Returns:
            List of LineItem objects.
            
        Example:
            >>> items = extractor.extract_line_items(invoice_image)
            >>> total = sum(item.total for item in items if item.total)
        """
        # Get structured data
        data = self.extract_structured(image)
        
        # Extract menu/items
        items = data.get('menu', [])
        
        if not items:
            # Try alternative keys
            items = data.get('items', [])
            items = items or data.get('line_items', [])
        
        # Convert to LineItem objects
        line_items = []
        for idx, item_data in enumerate(items):
            try:
                line_item = LineItem.from_donut_output(item_data, row_index=idx)
                if line_item.is_valid:
                    line_items.append(line_item)
            except Exception as e:
                logger.warning(f"Failed to parse line item {idx}: {e}")
        
        logger.info(f"Extracted {len(line_items)} line items with Donut")
        return line_items
    
    def extract_total(self, image: Image.Image) -> Optional[Dict[str, Any]]:
        """
        Extract total amounts from document.
        
        Args:
            image: PIL Image of the document.
            
        Returns:
            Dictionary with total information.
        """
        data = self.extract_structured(image)
        
        total_info = {}
        
        # Common total field names
        total_fields = ['total', 'sub_total', 'subtotal', 'total_price', 
                       'grand_total', 'tax', 'service']
        
        for field in total_fields:
            if field in data:
                total_info[field] = data[field]
        
        return total_info if total_info else None
    
    def answer_question(
        self,
        image: Image.Image,
        question: str
    ) -> str:
        """
        Answer a question about the document (DocVQA mode).
        
        Uses the DocVQA version of Donut for question answering.
        
        Args:
            image: PIL Image of the document.
            question: Question to answer.
            
        Returns:
            Answer string.
        """
        # Switch to DocVQA task
        original_task = self.task_prompt
        self.task_prompt = f"<s_docvqa><s_question>{question}</s_question><s_answer>"
        
        try:
            result = self.extract_structured(image)
            answer = result.get('answer', result.get('raw_output', ''))
            
            # Clean answer
            answer = re.sub(r'</s_answer>', '', str(answer))
            return answer.strip()
            
        finally:
            # Restore original task
            self.task_prompt = original_task
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the Donut model.
        
        Returns:
            Dictionary with model details.
        """
        return {
            'model_name': self.model_name,
            'device': self.device,
            'task': self.task,
            'is_loaded': self._is_loaded,
            'capabilities': ['line_items', 'structured_extraction', 'totals'],
            'ocr_free': True
        }
    
    def __repr__(self) -> str:
        return f"DonutExtractor(model={self.model_name}, device={self.device})"
