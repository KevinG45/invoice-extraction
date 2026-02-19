"""
Baseline Invoice Extraction Package.

A clean, high-accuracy invoice extraction pipeline that works locally
without paid APIs. Uses a dual-track approach:

  Track A (Digital PDFs): pdfplumber → perfect text + table extraction
  Track B (Images/Scans): Tesseract OCR → text extraction

Both tracks then feed into:
  → Regex + keyword pattern matching for header field extraction
  → LayoutLMv3 Document QA for semantic field extraction
  → Table parsing for line item extraction
  → Post-processing for validation and normalization

Architecture Overview:
  ┌─────────────────┐
  │  Document Input  │ (PDF or Image)
  └────────┬────────┘
           │
  ┌────────▼────────┐
  │ Document Loader  │ Detects type, loads pages
  └────────┬────────┘
           │
  ┌────────▼────────┐          ┌──────────────────┐
  │ Text Extraction  │◄─────────│ Digital PDF:      │
  │                  │          │  pdfplumber       │
  │                  │          ├──────────────────┤
  │                  │◄─────────│ Image/Scan:       │
  │                  │          │  Tesseract OCR    │
  └────────┬────────┘          └──────────────────┘
           │
  ┌────────▼────────┐
  │ Field Extraction │ Regex + LayoutLMv3 QA
  └────────┬────────┘
           │
  ┌────────▼────────┐
  │ Table Extraction │ pdfplumber tables + regex rows
  └────────┬────────┘
           │
  ┌────────▼────────┐
  │ Post-Processing  │ Normalize, validate, score
  └────────┬────────┘
           │
  ┌────────▼────────┐
  │     Export       │ JSON, Excel, CSV
  └─────────────────┘

Author: ML Engineering Team
Date: 2026-02-19
Version: 3.0.0 (Baseline)
"""

from src.baseline.result import (
    InvoiceResult,
    HeaderField,
    LineItem,
    ExtractionMetadata,
)
from src.baseline.pipeline import BaselinePipeline

__all__ = [
    "BaselinePipeline",
    "InvoiceResult",
    "HeaderField",
    "LineItem",
    "ExtractionMetadata",
]
