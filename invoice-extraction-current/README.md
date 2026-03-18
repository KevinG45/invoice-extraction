# Invoice Extraction + RAG System

Automated invoice data extraction using OCR and LLMs, with a multi-strategy RAG pipeline for querying extracted data.

**Stack**: PaddleOCR + Tesseract | pdfplumber + PyMuPDF | Ollama (local LLM) | ChromaDB + BM25 | FastAPI + Streamlit

## Setup

### Prerequisites

- Python 3.10+
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) installed and on PATH
- [Ollama](https://ollama.com) installed and running

### Installation

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install and start Ollama, then pull the model
ollama serve
ollama pull qwen2.5:3b
```

Tesseract install (if not already present):

- **Ubuntu/Debian**: `sudo apt install tesseract-ocr`
- **macOS**: `brew install tesseract`
- **Windows**: download installer from [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki) and add to PATH

### Environment Variables

Copy `.env.example` to `.env` and fill in values as needed. See `core/config.py` for all supported variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `OCR_ENGINE` | `paddleocr` | Primary OCR engine (`paddleocr` or `tesseract`) |
| `LLM_MODEL` | `qwen2.5:3b` | Ollama model name |
| `LLM_BASE_URL` | `http://localhost:11434` | Ollama endpoint |
| `API_HOST` | `0.0.0.0` | API listen address |
| `API_PORT` | `8000` | API listen port |
| `CHROMA_COLLECTION` | `invoices` | ChromaDB collection name |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformer model |

## Running

### Quick Start (One Command)

```bash
python main.py
```

This single command will:
1. ✅ Check prerequisites (Tesseract, Ollama)
2. 📊 Initialize database if needed
3. 📇 Build indexes if needed
4. 🚀 Launch the Streamlit frontend at `http://localhost:8501`

**Upload an invoice via the frontend to see extraction in action!**

### Other Options

```bash
python main.py --api        # Launch API server instead (http://localhost:8000)
python main.py --batch      # Process all invoices in data/input/ first
python main.py --setup      # Setup only (no launch)
```

### Individual Components (Advanced)

If you need to run components separately:

| Script | Purpose |
|--------|---------|
| `run_api.py` | Launch FastAPI server on port 8000 |
| `run_frontend.py` | Launch Streamlit frontend on port 8501 |
| `run_batch_extract.py` | Batch process all invoices in `data/input/` |
| `run_db_ingest.py` | Ingest all JSON outputs into SQLite |
| `run_bm25_index.py` | Rebuild the BM25 keyword index |
| `run_rag_agent.py` | CLI RAG agent (index + ask) |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check. Returns `{"status": "ok", "version": "2.0.0"}` |
| `POST` | `/extract` | Upload a single PDF or image. Runs the full 6-stage pipeline, saves JSON, inserts into SQLite, indexes into ChromaDB, rebuilds BM25. Returns the extraction result. |
| `POST` | `/extract/batch` | Upload a `.zip` of invoices. Processes each file and returns an array of results. |
| `POST` | `/rag/index` | Rebuild ChromaDB and BM25 indexes from all JSON files in `outputs/extractions/`. |
| `POST` | `/ask` | Send `{"question": "..."}`. Routes through the multi-strategy RAG pipeline and returns an answer with strategy, sources, and context. |

## RAG Strategies

The query router (`rag/router.py`) classifies each question and selects one of four retrieval strategies:

| Strategy | Trigger | How It Works |
|----------|---------|--------------|
| **SQL** | Aggregation words like "how many", "total", "average", "highest" | Translates the question to SQL via Ollama, executes against SQLite |
| **BM25** | Specific invoice numbers, GSTINs, quoted terms, vendor names | Keyword search using BM25Okapi over tokenised invoice text |
| **Vector** | Semantic words like "similar to", "describe", "explain", "related" | Cosine similarity search over ChromaDB embeddings (all-MiniLM-L6-v2) |
| **Hybrid** | Default fallback when no clear signal is detected | Runs both BM25 and vector search, merges and deduplicates results |

After retrieval, the context is sent to Ollama for final answer generation.

## Project Structure

```
api/            FastAPI application and endpoints
core/           Extraction pipeline (OCR, PDF, LLM, validation)
frontend/       Streamlit web interface
rag/            RAG pipeline (indexing, retrieval, QA)
schemas/        Pydantic data models
data/           Input invoices and SQLite database
outputs/        JSON extraction results (see outputs/README.md)
chroma_db/      ChromaDB persistent vector store
```

## Docker

```bash
docker build -t invoice-extraction .
docker run -p 8000:8000 invoice-extraction
```

Requires Ollama accessible from inside the container (set `LLM_BASE_URL` to host address).
