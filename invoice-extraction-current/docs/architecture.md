# System Architecture

## Overview

The Intelligent Invoice Header Extraction System follows a modular pipeline architecture designed for:
- **Maintainability**: Each module has a single responsibility
- **Extensibility**: Easy to swap components (e.g., different OCR engines)
- **Reliability**: Comprehensive error handling and logging
- **Scalability**: Designed for batch processing

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              EXTRACTION PIPELINE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌──────────────┐                                                          │
│   │   main.py    │  Entry Point & CLI                                       │
│   └──────┬───────┘                                                          │
│          │                                                                   │
│          ▼                                                                   │
│   ┌──────────────┐                                                          │
│   │  pipeline.py │  Orchestration Layer                                     │
│   └──────┬───────┘                                                          │
│          │                                                                   │
│   ┌──────┴──────────────────────────────────────────────────────────┐       │
│   │                     PROCESSING MODULES                          │       │
│   │                                                                  │       │
│   │  ┌───────────────┐  ┌───────────────┐  ┌───────────────────┐   │       │
│   │  │ input_handler │─▶│  ocr_engine   │─▶│ model_inference   │   │       │
│   │  │               │  │               │  │                   │   │       │
│   │  │ - PDF detect  │  │ - Tesseract   │  │ - LayoutLMv3      │   │       │
│   │  │ - Image load  │  │ - Text+BBox   │  │ - Field extraction│   │       │
│   │  │ - Normalize   │  │ - Normalize   │  │ - Confidence      │   │       │
│   │  └───────────────┘  └───────────────┘  └────────┬──────────┘   │       │
│   │                                                  │              │       │
│   │                                                  ▼              │       │
│   │  ┌───────────────────────────────────────────────────────────┐ │       │
│   │  │                    postprocessor                          │ │       │
│   │  │                                                           │ │       │
│   │  │  - Date normalization      - Amount parsing               │ │       │
│   │  │  - Validation rules        - Missing field handling       │ │       │
│   │  │  - Confidence thresholds   - Duplicate detection          │ │       │
│   │  └────────────────────────────────┬──────────────────────────┘ │       │
│   │                                   │                            │       │
│   └───────────────────────────────────┼────────────────────────────┘       │
│                                       │                                     │
│                                       ▼                                     │
│   ┌───────────────────────────────────────────────────────────────────┐    │
│   │                        output_handler                              │    │
│   │                                                                    │    │
│   │  ┌─────────────────┐              ┌─────────────────────────┐    │    │
│   │  │  Excel Export   │              │    SQLite Database       │    │    │
│   │  │  - Formatted    │              │    - Schema management   │    │    │
│   │  │  - Multi-sheet  │              │    - Duplicate check     │    │    │
│   │  └─────────────────┘              └─────────────────────────┘    │    │
│   └───────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│   ┌───────────────────────────────────────────────────────────────────┐    │
│   │                         evaluation                                 │    │
│   │                                                                    │    │
│   │  - Field accuracy    - Missing rate    - Exact match             │    │
│   │  - Confusion matrix  - Error analysis  - Report generation       │    │
│   └───────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                              SUPPORT LAYER                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐ │
│  │    config/      │  │    utils/       │  │        logs/                │ │
│  │                 │  │                 │  │                             │ │
│  │ - settings.yaml │  │ - logger.py     │  │ - extraction.log           │ │
│  │ - ConfigManager │  │ - helpers.py    │  │ - Rotation enabled         │ │
│  │                 │  │ - exceptions.py │  │                             │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Module Responsibilities

### 1. Input Handler (`input_handler.py`)
- **Purpose**: Accept and normalize input files
- **Inputs**: PDF, JPG, PNG, TIFF, BMP files
- **Outputs**: Normalized PIL Image objects
- **Key Features**:
  - File type detection
  - PDF to image conversion
  - Image orientation correction
  - Resolution normalization

### 2. OCR Engine (`ocr_engine.py`)
- **Purpose**: Extract text and spatial information
- **Inputs**: PIL Image
- **Outputs**: Structured OCR result (text, bounding boxes)
- **Key Features**:
  - Tesseract OCR integration
  - Bounding box extraction
  - Coordinate normalization
  - Replaceable engine design

### 3. Model Inference (`model_inference.py`)
- **Purpose**: Extract invoice fields using AI
- **Inputs**: OCR result with text and bounding boxes
- **Outputs**: Raw extracted fields with confidence
- **Key Features**:
  - LayoutLMv3 integration
  - Question-answering approach
  - Confidence score extraction
  - No training required

### 4. Post Processor (`postprocessor.py`)
- **Purpose**: Validate and normalize extracted data
- **Inputs**: Raw extracted fields
- **Outputs**: Clean, validated data
- **Key Features**:
  - Date format normalization
  - Currency parsing
  - Validation rules
  - Missing field handling

### 5. Output Handler (`output_handler.py`)
- **Purpose**: Persist extracted data
- **Inputs**: Validated extraction results
- **Outputs**: Excel file, database records
- **Key Features**:
  - Excel formatting
  - Database schema management
  - Duplicate prevention
  - Metadata inclusion

### 6. Evaluation (`evaluation.py`)
- **Purpose**: Measure system accuracy
- **Inputs**: Predictions, ground truth
- **Outputs**: Accuracy metrics, reports
- **Key Features**:
  - Field-level accuracy
  - Missing rate calculation
  - Error analysis
  - JSON report generation

## Design Decisions

### Why LayoutLMv3?
- Pre-trained on large document corpus
- Understands visual layout (not just text)
- No fine-tuning required for basic tasks
- Well-documented and maintained

### Why Tesseract OCR?
- Open-source and free
- Good accuracy for printed text
- Wide language support
- Easy to install and configure

### Why SQLite for Database?
- Zero configuration required
- Portable (single file)
- Sufficient for most use cases
- Easy to upgrade to PostgreSQL if needed

### Why YAML for Configuration?
- Human-readable format
- Supports complex nested structures
- Easy to modify without code changes
- Good Python library support

## Data Flow

```
Input File (PDF/Image)
        │
        ▼
┌───────────────────┐
│  Detect File Type │
└────────┬──────────┘
         │
    ┌────┴────┐
    ▼         ▼
  PDF       Image
    │         │
    ▼         │
Convert to    │
  Image       │
    │         │
    └────┬────┘
         │
         ▼
┌───────────────────┐
│ Normalize Image   │
│ (DPI, Orientation)│
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│   Run OCR         │
│ (Text + BBoxes)   │
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  Model Inference  │
│ (LayoutLMv3 QA)   │
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  Post-Process     │
│ (Validate/Clean)  │
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  Output           │
│ (Excel + DB)      │
└───────────────────┘
```

## Error Handling Strategy

1. **Graceful Degradation**: If one field fails, continue with others
2. **Comprehensive Logging**: All errors logged with context
3. **Custom Exceptions**: Specific exception types for different failures
4. **Never Crash**: Pipeline continues even if individual files fail
