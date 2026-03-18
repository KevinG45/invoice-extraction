# Invoice Extraction + RAG System — Project Overview

> **Purpose of this document:** A single reference for understanding the current state of the project, what it can do, how to test it, and how to improve it. Intended for developers, testers, and contributors.

---

## Table of Contents

1. [Project Summary](#1-project-summary)
2. [Current Status](#2-current-status)
3. [Capabilities & Feature List](#3-capabilities--feature-list)
4. [System Architecture](#4-system-architecture)
5. [Extraction Pipeline — Stage by Stage](#5-extraction-pipeline--stage-by-stage)
6. [RAG System — Query & Retrieval](#6-rag-system--query--retrieval)
7. [API Reference](#7-api-reference)
8. [Data Schemas](#8-data-schemas)
9. [Technology Stack & Dependencies](#9-technology-stack--dependencies)
10. [Configuration Reference](#10-configuration-reference)
11. [How to Run](#11-how-to-run)
12. [Testing & Validation Guide](#12-testing--validation-guide)
13. [Known Limitations & Open Issues](#13-known-limitations--open-issues)
14. [Improvement Roadmap](#14-improvement-roadmap)
15. [Project Structure Reference](#15-project-structure-reference)

---

## 1. Project Summary

**Invoice Extraction + RAG System** is an end-to-end pipeline that:

1. **Extracts** structured data from invoice files (PDF, JPG, PNG, TIFF) using a combination of OCR engines and a local LLM.
2. **Stores** extracted data in multiple backends — JSON files, a SQLite relational database, a ChromaDB vector store, and a BM25 keyword index.
3. **Answers** natural-language questions about the indexed invoices using a multi-strategy Retrieval-Augmented Generation (RAG) pipeline.
4. **Exposes** all functionality through a REST API (FastAPI) and an interactive web frontend (Streamlit).

The system is designed to run **entirely locally** — no cloud APIs, no paid services. The LLM component uses [Ollama](https://ollama.com) to run open-source models on-device.

**Typical use cases:**
- Digitising and structuring paper or scanned invoices
- Searching a library of invoices by vendor, amount, date, or keyword
- Asking questions such as "What is the total amount across all invoices from ABC Ltd this year?"
- Auditing financial data with automated math-consistency validation

---

## 2. Current Status

### ✅ Implemented & Working

| Component | Status | Notes |
|-----------|--------|-------|
| Digital PDF extraction | ✅ Stable | Via `pdfplumber` + `PyMuPDF` |
| Scanned PDF / Image OCR | ✅ Stable | Tesseract (default); PaddleOCR optional |
| Table extraction from PDFs | ✅ Stable | Camelot → Tabula → regex fallback |
| LLM field extraction | ✅ Stable | Ollama (`qwen2.5:3b`), JSON retry logic |
| Field validation (math checks) | ✅ Stable | Line-item math, subtotal, total checks |
| JSON output | ✅ Stable | Per-invoice timestamped JSON files |
| SQLite persistence | ✅ Stable | `invoices`, `line_items`, `validation_reports` tables |
| ChromaDB vector indexing | ✅ Stable | Header + per-line-item chunking |
| BM25 keyword indexing | ✅ Stable | Auto-rebuilt on each extraction |
| Multi-strategy RAG router | ✅ Stable | SQL / BM25 / Vector / Hybrid selection |
| FastAPI REST endpoints | ✅ Stable | Single upload, batch ZIP, ask, index, health |
| Streamlit web UI | ✅ Stable | Extract tab + Ask tab |
| Docker image | ✅ Stable | Python 3.10-slim base |
| Batch processing script | ✅ Stable | All files in `data/input/INVOICES/` |
| Regression check scripts | ✅ Stable | Summary tables + known-issues tracking |

### ⚠️ Partial / Conditional

| Component | Status | Notes |
|-----------|--------|-------|
| PaddleOCR table extraction | ⚠️ Optional | Large (~2 GB); requires Python ≤3.12 and manual install |
| Ground truth evaluation | ⚠️ Minimal | `data/ground_truth.json` contains only 2 sample entries |
| Logo / vendor-name fallback | ⚠️ Fallback only | EasyOCR used when LLM returns blank vendor name |

### ❌ Not Yet Implemented

| Component | Status | Notes |
|-----------|--------|-------|
| Automated unit / integration tests | ❌ Missing | No `pytest` suite exists |
| CI/CD pipeline | ❌ Missing | No GitHub Actions or similar |
| API authentication | ❌ Missing | All endpoints are open |
| Async / parallel batch processing | ❌ Missing | Sequential only |
| Structured export (CSV, XLSX) | ❌ Missing | JSON and SQLite only |

---

## 3. Capabilities & Feature List

### Document Ingestion

- Accepts **PDF** (digital and scanned), **JPG**, **JPEG**, **PNG**, **TIFF**, **TIF** files
- Auto-detects document type: `digital` (selectable text), `scanned` (raster PDF), or `image`
- Handles multi-page documents; reports page count in metadata

### Data Extraction

Extracts the following fields from each invoice:

| Category | Fields |
|----------|--------|
| **Header** | Invoice number, invoice date, due date, purchase order number |
| **Vendor** | Name, address, email, phone, GSTIN/tax ID, website |
| **Bill-To** | Name, address, email |
| **Ship-To** | Name, address |
| **Financials** | Subtotal, discount, tax rate, tax amount, shipping, total amount, amount paid, amount due, currency |
| **Payment** | Payment terms, payment method, bank details (account, IFSC, name, branch) |
| **Line Items** | Per-line: description, quantity, unit, unit price, discount, tax rate, total |
| **Misc** | Notes / additional text |

### Validation

- **Line-item math check**: verifies `quantity × unit_price ≈ line_total` for each item
- **Subtotal check**: verifies `sum(line_item totals) ≈ subtotal`
- **Total consistency check**: verifies `subtotal + tax_amount + shipping − discount ≈ total_amount`
- Configurable tolerance (default: 5%) via `MATH_TOLERANCE_PERCENT`
- Required-field presence check (invoice number, vendor name, total amount)
- Date normalisation to ISO 8601 format (`YYYY-MM-DD`)

### Storage & Indexing

- **JSON**: one timestamped file per extraction in `outputs/extractions/`
- **SQLite**: relational database (`data/invoices.db`) with full-text and numeric search
- **ChromaDB**: vector embeddings (all-MiniLM-L6-v2) for semantic similarity search
- **BM25**: pickled keyword index (`rag/bm25_index.pkl`) for fast exact-term search

### Question Answering (RAG)

- Natural-language Q&A over all indexed invoices
- Automatic query routing to the best retrieval strategy (see [Section 6](#6-rag-system--query--retrieval))
- Final answers generated by the local Ollama LLM using retrieved context

### Interfaces

- **REST API** (FastAPI) at `http://localhost:8000` — file upload, batch, Q&A, indexing
- **Web UI** (Streamlit) at `http://localhost:8501` — drag-and-drop upload, Q&A chat
- **CLI agent** (`run_rag_agent.py`) — interactive terminal Q&A
- **Docker** — single-container deployment

---

## 4. System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         User Interfaces                             │
│   Streamlit UI (port 8501)   |   FastAPI REST (port 8000)   |  CLI  │
└──────────────┬──────────────────────────┬──────────────────────────┘
               │ upload file              │ POST /extract or /ask
               ▼                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Invoice Extraction Pipeline                       │
│                         (core/pipeline.py)                          │
│                                                                     │
│  Stage 1: detect_file_type()  →  digital | scanned | image          │
│  Stage 2: extract_text()      →  pdfplumber | PyMuPDF | OCR         │
│  Stage 3: extract_tables()    →  Camelot | Tabula | PPStructure      │
│  Stage 4: extract_with_llm()  →  Ollama (qwen2.5:3b)                │
│  Stage 5: merge_table_data()  →  fill missing line_items            │
│  Stage 6: validate_invoice()  →  math checks, field checks          │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ structured dict
                            ▼
        ┌───────────────────┬───────────────────┬──────────────────┐
        │   JSON file        │   SQLite DB        │  ChromaDB + BM25 │
        │  outputs/          │  data/invoices.db  │  Vector + Keyword│
        │  extractions/      │                    │  indexes         │
        └───────────────────┴───────────────────┴──────────────────┘
                                                          │
                                                 ┌────────▼─────────┐
                                                 │   RAG Pipeline    │
                                                 │  rag/router.py   │
                                                 │  rag/qa_chain.py │
                                                 │                   │
                                                 │  SQL → SQLite     │
                                                 │  BM25 → Keyword   │
                                                 │  Vector → Chroma  │
                                                 │  Hybrid → Both    │
                                                 └────────┬─────────┘
                                                          │ context
                                                          ▼
                                                   Ollama LLM
                                                 (answer generation)
```

---

## 5. Extraction Pipeline — Stage by Stage

The pipeline is implemented in `core/pipeline.py` as the `InvoicePipeline` class. Every stage is individually timed, logged, and wrapped in a `try/except` so that a failure in one stage does not abort the whole pipeline.

### Stage 1 — File Type Detection (`core/detector.py`)

Classifies the input as one of three types:

| Type | Description | How Detected |
|------|-------------|--------------|
| `digital` | PDF with embedded selectable text | `pdfplumber` extracts ≥ 50 chars of text per page |
| `scanned` | PDF containing raster images only | `pdfplumber` finds minimal text; pages contain image data |
| `image` | Standalone image file (JPG/PNG/TIFF) | File extension check |

### Stage 2 — Text Extraction

| File Type | Extractor | Module |
|-----------|-----------|--------|
| `digital` | `pdfplumber` (primary) → `PyMuPDF` (fallback) | `core/pdf_extractor.py` |
| `scanned` | Converts pages to images, then runs OCR | `core/ocr_engine.py` |
| `image` | Runs OCR directly on the image | `core/ocr_engine.py` |

**OCR chain** (scanned PDFs and images):
1. **PaddleOCR** (if installed) — highest accuracy
2. **Tesseract** — always-available fallback
3. Returns raw text + bounding-box layout information

### Stage 3 — Table Extraction (`core/table_extractor.py`)

Attempts to extract line-item tables using multiple engines in priority order:

| Priority | Engine | Suitable For |
|----------|--------|--------------|
| 1 | **Camelot** (lattice mode) | PDFs with visible grid lines |
| 2 | **Camelot** (stream mode) | PDFs with whitespace-aligned columns |
| 3 | **Tabula** | PDFs — alternative table parser |
| 4 | **PPStructure** (PaddleOCR) | Scanned / image — deep-learning table detection |
| 5 | **Regex fallback** | Any file — heuristic line-item pattern matching |

### Stage 4 — LLM Extraction (`core/llm_extractor.py`)

Sends the extracted text (and table data as context) to Ollama with a structured JSON prompt. The model is asked to fill in all invoice fields. If the model returns malformed JSON, the extractor retries up to 3 times with a corrective prompt.

**Model:** `qwen2.5:3b` (default, configurable via `LLM_MODEL`)

### Stage 5 — Table Merge

If the LLM returned zero line items but Stage 3 found tables, the pipeline merges the table rows into `line_items`, normalising column headers into the standard schema.

### Stage 6 — Validation & Post-Processing (`core/validator.py`)

- Normalises dates to ISO 8601
- Strips currency symbols from numeric fields
- Runs three levels of math checks (line item, subtotal, total)
- Produces a `validation` object attached to the result
- Logs `PASS` or `FAIL` with a list of specific warnings

---

## 6. RAG System — Query & Retrieval

### Query Router (`rag/router.py`)

Classifies each question using **pure regex/string matching** (no LLM call) and selects the most appropriate retrieval strategy:

| Strategy | When Selected | How It Works |
|----------|---------------|--------------|
| **SQL** | Question contains aggregation words (`total`, `count`, `average`, `highest`, `lowest`, `how many`, `top N`, etc.) or amount thresholds | Translates the question to SQL via Ollama, executes against SQLite, returns structured result |
| **BM25** | Question contains a specific invoice number (e.g. `GST-001`), GSTIN, quoted term, or all-caps vendor name | BM25Okapi keyword search over tokenised invoice text; returns ranked document list |
| **Vector** | Question contains semantic cues (`similar to`, `describe`, `explain`, `related to`, `what kind`, etc.) | Cosine similarity over ChromaDB embeddings; returns nearest-neighbour documents |
| **Hybrid** | Default — no clear signal detected | Runs both BM25 and vector search, merges and deduplicates results |

### Answer Generation (`rag/qa_chain.py`)

After retrieval, the top-N results are assembled into a context block and sent to Ollama for final answer generation. The response includes:
- `answer` — the generated natural-language answer
- `strategy` — which retrieval strategy was used
- `sources` — list of source invoice filenames
- `context` — the retrieved context snippets

### Indexing

| Store | Index File | Rebuild Command |
|-------|------------|-----------------|
| ChromaDB | `chroma_db/` directory | `POST /rag/index` or `python run_rag_agent.py` |
| BM25 | `rag/bm25_index.pkl` | `python run_bm25_index.py` |
| SQLite | `data/invoices.db` | `python run_db_ingest.py` |

Indexes are automatically rebuilt when a new invoice is processed via `POST /extract`.

---

## 7. API Reference

Base URL: `http://localhost:8000`

### `GET /health`

Health check endpoint.

**Response:**
```json
{ "status": "ok", "version": "2.0.0" }
```

---

### `POST /extract`

Upload and extract a single invoice file.

**Request:** `multipart/form-data` with field `file` (PDF, JPG, PNG, or TIFF).

**Response:** Full extraction JSON (see [Section 8](#8-data-schemas)).

**Side effects:** Saves JSON to `outputs/extractions/`, inserts into SQLite, updates ChromaDB and BM25 indexes.

**Example (curl):**
```bash
curl -X POST http://localhost:8000/extract \
  -F "file=@invoice.pdf"
```

---

### `POST /extract/batch`

Upload a ZIP file containing multiple invoices for batch processing.

**Request:** `multipart/form-data` with field `file` (a `.zip` archive).

**Response:** JSON array of extraction results, one per invoice file found in the ZIP.

**Example (curl):**
```bash
curl -X POST http://localhost:8000/extract/batch \
  -F "file=@invoices.zip"
```

---

### `POST /rag/index`

Rebuild ChromaDB and BM25 indexes from all JSON files currently in `outputs/extractions/`.

**Request body:** None required.

**Response:**
```json
{ "status": "indexed", "count": 12 }
```

---

### `POST /ask`

Ask a natural-language question about the indexed invoices.

**Request body:**
```json
{ "question": "What is the total amount of all invoices from ABC Supplies?" }
```

**Response:**
```json
{
  "answer": "The total amount across all invoices from ABC Supplies is ₹15,250.00.",
  "strategy": "sql",
  "sources": ["abc_inv_001_20260115_120000.json"],
  "context": "..."
}
```

---

## 8. Data Schemas

### Extraction Output JSON

Each processed invoice produces one JSON file in `outputs/extractions/`, named `{source_stem}_{YYYYMMDD_HHMMSS}.json`.

```json
{
  "invoice_number": "INV-2026-001",
  "invoice_date": "2026-01-15",
  "due_date": "2026-02-15",
  "purchase_order_number": "PO-12345",

  "vendor": {
    "name": "ABC Supplies Ltd.",
    "address": "123 Main Street, Mumbai",
    "email": "billing@abc.com",
    "phone": "+91-9876543210",
    "tax_id": "27AABCS1234A1Z5",
    "website": "https://abc.com"
  },

  "bill_to": {
    "name": "XYZ Corporation",
    "address": "456 Park Avenue, Delhi",
    "email": "accounts@xyz.com"
  },

  "ship_to": {
    "name": "XYZ Corporation Warehouse",
    "address": "789 Industrial Estate, Delhi"
  },

  "line_items": [
    {
      "line_number": 1,
      "description": "Widget Type A",
      "quantity": 10,
      "unit": "pcs",
      "unit_price": 100.00,
      "discount": null,
      "tax_rate": 18.0,
      "total": 1000.00
    }
  ],

  "subtotal": 1000.00,
  "discount": 0.00,
  "tax_rate": 18.0,
  "tax_amount": 180.00,
  "shipping": 50.00,
  "total_amount": 1230.00,
  "amount_paid": 0.00,
  "amount_due": 1230.00,
  "currency": "INR",
  "payment_terms": "Net 30",
  "payment_method": "Bank Transfer",
  "bank_details": {
    "account": "001234567890",
    "ifsc": "HDFC0001234",
    "name": "ABC Supplies Ltd.",
    "branch": "Mumbai Main"
  },
  "notes": "Please include invoice number on payment.",

  "validation": {
    "passed": true,
    "warnings": [],
    "math_checks": {
      "line_item_math": { "1": "ok" },
      "line_items_sum_to_subtotal": true,
      "totals_consistent": true
    },
    "line_item_count": 1
  },

  "metadata": {
    "source_file": "invoice.pdf",
    "source_path": "/path/to/invoice.pdf",
    "extraction_time": "2026-01-15T12:00:00",
    "processing_seconds": 4.72,
    "pdf_type": "digital",
    "page_count": 1,
    "ocr_engine": "none",
    "tables_found": 1,
    "text_length": 1842
  }
}
```

### SQLite Tables

**`invoices`** — One row per processed invoice. Contains all header and financial fields plus processing metadata. `source_file` is unique (prevents duplicate ingestion).

**`line_items`** — One row per line item. Foreign key `invoice_id` references `invoices.id`. Fields: `description`, `hsn_sac`, `quantity`, `unit_price`, `discount`, `tax_rate`, `tax_amount`, `total`.

**`validation_reports`** — One row per invoice. Fields: `passed` (BOOLEAN), `score` (REAL), `issues` (JSON string of warnings).

---

## 9. Technology Stack & Dependencies

### Core Runtime

| Technology | Version | Role |
|------------|---------|------|
| Python | 3.10 – 3.12 | Primary language (3.13+ not supported due to PaddleOCR) |
| FastAPI | ≥0.109 | REST API framework |
| Uvicorn | ≥0.27 | ASGI server for FastAPI |
| Streamlit | ≥1.30 | Web frontend |

### LLM & Inference

| Technology | Version | Role |
|------------|---------|------|
| Ollama | latest | Local LLM serving (must be installed separately) |
| qwen2.5:3b | — | Default extraction + Q&A model |
| Sentence-Transformers | ≥3.0 | Embedding generation (all-MiniLM-L6-v2) |

### OCR & Document Processing

| Technology | Version | Role |
|------------|---------|------|
| pdfplumber | ≥0.10 | Digital PDF text extraction |
| PyMuPDF (fitz) | ≥1.23 | PDF fallback + page rendering |
| pdf2image | ≥1.16 | PDF → image conversion for OCR |
| Tesseract OCR | system | Always-available OCR fallback (must be installed separately) |
| pytesseract | ≥0.3 | Python wrapper for Tesseract |
| PaddleOCR | ≥2.7 | High-accuracy OCR (optional, large install) |
| paddlepaddle | — | PaddleOCR backend (optional) |
| EasyOCR | ≥1.7 | Logo / vendor-name fallback |
| OpenCV | ≥4.8 | Image preprocessing |
| Pillow | ≥10.0 | Image loading |
| Camelot-py | ≥0.11 | PDF table extraction (lattice & stream) |
| tabula-py | ≥2.8 | PDF table extraction (alternative) |

### Storage & Search

| Technology | Version | Role |
|------------|---------|------|
| SQLAlchemy | ≥2.0 | ORM for SQLite |
| ChromaDB | ≥1.0 | Vector store (persistent) |
| rank-bm25 | ≥0.2.2 | BM25 keyword search |

### Infrastructure

| Technology | Role |
|------------|------|
| Docker | Containerised deployment |
| python-dotenv | `.env` file loading |

---

## 10. Configuration Reference

Copy `.env.example` to `.env` and set values as needed. All variables are also documented in `core/config.py`.

| Variable | Default | Description |
|----------|---------|-------------|
| `OCR_ENGINE` | `paddleocr` | Primary OCR engine: `paddleocr` or `tesseract` |
| `LLM_MODEL` | `qwen2.5:3b` | Ollama model name for extraction and Q&A |
| `LLM_BASE_URL` | `http://localhost:11434` | Ollama API endpoint |
| `API_HOST` | `0.0.0.0` | FastAPI listen address |
| `API_PORT` | `8000` | FastAPI listen port |
| `CHROMA_COLLECTION` | `invoices` | ChromaDB collection name |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence-Transformers model |
| `MATH_TOLERANCE_PERCENT` | `5` | Acceptable % difference in math checks |

---

## 11. How to Run

### Prerequisites

1. **Python 3.10 – 3.12** (3.13+ breaks PaddleOCR; Tesseract fallback still works)
2. **Tesseract OCR** installed and on `PATH`:
   - Ubuntu/Debian: `sudo apt install tesseract-ocr`
   - macOS: `brew install tesseract`
   - Windows: [UB-Mannheim installer](https://github.com/UB-Mannheim/tesseract/wiki)
3. **Ollama** installed and running:
   ```bash
   ollama serve          # start the server
   ollama pull qwen2.5:3b  # download the default model
   ```
4. **Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
5. (Optional) **PaddleOCR** for higher table accuracy:
   ```bash
   pip install paddlepaddle      # CPU backend
   pip install paddleocr>=2.7.0
   ```

### Quick Start

```bash
# From invoice-extraction-current/
python main.py
```

This single command:
1. Checks that Tesseract and Ollama are available
2. Initialises the SQLite database if it does not exist
3. Builds ChromaDB and BM25 indexes if they are empty
4. Launches the FastAPI server at `http://localhost:8000`
5. Launches the Streamlit frontend at `http://localhost:8501`

### CLI Options

```bash
python main.py                  # API + Streamlit frontend (default)
python main.py --api            # API server only (no frontend)
python main.py --batch          # Batch-process all invoices in data/input/, then launch frontend
python main.py --setup          # Initialise DB + indexes, then exit (no server launch)
```

### Individual Component Scripts

| Script | What It Does |
|--------|-------------|
| `run_api.py` | Start FastAPI server on port 8000 |
| `run_frontend.py` | Start Streamlit frontend on port 8501 |
| `run_batch_extract.py` | Process all files in `data/input/INVOICES/` |
| `run_db_ingest.py` | Load all JSON outputs into SQLite |
| `run_bm25_index.py` | Rebuild the BM25 keyword index |
| `run_rag_agent.py` | Interactive CLI Q&A agent |
| `run_regression_check.py` | Print regression summary table (reads existing outputs, no extraction) |
| `run_final_crosscheck.py` | Detailed validation and known-issues report |
| `run_key_regression.py` | Key-field regression check against ground truth |

### Docker

```bash
docker build -t invoice-extraction .

# Ollama must be accessible from inside the container
docker run -p 8000:8000 \
  -e LLM_BASE_URL=http://host.docker.internal:11434 \
  invoice-extraction
```

---

## 12. Testing & Validation Guide

The project does not yet have a `pytest` unit test suite. Testing is performed through the regression and validation scripts described below.

### End-to-End Extraction Test

1. Place one or more invoice files in `data/input/INVOICES/PDF/` (for PDFs) or `data/input/INVOICES/IMAGES/` (for images).
2. Run batch extraction:
   ```bash
   python run_batch_extract.py
   ```
3. Examine the JSON output in `outputs/extractions/`.
4. Run the regression summary:
   ```bash
   python run_regression_check.py
   ```
   This prints a table with vendor name, customer name, subtotal, tax, total, math-match status, item count, and validation result for every processed invoice.

### Regression Check Scripts

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `run_regression_check.py` | Summary table of all latest outputs. Checks 6 known issues. | After any extraction-pipeline change |
| `run_final_crosscheck.py` | Detailed per-invoice validation report | Before a release or after bulk processing |
| `run_key_regression.py` | Compares key fields against `data/ground_truth.json` | When adding ground truth entries |

### RAG Router Self-Test

The router module includes 8 built-in test cases covering all four strategies. Run them with:

```bash
cd invoice-extraction-current
python -m rag.router
```

Expected output: all 8 test cases printed with their classified strategy.

### API Smoke Tests

With the server running (`python main.py --api`):

```bash
# Health check
curl http://localhost:8000/health

# Single file extraction
curl -X POST http://localhost:8000/extract \
  -F "file=@data/input/INVOICES/PDF/sample.pdf"

# Ask a question (requires at least one indexed invoice)
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "List all vendor names in the database"}'
```

### Ground Truth Evaluation

`data/ground_truth.json` maps filenames to expected field values. Currently contains 2 sample entries. To evaluate extractions against this file:

```bash
python run_key_regression.py
```

To improve coverage, add entries to `data/ground_truth.json` using this format:
```json
{
  "filename": "your_invoice.pdf",
  "fields": {
    "invoice_number": "INV-2026-001",
    "invoice_date": "2026-01-15",
    "vendor_name": "Vendor Name Here",
    "customer_name": "Customer Name Here",
    "total_amount": "1250.00",
    "payment_due_date": "2026-02-15"
  }
}
```

### Math Validation Interpretation

The `validation` block in each output JSON shows the result of three checks:

| Check | Passes When |
|-------|-------------|
| `line_item_math` | `quantity × unit_price` is within tolerance of `line_total` for each item |
| `line_items_sum_to_subtotal` | `sum(line_item totals)` is within tolerance of `subtotal` |
| `totals_consistent` | `subtotal + tax_amount + shipping − discount` is within tolerance of `total_amount` |

Tolerance is configurable via `MATH_TOLERANCE_PERCENT` (default 5%). A `PASS` result with zero warnings indicates a fully consistent extraction.

---

## 13. Known Limitations & Open Issues

### Tracked Issues (from regression script)

| # | Issue | Status |
|---|-------|--------|
| 1 | `vendor_name` missing in `invis1.jpg` | Under investigation |
| 2 | `bill_to.name` missing in `invoice.png` | Under investigation |
| 3 | Line-item math error in `invis1.jpg` | Under investigation |
| 4 | Total mismatch in `GST003` | Under investigation |
| 5 | Total mismatch in `invoice.png` | Under investigation |
| 6 | PaddleOCR not auto-installed | Documented — manual install required |

### Structural Limitations

| Limitation | Impact | Workaround |
|------------|--------|-----------|
| PaddleOCR requires Python ≤3.12 | Cannot use PPStructure table extraction on Python 3.13+ | Use Tesseract + regex fallback |
| PaddleOCR is ~2 GB | Large install size for CI environments | Install only when higher OCR accuracy is needed |
| Sequential batch processing | Slow for large invoice sets | Process smaller batches; parallelisation is a roadmap item |
| No API authentication | API is open to any network client | Restrict with firewall or reverse proxy in production |
| Minimal ground truth | `run_key_regression.py` covers only 2 invoices | Add more entries to `data/ground_truth.json` |
| No formal unit tests | Bugs may go undetected | Use regression scripts after each change |
| LLM output is non-deterministic | Same invoice may produce slightly different fields across runs | Use higher-quality models (`qwen2.5:7b`, `llama3.1`) for better consistency |
| Context window limit | Very long invoices may be truncated before the LLM | Chunking strategies could be improved |

---

## 14. Improvement Roadmap

The following items represent the most impactful improvements, roughly ordered by priority:

### Testing & Quality

- [ ] **Add pytest suite** — unit tests for each `core/` module (`detector`, `validator`, `llm_extractor`, etc.) and integration tests for the full pipeline
- [ ] **Expand ground truth** — add real-world invoice samples to `data/ground_truth.json` to make `run_key_regression.py` statistically meaningful
- [ ] **CI/CD pipeline** — GitHub Actions workflow to run tests on every pull request
- [ ] **Accuracy benchmarking** — measure field-level extraction accuracy against a labelled test set; track changes over time

### Performance

- [ ] **Async / parallel batch processing** — use `asyncio` or `concurrent.futures` to process multiple invoices simultaneously
- [ ] **Streaming API responses** — return partial results as extraction stages complete
- [ ] **Smarter chunking** — improve ChromaDB chunking to handle very long invoices without truncation

### Robustness

- [ ] **Retry logic for network calls** — more robust Ollama connection handling (reconnect, timeout config)
- [ ] **Better table extraction fallback chain** — investigate deep-learning-based table detection alternatives to PPStructure
- [ ] **Improved vendor name detection** — extend logo/name fallback for invoices with no text vendor block
- [ ] **Multi-language OCR** — support for non-English invoices

### Features

- [ ] **CSV / XLSX export** — allow downloading extracted data in spreadsheet format
- [ ] **Webhook / callback support** — notify external systems when extraction completes
- [ ] **API authentication** — JWT or API key middleware for production deployments
- [ ] **Invoice duplicate detection** — warn when the same invoice number is uploaded twice
- [ ] **Dashboard** — Streamlit analytics page showing extraction statistics over time

### Developer Experience

- [ ] **Pre-commit hooks** — `ruff` / `black` linting and formatting on commit
- [ ] **Structured logging** — write JSON log lines to disk (currently console-only)
- [ ] **Environment validation script** — single command to verify all prerequisites are satisfied
- [ ] **Contribution guide** — `CONTRIBUTING.md` with branching model, review process, and code style guide

---

## 15. Project Structure Reference

```
invoice-extraction-current/
│
├── main.py                     # Unified launcher (API + frontend + setup)
├── requirements.txt            # Python package dependencies
├── Dockerfile                  # Container build (Python 3.10-slim)
├── .env.example                # Environment variable template
├── README.md                   # Quick-start guide
├── PROJECT_OVERVIEW.md         # This document
│
├── core/                       # Extraction pipeline modules
│   ├── pipeline.py             # Master orchestrator (6-stage flow)
│   ├── detector.py             # File type classification
│   ├── pdf_extractor.py        # Digital PDF text extraction
│   ├── ocr_engine.py           # OCR wrapper (PaddleOCR / Tesseract)
│   ├── table_extractor.py      # Table extraction (Camelot / Tabula / PPStructure)
│   ├── llm_extractor.py        # Ollama LLM field extraction
│   ├── logo_extractor.py       # EasyOCR vendor-name fallback
│   ├── validator.py            # Math checks & date normalisation
│   ├── db.py                   # SQLAlchemy ORM models & session
│   └── config.py               # Environment variable loading
│
├── rag/                        # Retrieval-Augmented Generation
│   ├── router.py               # Query classifier (regex-based)
│   ├── qa_chain.py             # Multi-strategy retrieval + answer gen
│   ├── chunker.py              # Document chunking for embeddings
│   ├── indexer.py              # ChromaDB indexing
│   ├── bm25_retriever.py       # BM25Okapi keyword search
│   ├── sql_retriever.py        # SQL generation & execution via Ollama
│   ├── agent.py                # CLI RAG agent
│   └── bm25_index.pkl          # Pickled BM25 index (auto-generated)
│
├── api/
│   └── main.py                 # FastAPI app with all endpoints
│
├── frontend/
│   └── app.py                  # Streamlit web UI (Extract + Ask tabs)
│
├── schemas/
│   └── invoice_schema.py       # Pydantic models for API validation
│
├── data/
│   ├── ground_truth.json       # Expected field values for test invoices
│   ├── invoices.db             # SQLite database (auto-generated)
│   ├── input/
│   │   └── INVOICES/
│   │       ├── PDF/            # Place PDF invoices here for batch processing
│   │       └── IMAGES/         # Place image invoices here for batch processing
│   └── README.md
│
├── outputs/
│   ├── extractions/            # Per-invoice JSON output files
│   └── README.md               # Output schema documentation
│
├── chroma_db/                  # ChromaDB persistent vector store (auto-generated)
│
├── run_api.py                  # Start API server only
├── run_frontend.py             # Start Streamlit only
├── run_batch_extract.py        # Batch process all invoices in data/input/
├── run_db_ingest.py            # Populate SQLite from JSON outputs
├── run_bm25_index.py           # Rebuild BM25 keyword index
├── run_rag_agent.py            # CLI interactive Q&A agent
├── run_regression_check.py     # Regression summary (no extraction)
├── run_final_crosscheck.py     # Detailed validation report
└── run_key_regression.py       # Key-field regression vs ground truth
```

---

*Last updated: 2026-03-18*
