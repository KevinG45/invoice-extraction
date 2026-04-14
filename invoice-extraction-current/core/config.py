"""
Configuration for the Invoice Extraction System.

All runtime constants are loaded from environment variables (via .env)
or use sensible defaults. No hardcoded file paths.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent  # invoice-extraction-current/
DATA_DIR = BASE_DIR / "data" / "input" / "INVOICES"
OUTPUTS_DIR = BASE_DIR / "outputs" / "extractions"
TEMP_DIR = BASE_DIR / "temp"
CHROMA_DIR = BASE_DIR / "chroma_db"
DATABASE_PATH = BASE_DIR / "data" / "invoices.db"
LOGS_DIR = BASE_DIR / "logs"
BM25_INDEX_PATH = BASE_DIR / "rag" / "bm25_index.pkl"

# Ensure directories exist
for d in [OUTPUTS_DIR, TEMP_DIR, CHROMA_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── API Security Configuration ────────────────────────────────────────────
# FIXED: Security - File upload limits and CORS configuration
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))  # 50MB default
MAX_ZIP_EXTRACT_SIZE_MB = int(os.getenv("MAX_ZIP_EXTRACT_SIZE_MB", "500"))  # 500MB max extraction
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8501").split(",")

# ── OCR Settings ───────────────────────────────────────────────────────────
OCR_ENGINE = os.getenv("OCR_ENGINE", "paddleocr")          # "paddleocr" | "tesseract"
USE_GPU = os.getenv("USE_GPU", "false").lower() == "true"
OCR_LANG = os.getenv("OCR_LANG", "en")
IMAGE_DPI = int(os.getenv("IMAGE_DPI", "300"))

# ── LLM Settings (Ollama) ─────────────────────────────────────────────────
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:3b")   # Ollama model name; set LLM_MODEL=llama3 in .env for higher accuracy
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "120"))  # seconds; qwen2.5:3b ~40-80s; llama3 ~85-150s on CPU

# ── Extraction Thresholds ─────────────────────────────────────────────────
MIN_TEXT_CHARS = int(os.getenv("MIN_TEXT_CHARS", "50"))       # Digital vs scanned threshold
TABLE_CONFIDENCE_THRESHOLD = float(os.getenv("TABLE_CONFIDENCE_THRESHOLD", "0.8"))
FIELD_CONFIDENCE_THRESHOLD = float(os.getenv("FIELD_CONFIDENCE_THRESHOLD", "0.5"))

# ── Table Extraction (Camelot) ────────────────────────────────────────────
CAMELOT_FLAVOR_BORDERED = "lattice"      # For bordered/ruled tables
CAMELOT_FLAVOR_BORDERLESS = "stream"     # For borderless tables

# ── RAG Settings ───────────────────────────────────────────────────────────
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "invoices")
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "10"))  # Increased from 5 for better coverage
RAG_TOP_K_LIST = int(os.getenv("RAG_TOP_K_LIST", "20"))  # For "show all", "list" queries

# ── API Settings ───────────────────────────────────────────────────────────
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

# ── Validation Tolerances ─────────────────────────────────────────────────
MATH_TOLERANCE_PERCENT = float(os.getenv("MATH_TOLERANCE_PERCENT", "5.0"))  # 5% tolerance
MATH_TOLERANCE = MATH_TOLERANCE_PERCENT / 100.0  # Fractional form (0.05)

# ── Supported File Types ──────────────────────────────────────────────────
SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"}
