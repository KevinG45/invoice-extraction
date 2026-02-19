"""
Model Inference Module for Invoice Extraction System.

This module provides Transformer-based field extraction using
pre-trained layout-aware models like LayoutLMv3 and Donut.

Features:
    - Pre-trained model loading (no fine-tuning required)
    - Question-answering approach for field extraction
    - OCR-free extraction with Donut
    - Hybrid model for headers + line items
    - Confidence score extraction
    - Standardized JSON output

Model Options:
    - microsoft/layoutlmv3-base (headers)
    - impira/layoutlm-document-qa (headers)
    - naver-clova-ix/donut-base-finetuned-cord-v2 (line items)

Hybrid Approach:
    - LayoutLMv3: Best for header fields (layout understanding)
    - Donut: Best for line items (OCR-free, end-to-end)

Author: ML Engineering Team
"""

from .extractor import InvoiceExtractor
from .extraction_result import ExtractionResult
from .line_item import LineItem
from .donut_extractor import DonutExtractor
from .hybrid_extractor import HybridExtractor, HybridExtractionResult

__all__ = [
    'InvoiceExtractor',
    'ExtractionResult',
    'LineItem',
    'DonutExtractor',
    'HybridExtractor',
    'HybridExtractionResult'
]
