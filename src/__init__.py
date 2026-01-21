"""
Invoice Extraction System - Source Package.

This package contains all core modules for the intelligent invoice
header extraction system. Each module has a single responsibility
following SOLID principles.

Modules:
    - input_handler: PDF and image input processing
    - ocr_engine: Text and bounding box extraction
    - model_inference: Transformer-based field extraction
    - postprocessor: Validation and normalization
    - output_handler: Excel and database output
    - evaluation: Quality metrics and accuracy computation

Architecture:
    Input → OCR → Model Inference → Post-Processing → Output
                                                    ↓
                                              Evaluation
"""

__version__ = "1.0.0"
__author__ = "ML Engineering Team"

# Module imports will be added as they are implemented
__all__ = [
    'input_handler',
    'ocr_engine', 
    'model_inference',
    'postprocessor',
    'output_handler',
    'evaluation',
    'utils'
]
