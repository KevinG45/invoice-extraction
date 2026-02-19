"""
Invoice Extraction System 2026 - Model Extractors Package.

Provides unified interfaces for 2026 state-of-the-art VLM models:
- Sarvam Vision 3B (Primary)
- DeepSeek-OCR 2 (Verification)
- PaddleOCR-VL 1.5 (Fallback)
- Qwen3-VL 8B (Long Documents)

Author: ML Engineering Team
Version: 2.0.0
"""

from src.models.base_extractor import BaseExtractor, ExtractionOutput
from src.models.sarvam_vision import SarvamVisionExtractor
from src.models.deepseek_ocr2 import DeepSeekOCR2Extractor
from src.models.paddleocr_vl import PaddleOCRVLExtractor
from src.models.model_router import ModelRouter

__all__ = [
    "BaseExtractor",
    "ExtractionOutput",
    "SarvamVisionExtractor",
    "DeepSeekOCR2Extractor",
    "PaddleOCRVLExtractor",
    "ModelRouter",
]
