"""
FastAPI Backend for Invoice Extraction + RAG Q&A System.

Endpoints:
    POST /extract          — Upload & extract single invoice
    POST /extract/batch    — Upload a .zip and extract every invoice inside
    POST /rag/index        — Rebuild ChromaDB + BM25 indexes
    POST /ask              — Ask natural-language questions about invoices
    GET  /health           — Health check
"""

import json
import logging
import os
import shutil
import tempfile
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# FIXED: Bug #23 — Rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from core.config import (
    BM25_INDEX_PATH,
    OUTPUTS_DIR,
    SUPPORTED_EXTENSIONS,
    TEMP_DIR,
    MAX_UPLOAD_SIZE_MB,
    MAX_ZIP_EXTRACT_SIZE_MB,
    ALLOWED_ORIGINS,
)

# FIXED: Bug P0-1 — Initialize limiter instance
limiter = Limiter(key_func=get_remote_address)


# ── Error Response Standardization ────────────────────────────────────────

def _standardized_error(error_code: str, message: str, status_code: int = 500) -> JSONResponse:
    """
    FIXED: Security - Return standardized error responses without exposing internals.
    """
    return JSONResponse(
        status_code=status_code,
        content={
            "error_code": error_code,
            "message": message,
            "status_code": status_code,
        }
    )

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


# ── Helper Functions ───────────────────────────────────────────────────────

def _safe_extract_zip(zip_path: str, extract_dir: str) -> None:
    """
    Safely extract ZIP with bomb detection and path traversal prevention.
    
    FIXED: Security - Prevent ZIP bombs and path traversal attacks.
    """
    with zipfile.ZipFile(zip_path, 'r') as zf:
        total_size = 0
        for member in zf.infolist():
            # Prevent path traversal
            if '..' in member.filename or member.filename.startswith('/'):
                raise ValueError(f"Unsafe path in ZIP: {member.filename}")
            
            # Prevent symbolic links
            if member.is_symlink():
                raise ValueError(f"Symbolic links not allowed: {member.filename}")
            
            # Check uncompressed size (ZIP bomb detection)
            total_size += member.file_size
            if total_size > MAX_ZIP_EXTRACT_SIZE_MB * 1024 * 1024:
                raise ValueError(
                    f"ZIP bomb detected: uncompressed size {total_size / 1024 / 1024:.1f}MB "
                    f"exceeds {MAX_ZIP_EXTRACT_SIZE_MB}MB limit"
                )
        
        # Safe to extract
        zf.extractall(extract_dir)
        logger.info("[api] Extracted ZIP: %d files, %.1f MB", len(zf.infolist()), total_size / 1024 / 1024)


# ── Lazy singletons ───────────────────────────────────────────────────────
_pipeline = None


def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        from core.pipeline import InvoicePipeline
        _pipeline = InvoicePipeline()
    return _pipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Invoice Extraction API starting up...")
    yield
    logger.info("Invoice Extraction API shutting down...")


