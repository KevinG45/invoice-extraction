# Invoice Extraction System v2.0.0 - Deployment Guide

## Quick Start

### CLI Mode
```bash
# Install dependencies
pip install -r requirements_2026.txt

# Extract from a single file
python main_2026.py --input invoice.pdf

# Extract from a directory
python main_2026.py --input data/input/INVOICES --output outputs/extractions

# Specify output formats
python main_2026.py --input invoice.pdf --format json excel csv

# Force a specific model
python main_2026.py --input invoice.pdf --model sarvam_vision

# Skip validation (faster, less reliable)
python main_2026.py --input invoice.pdf --skip-validation
```

### API Server Mode
```bash
# Start API server
python main_2026.py --api --port 8000

# Or with uvicorn directly
uvicorn src.api.api_service_2026:create_app --host 0.0.0.0 --port 8000 --factory
```

API Docs: http://localhost:8000/docs

### Docker
```bash
# Build
docker build -t invoice-extraction:2.0.0 .

# Run API
docker run -p 8000:8000 invoice-extraction:2.0.0

# Run CLI
docker run -v $(pwd)/data:/app/data -v $(pwd)/outputs:/app/outputs \
    invoice-extraction:2.0.0 \
    python main_2026.py --input data/input/INVOICES
```

---

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐
│  Input       │────▶│ Preprocessing │────▶│ Model Router  │
│  (PDF/Image) │     │ + Quality     │     │               │
└─────────────┘     └──────────────┘     │ ┌───────────┐ │
                                          │ │ Sarvam    │ │
                                          │ │ Vision 3B │ │
                                          │ └───────────┘ │
                                          │ ┌───────────┐ │
                                          │ │ DeepSeek  │ │
                                          │ │ OCR 2     │ │
                                          │ └───────────┘ │
                                          │ ┌───────────┐ │
                                          │ │ PaddleOCR │ │
                                          │ │ VL 1.5    │ │
                                          │ └───────────┘ │
                                          └───────┬───────┘
                                                  │
                                          ┌───────▼───────┐
                                          │ 6-Layer       │
                                          │ Validation    │
                                          │ Framework     │
                                          │               │
                                          │ L1: RAG       │
                                          │ L2: Multi-Agt │
                                          │ L3: Q-A-E     │
                                          │ L4: Neuro-Sym │
                                          │ L5: Confidence│
                                          │ L6: Cross-Mdl │
                                          └───────┬───────┘
                                                  │
                                          ┌───────▼───────┐
                                          │ Export        │
                                          │ JSON/Excel/CSV│
                                          └───────────────┘
```

## Model Setup

### Sarvam Vision 3B (Primary - API)
```bash
export SARVAM_API_KEY="your_api_key_here"
```
Free tier available at https://sarvam.ai

### DeepSeek-OCR 2 (Local Verification)
Auto-downloads from HuggingFace on first use (~6GB).
Requires GPU with 8GB+ VRAM for optimal performance.

### PaddleOCR-VL 1.5 (Fallback)
```bash
pip install paddleocr>=3.0.0 paddlepaddle>=3.0.0
```

## Configuration

Edit `config/models_2026.yaml` to customize:
- Model selection and routing thresholds
- Validation layer toggles and thresholds
- Output formats and paths
- API settings

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SARVAM_API_KEY` | Sarvam Vision API key | None |
| `LOG_LEVEL` | Logging level | INFO |
| `OUTPUT_DIR` | Output directory | outputs/extractions |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/models` | List available models |
| GET | `/config` | Current configuration |
| POST | `/extract` | Single invoice extraction |
| POST | `/extract/batch` | Batch extraction (up to 50) |

### Example: Extract via API
```bash
curl -X POST http://localhost:8000/extract \
    -F "file=@invoice.pdf" \
    -H "accept: application/json"
```

## Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Header Accuracy | ≥98% | invoice_number, date, total |
| Line Item Accuracy | ≥96% | description, qty, price |
| Processing Speed | ≤4 sec/page | Single page invoice |
| Batch Throughput | ≥150/hour | Standard invoices |
| Hallucination Detection | ≥95% | 6-layer framework |
| False Positive Rate | ≤8% | Validation rejections |

## Running Tests
```bash
pip install pytest pytest-cov
pytest tests/ -v
pytest tests/ -v --cov=src --cov-report=html
```
