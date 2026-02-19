# API Reference

This document provides detailed API documentation for all public modules and classes in the Invoice Extraction System.

## Table of Contents

- [Input Handler](#input-handler)
- [OCR Engine](#ocr-engine)
- [Model Inference](#model-inference)
- [Post Processor](#post-processor)
- [Output Handler](#output-handler)
- [Evaluation](#evaluation)
- [Configuration](#configuration)

---

## Input Handler

### `InputHandler`

Main class for handling document input and normalization.

```python
from src.input_handler import InputHandler

handler = InputHandler()
document = handler.load("invoice.pdf")
```

#### Methods

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `load(path)` | `path: str` | `dict` | Load and process a single document |
| `load_batch(paths)` | `paths: List[str]` | `List[dict]` | Load multiple documents |
| `detect_file_type(path)` | `path: str` | `str` | Detect file type ('pdf', 'image') |

#### Return Structure

```python
{
    'image': PIL.Image,        # Normalized image
    'images': List[PIL.Image], # For multi-page PDFs
    'path': str,               # Original file path
    'file_type': str,          # 'pdf' or 'image'
    'metadata': dict           # File metadata
}
```

---

## OCR Engine

### `OCREngine`

Unified interface for OCR processing with multiple backend support.

```python
from src.ocr_engine import OCREngine

engine = OCREngine(backend='tesseract')
result = engine.process(image)
```

#### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `backend` | `str` | `'tesseract'` | OCR backend ('tesseract', 'easyocr', 'paddleocr') |

#### Methods

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `process(image)` | `image: PIL.Image` | `OCRResult` | Process image and extract text |
| `get_text(image)` | `image: PIL.Image` | `str` | Get plain text from image |

### `OCRResult`

Dataclass containing OCR results with spatial information.

```python
@dataclass
class OCRResult:
    full_text: str
    words: List[OCRWord]
    lines: List[OCRLine]
    confidence: float
```

#### Key Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `to_layoutlm_format()` | `dict` | Convert to LayoutLM input format |
| `normalize_bboxes(width, height)` | `OCRResult` | Normalize bounding boxes to 0-1000 |
| `get_text()` | `str` | Get full text content |

---

## Model Inference

### `InvoiceExtractor`

Extracts invoice header fields using LayoutLM-based document understanding.

```python
from src.model_inference import InvoiceExtractor

extractor = InvoiceExtractor()
result = extractor.extract(image, ocr_result, source_file="invoice.pdf")
```

#### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `model_name` | `str` | Config-based | HuggingFace model name |
| `device` | `str` | Auto-detected | 'cuda' or 'cpu' |

#### Methods

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `extract(image, ocr_result, source_file)` | See below | `ExtractionResult` | Extract all header fields |
| `extract_field(field_name, image, ocr_text)` | Field name, image, text | `tuple` | Extract single field |

### `ExtractionResult`

Dataclass containing extracted fields and metadata.

```python
@dataclass
class ExtractionResult:
    invoice_number: Optional[str]
    invoice_date: Optional[str]
    vendor_name: Optional[str]
    customer_name: Optional[str]
    total_amount: Optional[str]
    payment_due_date: Optional[str]
    confidence_scores: Dict[str, float]
    source_file: Optional[str]
    extraction_timestamp: str
    model_name: str
    processing_time: float
    success: bool
```

#### Key Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `to_dict()` | `dict` | Convert to dictionary |
| `to_json()` | `str` | Convert to JSON string |
| `extraction_rate` | `float` | Percentage of fields extracted |
| `average_confidence` | `float` | Average confidence score |

---

## Post Processor

### `PostProcessor`

Normalizes and validates extracted data.

```python
from src.postprocessor import PostProcessor

processor = PostProcessor()
validated_result = processor.process(extraction_result)
```

#### Methods

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `process(result)` | `ExtractionResult` | `ExtractionResult` | Normalize and validate all fields |
| `normalize_date(date_str)` | `str` | `str` | Normalize date format |
| `normalize_amount(amount_str)` | `str` | `str` | Normalize amount format |
| `validate(result)` | `ExtractionResult` | `ValidationResult` | Validate all fields |

### Normalizers

```python
from src.postprocessor.normalizers import DateNormalizer, AmountNormalizer

# Date normalization
date_normalizer = DateNormalizer(output_format="%Y-%m-%d")
normalized_date = date_normalizer.normalize("15/01/2024")  # "2024-01-15"

# Amount normalization
amount_normalizer = AmountNormalizer(decimal_places=2)
normalized_amount = amount_normalizer.normalize("$1,234.56")  # "1234.56"
```

---

## Output Handler

### `OutputHandler`

Unified handler for Excel and database output.

```python
from src.output_handler import OutputHandler

handler = OutputHandler(excel_enabled=True, database_enabled=True)
output_info = handler.save(results, excel_filename="output.xlsx")
```

#### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `excel_enabled` | `bool` | `True` | Enable Excel export |
| `database_enabled` | `bool` | `True` | Enable database storage |

#### Methods

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `save(results, excel_filename)` | Results, optional filename | `dict` | Save to all enabled outputs |
| `to_excel(results, filename)` | Results, filename | `str` | Export to Excel file |
| `to_database(results)` | Results | `dict` | Save to database |
| `get_database_stats()` | None | `dict` | Get database statistics |
| `search_database(...)` | Various filters | `List[dict]` | Search database records |

### `ExcelExporter`

```python
from src.output_handler import ExcelExporter

exporter = ExcelExporter()
filepath = exporter.export(results, "invoices.xlsx")
```

### `DatabaseHandler`

```python
from src.output_handler import DatabaseHandler

db = DatabaseHandler("path/to/database.db")
db.insert(result)
all_records = db.get_all()
```

---

## Evaluation

### `Evaluator`

Main class for evaluating extraction accuracy.

```python
from src.evaluation import Evaluator

evaluator = Evaluator("ground_truth.json")
evaluation_result = evaluator.evaluate(extraction_results)
print(evaluation_result.print_report())
```

#### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `ground_truth_path` | `str` | `None` | Path to ground truth file |
| `case_sensitive` | `bool` | `False` | Case-sensitive comparison |
| `partial_match_threshold` | `float` | `0.8` | Threshold for partial matches |

#### Methods

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `evaluate(results, ground_truth)` | Results, optional GT | `EvaluationResult` | Evaluate all results |
| `evaluate_single(result, ground_truth)` | Single result, GT | `dict` | Evaluate single result |
| `generate_report(result, output_path, format)` | Result, path, format | `str` | Generate report (txt/json/html) |
| `load_ground_truth(path)` | Path to GT file | None | Load ground truth data |

### `EvaluationResult`

```python
@dataclass
class EvaluationResult:
    field_metrics: Dict[str, FieldMetrics]
    overall_accuracy: float
    overall_extraction_rate: float
    avg_confidence: float
    total_samples: int
    timestamp: str
```

---

## Configuration

### `ConfigurationManager`

Singleton class for managing application configuration.

```python
from config import get_config, ConfigurationManager

# Get a config value
model_name = get_config("model.name", "default-model")

# Access configuration manager directly
config = ConfigurationManager()
all_paths = config.get("paths")
```

#### Key Methods

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `get(key, default)` | Key path, default value | Any | Get config value |
| `set(key, value)` | Key path, value | None | Set config value |
| `reload()` | None | None | Reload config from file |

### Configuration File Structure

```yaml
# config/settings.yaml

project:
  name: "Invoice Extraction System"
  version: "1.0.0"

paths:
  input_dir: "inputs"
  output_dir: "outputs"
  logs_dir: "logs"

ocr:
  backend: "tesseract"
  language: "eng"
  
model:
  name: "impira/layoutlm-document-qa"
  device: "auto"
  confidence_threshold: 0.5

output:
  excel:
    enabled: true
    include_metadata: true
  database:
    enabled: true
    name: "invoice_extractions.db"

logging:
  level: "INFO"
  file_enabled: true
```

---

## Error Handling

All modules use custom exceptions defined in `src/utils/exceptions.py`:

```python
from src.utils.exceptions import (
    InvoiceExtractionError,  # Base exception
    InputError,              # Input handling errors
    OCRError,                # OCR processing errors
    ModelError,              # Model inference errors
    ValidationError,         # Validation errors
    ExcelExportError,        # Excel export errors
    DatabaseError,           # Database operation errors
    ConfigurationError       # Configuration errors
)
```

Each exception includes contextual information for debugging:

```python
try:
    result = extractor.extract(image, ocr_result)
except ModelError as e:
    print(f"Operation: {e.operation}")
    print(f"Details: {e.details}")
```