# ── App ────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Invoice Extraction & RAG API",
    description=(
        "Local invoice extraction pipeline using PaddleOCR + Ollama LLM. "
        "Includes RAG-powered Q&A over indexed invoices via ChromaDB."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# FIXED: Bug #23 — Add rate limiter to app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # FIXED: Security - Restrict origins from config
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _process_single_file(tmp_path: str, filename: str) -> dict:
    """
    Run the full extraction pipeline on one file, persist everywhere.
    FIXED: Bug P0-7 — Enhanced error handling with specific error types.
    """
    # Validate file exists and is readable
    if not os.path.exists(tmp_path):
        raise FileNotFoundError(f"Temporary file not found: {tmp_path}")
    
    if os.path.getsize(tmp_path) == 0:
        raise ValueError("File is empty")
    
    try:
        pipeline = _get_pipeline()
        result = pipeline.run(tmp_path)
    except Exception as e:
        logger.error(f"[api] Pipeline failed for {filename}: {e}", exc_info=True)
        raise RuntimeError(f"Extraction pipeline failed: {str(e)[:100]}")

    # Document type guard — pipeline rejected this file as non-invoice
    if result.get("error") == "unsupported_document_type":
        return _standardized_error(
            error_code="UNSUPPORTED_DOCUMENT_TYPE",
            message=result.get("message", "This file does not appear to be an invoice."),
            status_code=422,
        )

    # Replace temp path with the original filename
    if "metadata" in result:
        result["metadata"]["source_file"] = filename

    # Save JSON to outputs/extractions/
    try:
        pipeline.save_result(result)
    except Exception as e:
        logger.warning("[api] JSON save failed for %s: %s", filename, e)
        # Non-fatal: continue

    # Insert into SQLite
    try:
        from core.db import insert_extraction, source_file_exists
        if not source_file_exists(filename):
            insert_extraction(result)
            logger.info("[api] DB insert OK: %s", filename)
        else:
            logger.info("[api] DB skip (already exists): %s", filename)
    except Exception as e:
        logger.warning("[api] DB insert failed for %s: %s", filename, e)
        # Non-fatal: continue

    # Index into ChromaDB
    try:
        from rag.chunker import chunk_invoice
        from rag.indexer import index_chunks
        chunks = chunk_invoice(result, filename=filename)
        index_chunks(chunks)
        logger.info("[api] ChromaDB index OK: %s (%d chunks)", filename, len(chunks))
    except Exception as e:
        logger.warning("[api] ChromaDB index failed for %s: %s", filename, e)
        # Non-fatal: continue

    # Incrementally update BM25 index (load existing + add one doc; avoids O(n) re-read)
    try:
        from rag.bm25_retriever import BM25Retriever
        bm25 = BM25Retriever(index_path=str(BM25_INDEX_PATH))
        if BM25_INDEX_PATH.exists():
            bm25.load_index()
        else:
            bm25.build_index(str(OUTPUTS_DIR))  # first run: build from scratch
        bm25.add_document(result, filename)
        logger.info("[api] BM25 incremental update OK")
    except Exception as e:
        logger.warning("[api] BM25 update failed: %s", e)
        # Non-fatal: continue

    return result


# ═══════════════════════════════════════════════════════════════════════════
#  POST /extract
# ═══════════════════════════════════════════════════════════════════════════

# FIXED: Bug #23 — Rate limiting (10 requests per minute)
@app.post("/extract")
@limiter.limit("10/minute")
async def extract_invoice(file: UploadFile = File(...), request: Request = None):
    """Upload a single invoice (PDF / image) and receive extracted fields."""
    filename = file.filename or "unknown"
    
    # FIXED: Bug P1-10 — Sanitize filename to prevent path traversal
    # Remove any path components, only keep the base filename
    filename = Path(filename).name  # Removes any directory path
    if '..' in filename or filename.startswith('/') or filename.startswith('\\'):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "INVALID_FILENAME",
                "message": "Filename contains invalid characters",
            },
        )
    
    ext = Path(filename).suffix.lower()

    # FIXED: Security - File size validation
    if file.size and file.size > MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail={
                "error": "FILE_TOO_LARGE",
                "message": f"File size exceeds {MAX_UPLOAD_SIZE_MB}MB limit",
            },
        )

    # FIXED: Security - Empty file validation
    if file.size == 0:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "EMPTY_FILE",
                "message": "Uploaded file is empty",
            },
        )

    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "UNSUPPORTED_FILE_TYPE",
                "message": f"File type '{ext}' is not supported.",
                "supported": sorted(SUPPORTED_EXTENSIONS),
            },
        )

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        logger.info("[api] Processing: %s", filename)
        result = _process_single_file(tmp_path, filename)
        return JSONResponse(content={"status": "success", "data": result})

    except Exception as e:
        logger.error("[api] Extraction failed for %s: %s", filename, e, exc_info=True)
        # FIXED: Security - Don't expose internal errors to clients
        return _standardized_error(
            error_code="EXTRACTION_FAILED",
            message="Failed to extract invoice. Please check the file format and try again.",
            status_code=500
        )
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ═══════════════════════════════════════════════════════════════════════════
#  POST /extract/batch
# ═══════════════════════════════════════════════════════════════════════════

