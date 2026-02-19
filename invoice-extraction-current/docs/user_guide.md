# User Guide

This guide provides step-by-step instructions for using the Invoice Extraction System.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Command Line Usage](#command-line-usage)
3. [Python API Usage](#python-api-usage)
4. [Configuration](#configuration)
5. [Processing Workflows](#processing-workflows)
6. [Output Formats](#output-formats)
7. [Evaluation](#evaluation)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Prerequisites

Before using the system, ensure you have:

1. **Python 3.9+** installed
2. **Tesseract OCR** installed and in PATH
3. **Poppler** installed (for PDF processing)
4. All Python dependencies installed: `pip install -r requirements.txt`

### Quick Verification

```bash
# Check Python version
python --version

# Check Tesseract installation
tesseract --version

# Verify dependencies
python -c "from src.input_handler import InputHandler; print('Ready!')"
```

---

## Command Line Usage

### Basic Usage

```bash
# Process a single invoice
python main.py --input invoice.pdf --output results.xlsx

# Process a directory of invoices
python main.py --input ./invoices/ --output ./results/

# With debug output
python main.py --input invoice.pdf --output results.xlsx --debug
```

### Command Line Options

| Option | Short | Description |
|--------|-------|-------------|
| `--input` | `-i` | Input file or directory (required) |
| `--output` | `-o` | Output file or directory |
| `--config` | `-c` | Custom configuration file |
| `--no-excel` | | Disable Excel output |
| `--no-database` | | Disable database output |
| `--evaluate` | | Run evaluation after extraction |
| `--ground-truth` | `-gt` | Ground truth file for evaluation |
| `--debug` | | Enable debug logging |
| `--quiet` | `-q` | Suppress console output |

### Examples

```bash
# Process invoices with evaluation
python main.py -i ./invoices/ -o results.xlsx --evaluate -gt ground_truth.json

# Process without database storage
python main.py -i invoice.pdf --no-database

# Use custom configuration
python main.py -i invoices/ -c my_config.yaml
```

---

## Python API Usage

### Basic Pipeline

```python
from src.input_handler import InputHandler
from src.ocr_engine import OCREngine
from src.model_inference import InvoiceExtractor
from src.postprocessor import PostProcessor
from src.output_handler import OutputHandler

# Initialize components
input_handler = InputHandler()
ocr_engine = OCREngine()
extractor = InvoiceExtractor()
post_processor = PostProcessor()
output_handler = OutputHandler()

# Process an invoice
document = input_handler.load("invoice.pdf")
image = document['image']

# Run OCR
ocr_result = ocr_engine.process(image)

# Extract fields
extraction = extractor.extract(image, ocr_result, source_file="invoice.pdf")

# Post-process
validated = post_processor.process(extraction)

# Output results
output_handler.save(validated, excel_filename="result.xlsx")

# Print extracted data
print(f"Invoice Number: {validated.invoice_number}")
print(f"Total Amount: {validated.total_amount}")
print(f"Confidence: {validated.average_confidence:.2f}")
```

### Batch Processing

```python
from pathlib import Path
from main import run_extraction

# Process all invoices in a directory
results = run_extraction(
    input_path="./invoices/",
    output_path="./results/",
    enable_excel=True,
    enable_database=True
)

for result in results:
    print(f"{result['source_file']}: {result['invoice_number']}")
```

### Using Individual Components

#### OCR Only

```python
from PIL import Image
from src.ocr_engine import OCREngine

engine = OCREngine()
image = Image.open("document.png")
result = engine.process(image)

print(f"Extracted text:\n{result.full_text}")
print(f"Confidence: {result.confidence:.2f}")
```

#### Database Operations

```python
from src.output_handler import DatabaseHandler

db = DatabaseHandler()

# Search for invoices
invoices = db.search(vendor_name="Acme Corp")

# Get statistics
stats = db.get_statistics()
print(f"Total records: {stats['total_records']}")
print(f"Success rate: {stats['success_rate']:.1%}")

# Get all records
all_invoices = db.get_all(limit=100)
```

---

## Configuration

### Configuration File

The system uses `config/settings.yaml` for configuration:

```yaml
# Model settings
model:
  name: "impira/layoutlm-document-qa"
  fallback_model: "deepset/roberta-base-squad2"
  device: "auto"  # "auto", "cuda", or "cpu"
  confidence_threshold: 0.5

# OCR settings
ocr:
  backend: "tesseract"
  language: "eng"
  
# Output settings
output:
  excel:
    enabled: true
    include_metadata: true
    include_confidence: true
    sheet_name: "Extracted Data"
  database:
    enabled: true
    name: "invoice_extractions.db"
    avoid_duplicates: true
```

### Environment-Specific Configuration

Create separate config files for different environments:

```bash
# Development
python main.py -i invoices/ -c config/settings_dev.yaml

# Production
python main.py -i invoices/ -c config/settings_prod.yaml
```

---

## Processing Workflows

### Single Document Workflow

```
Document → Detect Type → Load/Convert → OCR → Extract → Validate → Output
```

### Batch Processing Workflow

```
Directory
    │
    ├── Scan for supported files
    │
    ├── For each file:
    │       │
    │       ├── Load document
    │       ├── Run OCR
    │       ├── Extract fields
    │       ├── Post-process
    │       └── Collect result
    │
    ├── Export to Excel
    │
    └── Save to Database
```

### Multi-Page PDF Workflow

```
Multi-page PDF
    │
    ├── Convert to images (one per page)
    │
    ├── For each page:
    │       │
    │       ├── Run OCR
    │       ├── Extract fields
    │       └── Store result
    │
    └── Combine/deduplicate results
```

---

## Output Formats

### Excel Output

The Excel file contains three sheets:

1. **Extracted Data**: Main extraction results
   - Invoice Number, Invoice Date, Vendor Name, etc.

2. **Metadata**: Processing information
   - Source File, Timestamp, Processing Time, Success, etc.

3. **Confidence Scores**: Field-level confidence
   - Confidence score for each extracted field

### Database Schema

```sql
CREATE TABLE invoice_headers (
    id INTEGER PRIMARY KEY,
    invoice_number TEXT,
    invoice_date TEXT,
    vendor_name TEXT,
    customer_name TEXT,
    total_amount TEXT,
    payment_due_date TEXT,
    source_file TEXT,
    extraction_timestamp TEXT,
    model_name TEXT,
    processing_time REAL,
    success INTEGER,
    extraction_rate REAL,
    average_confidence REAL,
    -- Individual field confidence scores
    invoice_number_confidence REAL,
    invoice_date_confidence REAL,
    vendor_name_confidence REAL,
    customer_name_confidence REAL,
    total_amount_confidence REAL,
    payment_due_date_confidence REAL,
    created_at TEXT
);
```

---

## Evaluation

### Creating Ground Truth

Create a JSON file with ground truth data:

```json
{
    "records": [
        {
            "source_file": "invoice_001.pdf",
            "invoice_number": "INV-2024-001",
            "invoice_date": "2024-01-15",
            "vendor_name": "Acme Corporation",
            "customer_name": "XYZ Industries",
            "total_amount": "1250.00",
            "payment_due_date": "2024-02-15"
        }
    ]
}
```

### Running Evaluation

```python
from src.evaluation import Evaluator

evaluator = Evaluator("ground_truth.json")
result = evaluator.evaluate(extraction_results)

# Print report
print(result.print_report())

# Generate HTML report
evaluator.generate_report(result, "report.html", format="html")
```

### Understanding Metrics

- **Accuracy**: Exact match rate
- **Extraction Rate**: Percentage of fields successfully extracted
- **Partial Match**: Fields that partially match (e.g., similar but not identical)
- **Average Confidence**: Model's confidence in extractions

---

## Best Practices

### Document Quality

1. **Resolution**: Use documents with at least 300 DPI
2. **Clarity**: Ensure text is legible and not blurry
3. **Orientation**: Documents should be properly oriented
4. **Format**: Prefer PDF over images when available

### Performance Optimization

1. **Batch Processing**: Process multiple files together
2. **GPU Usage**: Enable CUDA for faster model inference
3. **Configuration**: Tune confidence thresholds for your use case

### Data Quality

1. **Validation**: Review low-confidence extractions
2. **Ground Truth**: Maintain accurate ground truth for evaluation
3. **Monitoring**: Track accuracy metrics over time

---

## Troubleshooting

### Common Issues

#### "Tesseract not found"

```bash
# Windows
choco install tesseract

# Add to PATH
set PATH=%PATH%;C:\Program Files\Tesseract-OCR
```

#### "PDF processing error"

```bash
# Install poppler
choco install poppler

# Verify installation
pdfinfo --version
```

#### "CUDA out of memory"

```yaml
# In settings.yaml
model:
  device: "cpu"  # Force CPU usage
```

#### "Low extraction accuracy"

1. Check document quality
2. Adjust confidence threshold
3. Verify OCR is working correctly
4. Consider preprocessing images

### Debug Mode

Enable debug logging for detailed information:

```bash
python main.py -i invoice.pdf --debug
```

Or in code:

```python
import logging
logging.getLogger("invoice_extraction").setLevel(logging.DEBUG)
```

### Getting Help

1. Check the logs in `logs/extraction.log`
2. Review the API documentation in `docs/api_reference.md`
3. Examine the architecture in `docs/architecture.md`
