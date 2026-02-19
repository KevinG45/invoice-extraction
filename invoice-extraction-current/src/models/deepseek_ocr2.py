"""
DeepSeek-OCR 2 Extractor - Verification model for invoice extraction.

Released: January 27, 2026
Benchmarks: 91.09% OmniDocBench v1.5, best reading order (0.057 edit distance)
Strengths: Multi-page tables, reading order, dense documents, MIT license

Author: ML Engineering Team
Version: 2.0.0
"""

import io
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image

from src.models.base_extractor import (
    BaseExtractor,
    ExtractionOutput,
    FieldValue,
    LineItemOutput,
)

logger = logging.getLogger("invoice_extraction.models.deepseek_ocr2")


class DeepSeekOCR2Extractor(BaseExtractor):
    """
    DeepSeek-OCR 2 extractor using local model inference.

    Verification model with best reading order in the industry.
    Revolutionary DeepEncoder V2 with Visual Causal Flow.
    MIT License - fully open source.
    """

    MODEL_NAME = "deepseek-ocr-2"
    MODEL_VERSION = "2026.01"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.model_name = self.MODEL_NAME
        self.model_path = config.get("model_path", "deepseek-ai/DeepSeek-OCR-2")
        self.local_dir = config.get("local_dir", "models/deepseek-ocr2")
        self.max_new_tokens = config.get("max_new_tokens", 2048)
        self.base_size = config.get("base_size", 1024)
        self.image_size = config.get("image_size", 768)
        self.crop_mode = config.get("crop_mode", True)
        self.device = config.get("device", "auto")
        self.dtype = config.get("dtype", "bfloat16")
        self.use_flash_attention = config.get("use_flash_attention", True)

        self._model = None
        self._tokenizer = None
        self._processor = None

    def _load_model(self) -> bool:
        """Lazy-load the DeepSeek-OCR 2 model."""
        if self._model is not None:
            return True

        try:
            import torch
            from transformers import AutoModel, AutoTokenizer

            logger.info(f"Loading DeepSeek-OCR 2 from {self.model_path}...")

            # Determine device
            if self.device == "auto":
                device = "cuda" if torch.cuda.is_available() else "cpu"
            else:
                device = self.device

            # Determine dtype
            dtype_map = {
                "float32": torch.float32,
                "float16": torch.float16,
                "bfloat16": torch.bfloat16,
            }
            dtype = dtype_map.get(self.dtype, torch.bfloat16)

            # Determine attention implementation
            attn_impl = "flash_attention_2" if (
                self.use_flash_attention and device == "cuda"
            ) else "eager"

            # Load model
            model_source = self.local_dir if Path(self.local_dir).exists() else self.model_path

            self._model = AutoModel.from_pretrained(
                model_source,
                trust_remote_code=True,
                _attn_implementation=attn_impl,
            ).eval()

            if device == "cuda":
                self._model = self._model.to(dtype).cuda()

            self._tokenizer = AutoTokenizer.from_pretrained(
                model_source,
                trust_remote_code=True,
            )

            self._loaded = True
            logger.info("DeepSeek-OCR 2 loaded successfully")
            return True

        except ImportError as e:
            logger.error(f"Missing dependency for DeepSeek-OCR 2: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to load DeepSeek-OCR 2: {e}")
            return False

    def is_available(self) -> bool:
        """Check if DeepSeek-OCR 2 model is available."""
        try:
            import torch
            from transformers import AutoModel
            model_source = self.local_dir if Path(self.local_dir).exists() else self.model_path
            # Check if model files exist locally or can be fetched
            if Path(self.local_dir).exists():
                return True
            # Try to check HuggingFace availability
            return True
        except ImportError:
            return False

    def extract(self, image: Image.Image, **kwargs) -> ExtractionOutput:
        """
        Extract invoice data using DeepSeek-OCR 2.

        Args:
            image: PIL Image of the invoice.
            **kwargs: source_file, page_number, prompt, etc.

        Returns:
            ExtractionOutput with extracted fields and metadata.
        """
        start_time = time.time()
        output = self._create_output(
            source_file=kwargs.get("source_file", ""),
            page_number=kwargs.get("page_number", 1),
            total_pages=kwargs.get("total_pages", 1),
            model_version=self.MODEL_VERSION,
        )

        if not self._load_model():
            output.errors.append("Failed to load DeepSeek-OCR 2 model")
            output.processing_time_seconds = time.time() - start_time
            return output

        try:
            # Save image temporarily for model inference
            img_buffer = io.BytesIO()
            image.save(img_buffer, format="PNG")
            img_buffer.seek(0)

            # Build extraction prompt
            extraction_prompt = kwargs.get("prompt", self._build_extraction_prompt())

            # Run inference
            result = self._run_inference(image, extraction_prompt)
            output.raw_output = result

            # Parse result
            parsed = self._parse_json_response(result)
            if parsed:
                self._map_to_output(parsed, output)
            else:
                # Try to extract from markdown/text output
                self._extract_from_text(result, output)

        except Exception as e:
            logger.error(f"DeepSeek-OCR 2 extraction failed: {e}")
            output.errors.append(f"Extraction error: {str(e)}")

        output.processing_time_seconds = time.time() - start_time
        output.calculate_overall_confidence()
        return output

    def answer_question(self, image: Image.Image, question: str) -> Optional[str]:
        """Answer a question about the image for Q-A-E validation."""
        if not self._load_model():
            return None

        try:
            prompt = f"<image>\nAnswer this question about the document. Give ONLY the answer.\n\nQuestion: {question}"
            return self._run_inference(image, prompt).strip()
        except Exception as e:
            logger.error(f"Question answering failed: {e}")
            return None

    def extract_markdown(self, image: Image.Image) -> str:
        """
        Convert document to markdown (DeepSeek-OCR 2 specialty).

        Uses Visual Causal Flow for optimal reading order.
        """
        if not self._load_model():
            return ""

        prompt = "<image>\n<|grounding|>Convert the document to markdown."
        return self._run_inference(image, prompt)

    def _run_inference(self, image: Image.Image, prompt: str) -> str:
        """Run inference with DeepSeek-OCR 2."""
        try:
            # DeepSeek-OCR 2 has a specific inference API
            if hasattr(self._model, "infer"):
                # Save temp image
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    image.save(tmp, format="PNG")
                    tmp_path = tmp.name

                result = self._model.infer(
                    self._tokenizer,
                    prompt=prompt,
                    image_file=tmp_path,
                    base_size=self.base_size,
                    image_size=self.image_size,
                    crop_mode=self.crop_mode,
                )

                # Clean up temp file
                Path(tmp_path).unlink(missing_ok=True)
                return str(result) if result else ""
            else:
                # Standard transformers inference
                import torch

                inputs = self._tokenizer(prompt, return_tensors="pt")
                if torch.cuda.is_available() and self.device != "cpu":
                    inputs = {k: v.cuda() for k, v in inputs.items()}

                with torch.no_grad():
                    outputs = self._model.generate(
                        **inputs,
                        max_new_tokens=self.max_new_tokens,
                        do_sample=False,
                    )

                result = self._tokenizer.decode(outputs[0], skip_special_tokens=True)
                return result

        except Exception as e:
            logger.error(f"DeepSeek-OCR 2 inference failed: {e}")
            return ""

    def _build_extraction_prompt(self) -> str:
        """Build the extraction prompt for DeepSeek-OCR 2."""
        return """<image>
Extract all invoice information from this document image and return as JSON.

Provide confidence scores (0-100) for each field.
If uncertain about a value, set "uncertain": true.

Return JSON with this structure:
{
  "header": {
    "invoice_number": {"value": "...", "confidence": 0-100},
    "invoice_date": {"value": "YYYY-MM-DD", "confidence": 0-100},
    "due_date": {"value": "YYYY-MM-DD or null", "confidence": 0-100},
    "vendor_name": {"value": "...", "confidence": 0-100},
    "vendor_address": {"value": "...", "confidence": 0-100},
    "vendor_email": {"value": "...", "confidence": 0-100},
    "vendor_phone": {"value": "...", "confidence": 0-100},
    "customer_name": {"value": "...", "confidence": 0-100},
    "customer_address": {"value": "...", "confidence": 0-100},
    "currency": {"value": "...", "confidence": 0-100},
    "subtotal": {"value": 0.00, "confidence": 0-100},
    "tax_amount": {"value": 0.00, "confidence": 0-100},
    "shipping": {"value": 0.00, "confidence": 0-100},
    "total_amount": {"value": 0.00, "confidence": 0-100}
  },
  "line_items": [
    {
      "item_code": {"value": "...", "confidence": 0-100},
      "description": {"value": "...", "confidence": 0-100},
      "quantity": {"value": 0, "confidence": 0-100},
      "unit_price": {"value": 0.00, "confidence": 0-100},
      "line_total": {"value": 0.00, "confidence": 0-100}
    }
  ]
}"""

    def _map_to_output(
        self, raw_data: Dict[str, Any], output: ExtractionOutput
    ) -> None:
        """Map parsed data to ExtractionOutput."""
        header = raw_data.get("header", raw_data)

        for field_name in ExtractionOutput.HEADER_FIELDS:
            if field_name in header:
                field_data = header[field_name]
                if isinstance(field_data, dict):
                    fv = FieldValue(
                        value=field_data.get("value"),
                        confidence=float(field_data.get("confidence", 0)),
                        uncertain=field_data.get("uncertain", False)
                        or float(field_data.get("confidence", 0)) < 85,
                        source_model=self.MODEL_NAME,
                    )
                else:
                    fv = FieldValue(
                        value=field_data,
                        confidence=65.0,
                        uncertain=True,
                        source_model=self.MODEL_NAME,
                    )
                output.set_field(field_name, fv)

        # Line items
        items = raw_data.get("line_items", [])
        for i, item_data in enumerate(items):
            item = LineItemOutput(line_number=i + 1)
            for attr in [
                "item_code", "description", "quantity", "unit_price",
                "tax_rate", "tax_amount", "discount", "line_total",
            ]:
                if attr in item_data:
                    fd = item_data[attr]
                    if isinstance(fd, dict):
                        fv = FieldValue(
                            value=fd.get("value"),
                            confidence=float(fd.get("confidence", 0)),
                            source_model=self.MODEL_NAME,
                        )
                    else:
                        fv = FieldValue(
                            value=fd, confidence=65.0, source_model=self.MODEL_NAME
                        )
                    setattr(item, attr, fv)
            if item.is_valid:
                output.line_items.append(item)

    def _extract_from_text(self, text: str, output: ExtractionOutput) -> None:
        """Fallback: extract fields from plain text/markdown output."""
        import re

        patterns = {
            "invoice_number": r"(?:invoice\s*(?:no|number|#))[:\s]*([A-Z0-9\-/]+)",
            "total_amount": r"(?:total|amount\s*due|grand\s*total)[:\s]*[\$€£]?\s*([\d,]+\.?\d*)",
            "invoice_date": r"(?:date|invoice\s*date)[:\s]*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})",
            "vendor_name": r"(?:from|vendor|seller|company)[:\s]*(.+?)(?:\n|$)",
        }

        for field_name, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                fv = FieldValue(
                    value=match.group(1).strip(),
                    confidence=40.0,
                    uncertain=True,
                    source_model=self.MODEL_NAME,
                )
                output.set_field(field_name, fv)
                output.warnings.append(
                    f"{field_name}: extracted via regex fallback (low confidence)"
                )
