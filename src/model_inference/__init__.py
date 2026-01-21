"""
Model Inference Module for Invoice Extraction System.

This module provides Transformer-based field extraction using
pre-trained layout-aware models like LayoutLMv3.

Features:
    - Pre-trained model loading (no fine-tuning required)
    - Question-answering approach for field extraction
    - Confidence score extraction
    - Standardized JSON output

Model Options:
    - microsoft/layoutlmv3-base
    - impira/layoutlm-document-qa
    - microsoft/layoutlm-base-uncased

Author: ML Engineering Team
"""

from .extractor import InvoiceExtractor
from .extraction_result import ExtractionResult

__all__ = ['InvoiceExtractor', 'ExtractionResult']
