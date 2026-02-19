"""
Sarvam Vision 3B Extractor - Primary model for invoice extraction.

Released: February 5, 2026
Benchmarks: 84.3% olmOCR-Bench, 93.28% OmniDocBench v1.5
Strengths: Complex layouts, tables, 22 Indic languages, formulas

Author: ML Engineering Team
Version: 2.0.0
"""

import base64
import io
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

import requests
from PIL import Image

from src.models.base_extractor import (
    BaseExtractor,
    ExtractionOutput,
    FieldValue,
    LineItemOutput,
)

logger = logging.getLogger("invoice_extraction.models.sarvam_vision")


class SarvamVisionExtractor(BaseExtractor):
    """
    Sarvam Vision 3B extractor using the Sarvam AI API.

    Primary model for general invoice extraction.
    Beats Gemini 3 Pro and GPT-5.2 on OCR benchmarks.
    FREE API access during February 2026.
    """

    MODEL_NAME = "sarvam-vision-3b"
    MODEL_VERSION = "2026.02"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.model_name = self.MODEL_NAME
        self.api_url = config.get("api_url", "https://api.sarvam.ai/vision/document")
        self.api_key = config.get("api_key") or os.environ.get("SARVAM_API_KEY", "")
        self.max_tokens = config.get("max_tokens", 4096)
        self.temperature = config.get("temperature", 0.05)
        self.timeout = config.get("timeout", 30)
        self.retry_count = config.get("retry_count", 3)
        self.retry_delay = config.get("retry_delay", 2)
        self._prompt_template = config.get("prompt_template", self._default_prompt())

    def is_available(self) -> bool:
        """Check if Sarvam Vision API is accessible."""
        if not self.api_key:
            logger.warning("SARVAM_API_KEY not set. Sarvam Vision unavailable.")
            return False
        try:
            resp = requests.get(
                self.api_url.replace("/vision/document", "/health"),
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10,
            )
            return resp.status_code in (200, 401, 403)
        except requests.RequestException:
            logger.warning("Sarvam Vision API unreachable.")
            return False

    def extract(self, image: Image.Image, **kwargs) -> ExtractionOutput:
        """
        Extract invoice data using Sarvam Vision API.

        Args:
            image: PIL Image of the invoice.
            **kwargs: source_file, page_number, etc.

        Returns:
            ExtractionOutput with extracted fields and confidence scores.
        """
        start_time = time.time()
        output = self._create_output(
            source_file=kwargs.get("source_file", ""),
            page_number=kwargs.get("page_number", 1),
            total_pages=kwargs.get("total_pages", 1),
            model_version=self.MODEL_VERSION,
        )

        try:
            # Convert image to bytes
            img_buffer = io.BytesIO()
            image.save(img_buffer, format="PNG")
            img_bytes = img_buffer.getvalue()

            # Build request
            prompt = kwargs.get("prompt", self._prompt_template)

            # Call API with retries
            response = self._call_api_with_retry(img_bytes, prompt)

            if response is None:
                output.errors.append("All API call attempts failed")
                output.processing_time_seconds = time.time() - start_time
                return output

            # Parse response
            raw_data = self._parse_json_response(response)
            output.raw_output = response

            if not raw_data:
                output.errors.append("Failed to parse API response as JSON")
                output.processing_time_seconds = time.time() - start_time
                return output

            # Map parsed data to output
            self._map_to_output(raw_data, output)

        except Exception as e:
            logger.error(f"Sarvam Vision extraction failed: {e}")
            output.errors.append(f"Extraction error: {str(e)}")

        output.processing_time_seconds = time.time() - start_time
        output.calculate_overall_confidence()
        return output

    def answer_question(self, image: Image.Image, question: str) -> Optional[str]:
        """Answer a specific question about the invoice image (for Q-A-E validation)."""
        try:
            img_buffer = io.BytesIO()
            image.save(img_buffer, format="PNG")
            img_bytes = img_buffer.getvalue()

            prompt = f"Answer this question about the document image. Give ONLY the answer, nothing else.\n\nQuestion: {question}"
            response = self._call_api_with_retry(img_bytes, prompt)
            return response.strip() if response else None
        except Exception as e:
            logger.error(f"Question answering failed: {e}")
            return None

    def _call_api_with_retry(
        self, img_bytes: bytes, prompt: str
    ) -> Optional[str]:
        """Call Sarvam Vision API with retry logic."""
        for attempt in range(self.retry_count):
            try:
                # Encode image as base64
                img_b64 = base64.b64encode(img_bytes).decode("utf-8")

                payload = {
                    "image": img_b64,
                    "prompt": prompt,
                    "max_tokens": self.max_tokens,
                    "temperature": self.temperature,
                }

                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }

                response = requests.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )

                if response.status_code == 200:
                    result = response.json()
                    return result.get("text", result.get("content", json.dumps(result)))
                elif response.status_code == 429:
                    wait = self.retry_delay * (attempt + 1)
                    logger.warning(f"Rate limited. Waiting {wait}s...")
                    time.sleep(wait)
                else:
                    logger.warning(
                        f"API returned {response.status_code}: {response.text}"
                    )

            except requests.Timeout:
                logger.warning(f"API timeout (attempt {attempt + 1})")
            except requests.RequestException as e:
                logger.warning(f"API request failed (attempt {attempt + 1}): {e}")

            if attempt < self.retry_count - 1:
                time.sleep(self.retry_delay)

        return None

    def _map_to_output(
        self, raw_data: Dict[str, Any], output: ExtractionOutput
    ) -> None:
        """Map parsed JSON to ExtractionOutput fields."""
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
                        confidence=70.0,
                        uncertain=True,
                        source_model=self.MODEL_NAME,
                    )
                output.set_field(field_name, fv)

        # Parse line items
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
                            uncertain=fd.get("uncertain", False),
                            source_model=self.MODEL_NAME,
                        )
                    else:
                        fv = FieldValue(
                            value=fd, confidence=70.0, source_model=self.MODEL_NAME
                        )
                    setattr(item, attr, fv)
            if item.is_valid:
                output.line_items.append(item)

    def _default_prompt(self) -> str:
        """Default extraction prompt for Sarvam Vision."""
        return """You are an expert invoice data extraction system. Extract ALL information from this invoice image.

CRITICAL RULES (Hallucination Prevention):
1. Provide confidence score (0-100) for EVERY field
2. If confidence < 85, set "uncertain": true
3. NEVER guess - express uncertainty instead
4. Verify all calculations before outputting
5. If a field is not visible, set value to null with confidence 0

Extract to this exact JSON structure:
{
  "header": {
    "invoice_number": {"value": "...", "confidence": 0-100, "uncertain": false},
    "invoice_date": {"value": "YYYY-MM-DD", "confidence": 0-100, "uncertain": false},
    "due_date": {"value": "YYYY-MM-DD or null", "confidence": 0-100, "uncertain": false},
    "vendor_name": {"value": "...", "confidence": 0-100, "uncertain": false},
    "vendor_address": {"value": "...", "confidence": 0-100, "uncertain": false},
    "vendor_email": {"value": "...", "confidence": 0-100, "uncertain": false},
    "vendor_phone": {"value": "...", "confidence": 0-100, "uncertain": false},
    "customer_name": {"value": "...", "confidence": 0-100, "uncertain": false},
    "customer_address": {"value": "...", "confidence": 0-100, "uncertain": false},
    "currency": {"value": "USD/EUR/etc", "confidence": 0-100, "uncertain": false},
    "subtotal": {"value": 0.00, "confidence": 0-100, "uncertain": false},
    "tax_amount": {"value": 0.00, "confidence": 0-100, "uncertain": false},
    "shipping": {"value": 0.00, "confidence": 0-100, "uncertain": false},
    "total_amount": {"value": 0.00, "confidence": 0-100, "uncertain": false}
  },
  "line_items": [
    {
      "item_code": {"value": "...", "confidence": 0-100},
      "description": {"value": "...", "confidence": 0-100},
      "quantity": {"value": 0, "confidence": 0-100},
      "unit_price": {"value": 0.00, "confidence": 0-100},
      "tax_rate": {"value": 0.00, "confidence": 0-100},
      "tax_amount": {"value": 0.00, "confidence": 0-100},
      "discount": {"value": 0.00, "confidence": 0-100},
      "line_total": {"value": 0.00, "confidence": 0-100}
    }
  ]
}

REMEMBER: Better to say "uncertain" than to guess wrong. Penalize confident errors."""