# FIXED: Bug #23 — Rate limiting (5 batch uploads per minute)
@app.post("/extract/batch")
@limiter.limit("5/minute")
async def extract_batch(request: Request, file: UploadFile = File(...)):
    """Upload a .zip archive of invoices and extract each one."""
    filename = file.filename or "upload.zip"
    if not filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip files are accepted.")

    tmp_zip = None
    extract_dir = None
    try:
        # Save uploaded zip
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_zip = tmp.name

        # Extract zip to a temp directory
        extract_dir = tempfile.mkdtemp(dir=str(TEMP_DIR))
        
        # FIXED: Security - Safe ZIP extraction with bomb detection
        try:
            _safe_extract_zip(tmp_zip, extract_dir)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except zipfile.BadZipFile:
            raise HTTPException(status_code=400, detail="Invalid or corrupted ZIP file")

        # Find all supported files inside the extracted directory
        invoice_files = []
        for root, _dirs, files in os.walk(extract_dir):
            for f in files:
                if Path(f).suffix.lower() in SUPPORTED_EXTENSIONS:
                    invoice_files.append(os.path.join(root, f))

        if not invoice_files:
            raise HTTPException(
                status_code=400,
                detail="No supported invoice files found inside the zip.",
            )

        results = []
        for fpath in sorted(invoice_files):
            fname = Path(fpath).name
            try:
                result = _process_single_file(fpath, fname)
                results.append({"status": "success", "filename": fname, "data": result})
            except Exception as e:
                logger.error("[api] Batch file failed %s: %s", fname, e)
                results.append({"status": "error", "filename": fname, "error": str(e)})

        return JSONResponse(content=results)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("[api] Batch extraction failed: %s", e, exc_info=True)
        # FIXED: Security - Don't expose internal errors
        return _standardized_error(
            error_code="BATCH_EXTRACTION_FAILED",
            message="Batch extraction failed. Please check the ZIP file and try again.",
            status_code=500
        )
    finally:
        if tmp_zip and os.path.exists(tmp_zip):
            os.unlink(tmp_zip)
        if extract_dir and os.path.exists(extract_dir):
            shutil.rmtree(extract_dir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════════
#  POST /rag/index
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/rag/index")
async def rag_index():
    """Rebuild both ChromaDB and BM25 indexes from outputs/extractions/."""
    try:
        # ChromaDB index_all
        from rag.indexer import index_all
        chroma_stats = index_all()
        
        # FIXED: Bug API-1 — Handle None return from index_all
        if chroma_stats is None:
            chroma_stats = {}

        # BM25 build_index
        from rag.bm25_retriever import BM25Retriever
        bm25 = BM25Retriever(index_path=str(BM25_INDEX_PATH))
        bm25_count = bm25.build_index(str(OUTPUTS_DIR))

        total_indexed = chroma_stats.get("indexed", 0) + chroma_stats.get("skipped", 0)
        return {
            "indexed": total_indexed,
            "status": "ok",
            "chroma": chroma_stats,
            "bm25_documents": bm25_count,
        }
    except Exception as e:
        logger.error("[api] Index rebuild failed: %s", e, exc_info=True)
        # FIXED: Security - Don't expose internal errors
        return _standardized_error(
            error_code="INDEX_REBUILD_FAILED",
            message="Failed to rebuild search indexes. Please try again later.",
            status_code=500
        )


# ═══════════════════════════════════════════════════════════════════════════
#  POST /ask
# ═══════════════════════════════════════════════════════════════════════════

class AskRequest(BaseModel):
    question: str


# FIXED: Bug #23 — Rate limiting (10 questions per minute)
@app.post("/ask")
@limiter.limit("10/minute")
async def ask_question(ask_req: AskRequest, request: Request):
    """Ask a natural-language question about indexed invoices.

    Uses multi-strategy RAG with conversation memory:
    - SQL for aggregation queries
    - BM25 for keyword/exact lookup
    - Vector (with HyDE) for semantic/vague questions
    - Hybrid (RRF fusion) for general questions

    Results are re-ranked before being sent to the LLM.
    """
    if not ask_req.question.strip():
        raise HTTPException(
            status_code=400,
            detail={"error": "EMPTY_QUESTION", "message": "Question cannot be empty"},
        )
    try:
        from rag.qa_chain import answer
        result = answer(ask_req.question)
        return result
    except Exception as e:
        logger.error("[api] Q&A failed: %s", e, exc_info=True)
        # FIXED: Security - Don't expose internal errors
        return _standardized_error(
            error_code="QA_FAILED",
            message="Failed to process your question. Please try rephrasing or contact support.",
            status_code=500
        )


# ═══════════════════════════════════════════════════════════════════════════
#  POST /ask/clear — Clear conversation memory
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/ask/clear")
async def clear_conversation():
    """Clear the conversation memory so follow-up context resets."""
    try:
        from rag.qa_chain import get_memory
        get_memory().clear()
        return {"status": "ok", "message": "Conversation memory cleared."}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ═══════════════════════════════════════════════════════════════════════════
#  POST /rag/evaluate — Run RAG evaluation suite
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/rag/evaluate")
async def rag_evaluate():
    """Run the evaluation test suite and return metrics."""
    try:
        from rag.evaluator import run_evaluation
        report = run_evaluation(verbose=False)
        return report
    except Exception as e:
        logger.error("[api] Evaluation failed: %s", e, exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})


# ═══════════════════════════════════════════════════════════════════════════
#  GET /rag/stats — Get RAG index statistics
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/rag/stats")
async def rag_stats():
    """Return statistics about the current RAG indexes."""
    stats = {}
    try:
        from rag.indexer import get_collection_stats
        stats["chroma"] = get_collection_stats()
    except Exception as e:
        stats["chroma"] = {"error": str(e)}

    try:
        from rag.bm25_retriever import BM25Retriever
        bm25 = BM25Retriever(index_path=str(BM25_INDEX_PATH))
        bm25.load_index()
        stats["bm25"] = {"documents": len(bm25.corpus)}
    except Exception as e:
        stats["bm25"] = {"error": str(e)}

    return stats


# ═══════════════════════════════════════════════════════════════════════════
#  GET /health
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/health")
async def health_check():
    """Quick health check."""
    return {"status": "ok", "version": "2.0.0"}


# ═══════════════════════════════════════════════════════════════════════════
#  Direct run
# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import uvicorn
    from core.config import API_HOST, API_PORT

    uvicorn.run(
        "api.main:app",
        host=API_HOST,
        port=API_PORT,
        reload=True,
    )
