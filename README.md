#  Intelligent Invoice Header Extraction System

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A production-ready, company-grade system for extracting header-level information from invoices using OCR and pre-trained layout-aware Transformer models.

## Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Architecture](#-architecture)
- [Installation](#-installation)
- [Quick Start](#-quick-start)
- [Configuration](#-configuration)
- [Project Structure](#-project-structure)
- [Usage](#-usage)
- [API Reference](#-api-reference)
- [Evaluation](#-evaluation)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)
- [License](#-license)

##  Overview

This system automates the extraction of key invoice header fields from various document formats (PDF, JPG, PNG). It uses a combination of OCR (Optical Character Recognition) and pre-trained layout-aware Transformer models to accurately identify and extract structured data.

### Extracted Fields

| Field | Description |
|-------|-------------|
| **Invoice Number** | Unique identifier for the invoice |
| **Invoice Date** | Date when the invoice was issued |
| **Vendor Name** | Name of the seller/supplier |
| **Customer Name** | Name of the buyer/recipient |
| **Total Amount** | Total amount due |
| **Payment Due Date** | Date by which payment is expected |

##  Features

- **Multi-format Support**: Process PDFs (digital and scanned) and images (JPG, PNG, TIFF)
- **Layout-aware Extraction**: Uses LayoutLMv3 for context-aware field extraction
- **Robust OCR**: Configurable OCR engine with multiple backend support
- **Data Validation**: Automatic date/currency normalization and validation
- **Dual Output**: Export to Excel and SQLite database
- **Confidence Scores**: Model confidence for each extracted field
- **Evaluation Metrics**: Built-in accuracy computation and reporting
- **Modular Design**: Easy to extend, maintain, and customize
- **Production-ready**: Comprehensive logging, error handling, and configuration

##  Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        INVOICE EXTRACTION PIPELINE                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐          │
│  │  INPUT   │───▶│   OCR    │───▶│  MODEL   │───▶│   POST   │          │
│  │ HANDLER  │    │  ENGINE  │    │INFERENCE │    │PROCESSOR │          │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘          │
│       │                                                │                │
│       │         PDF/Image          Text +             │                │
│       │         Processing         Bounding           │                │
│       ▼                            Boxes              ▼                │
│  ┌──────────┐                                   ┌──────────┐          │
│  │  FILE    │                                   │  OUTPUT  │          │
│  │DETECTION │                                   │ HANDLER  │          │
│  └──────────┘                                   └──────────┘          │
│                                                       │                │
│                                              ┌────────┴────────┐      │
│                                              ▼                 ▼      │
│                                         ┌────────┐       ┌────────┐  │
│                                         │ EXCEL  │       │DATABASE│  │
│                                         └────────┘       └────────┘  │
│                                                                        │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                        EVALUATION MODULE                         │  │
│  │            Field Accuracy • Missing Rate • Exact Match           │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                        │
└─────────────────────────────────────────────────────────────────────────┘
```

##  Installation

### Prerequisites

- Python 3.9 or higher
- Tesseract OCR installed on system
- Poppler (for PDF processing)

### Windows Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd invoice-extraction
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Tesseract OCR**
   - Download from: https://github.com/UB-Mannheim/tesseract/wiki
   - Add to PATH: `C:\Program Files\Tesseract-OCR`

5. **Install Poppler** (for PDF processing)
   - Download from: https://github.com/oschwartz10612/poppler-windows/releases
   - Add `bin` folder to PATH

### Linux/macOS Installation

```bash
# Ubuntu/Debian
sudo apt-get install tesseract-ocr poppler-utils

# macOS
brew install tesseract poppler
```

##  Quick Start

```python
from src.pipeline import InvoiceExtractionPipeline

# Initialize pipeline
pipeline = InvoiceExtractionPipeline()

# Process a single invoice
result = pipeline.process("path/to/invoice.pdf")
print(result)

# Process multiple invoices
results = pipeline.process_batch("path/to/invoice/folder/")

# Export to Excel
pipeline.export_to_excel(results, "output.xlsx")
```

##  Configuration

Configuration is managed through `config/settings.yaml`. Key settings:

```yaml
# OCR Configuration
ocr:
  engine: "pytesseract"
  tesseract:
    lang: "eng"
    psm: 3

# Model Configuration
model:
  name: "microsoft/layoutlmv3-base"
  device: "cpu"  # or "cuda" for GPU

# Output Configuration
output:
  excel:
    enabled: true
  database:
    enabled: true
    type: "sqlite"
```

##  Project Structure

```
invoice-extraction/
├── config/
│   ├── __init__.py          # Configuration manager
│   └── settings.yaml         # Main configuration file
├── src/
│   ├── __init__.py           # Package initialization
│   ├── input_handler.py      # PDF/Image input processing
│   ├── ocr_engine.py         # OCR text extraction
│   ├── model_inference.py    # Transformer model inference
│   ├── postprocessor.py      # Validation & normalization
│   ├── output_handler.py     # Excel & database output
│   ├── evaluation.py         # Accuracy metrics
│   ├── pipeline.py           # Main orchestration
│   └── utils/
│       ├── __init__.py
│       ├── logger.py         # Logging configuration
│       ├── helpers.py        # Utility functions
│       └── exceptions.py     # Custom exceptions
├── data/
│   ├── input/                # Input invoices
│   ├── temp/                 # Temporary processing files
│   └── ground_truth.json     # Evaluation ground truth
├── outputs/
│   ├── extractions/          # Extracted data
│   └── reports/              # Evaluation reports
├── logs/                     # Application logs
├── docs/                     # Documentation
│   ├── architecture.md
│   ├── api_reference.md
│   └── user_guide.md
├── tests/                    # Unit tests
├── requirements.txt          # Python dependencies
├── main.py                   # Entry point
└── README.md                 # This file
```

##  Usage

### Command Line Interface

```bash
# Process a single file
python main.py --input invoice.pdf --output results.xlsx

# Process a directory
python main.py --input ./invoices/ --output ./results/

# Run with evaluation
python main.py --input ./invoices/ --evaluate --ground-truth data/ground_truth.json
```

### Python API

```python
from src.input_handler import InputHandler
from src.ocr_engine import OCREngine
from src.model_inference import InvoiceExtractor
from src.postprocessor import PostProcessor
from src.output_handler import OutputHandler

# Step-by-step processing
input_handler = InputHandler()
image = input_handler.load("invoice.pdf")

ocr = OCREngine()
ocr_result = ocr.extract(image)

extractor = InvoiceExtractor()
raw_data = extractor.extract(ocr_result)

postprocessor = PostProcessor()
clean_data = postprocessor.process(raw_data)

output = OutputHandler()
output.to_excel(clean_data, "output.xlsx")
output.to_database(clean_data)
```

##  Evaluation

The system includes built-in evaluation capabilities:

```python
from src.evaluation import Evaluator

evaluator = Evaluator()
metrics = evaluator.compute_metrics(
    predictions=extracted_data,
    ground_truth="data/ground_truth.json"
)

print(f"Field Accuracy: {metrics['field_accuracy']:.2%}")
print(f"Missing Rate: {metrics['missing_rate']:.2%}")
```

##  Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| Tesseract not found | Add Tesseract to system PATH |
| PDF conversion fails | Install Poppler and add to PATH |
| CUDA out of memory | Set `device: "cpu"` in config |
| Low accuracy | Try different OCR settings or PSM mode |

### Debug Mode

Enable debug logging in `config/settings.yaml`:
```yaml
logging:
  level: "DEBUG"
```

##  Contributing

1. Fork the repository
2. Create a feature branch
3. Commit changes with clear messages
4. Submit a pull request

##  License

MIT License - see LICENSE file for details.

---


