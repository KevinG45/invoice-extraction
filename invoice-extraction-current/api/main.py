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

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from core.config import (
    BM25_INDEX_PATH,
    OUTPUTS_DIR,
    SUPPORTED_EXTENSIONS,
    TEMP_DIR,
)

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _process_single_file(tmp_path: str, filename: str) -> dict:
    """Run the full extraction pipeline on one file, persist everywhere."""
    pipeline = _get_pipeline()
    result = pipeline.run(tmp_path)

    # Replace temp path with the original filename
    if "metadata" in result:
        result["metadata"]["source_file"] = filename

    # Save JSON to outputs/extractions/
    pipeline.save_result(result)

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

    # Index into ChromaDB
    try:
        from rag.chunker import chunk_invoice
        from rag.indexer import index_chunks
        chunks = chunk_invoice(result, filename=filename)
        index_chunks(chunks)
        logger.info("[api] ChromaDB index OK: %s (%d chunks)", filename, len(chunks))
    except Exception as e:
        logger.warning("[api] ChromaDB index failed for %s: %s", filename, e)

    # Rebuild BM25 index
    try:
        from rag.bm25_retriever import BM25Retriever
        bm25 = BM25Retriever(index_path=str(BM25_INDEX_PATH))
        bm25.build_index(str(OUTPUTS_DIR))
        logger.info("[api] BM25 rebuild OK")
    except Exception as e:
        logger.warning("[api] BM25 rebuild failed: %s", e)

    return result


# ═══════════════════════════════════════════════════════════════════════════
#  POST /extract
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/extract")
async def extract_invoice(file: UploadFile = File(...)):
    """Upload a single invoice (PDF / image) and receive extracted fields."""
    filename = file.filename or "unknown"
    ext = Path(filename).suffix.lower()

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
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
        )
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ═══════════════════════════════════════════════════════════════════════════
#  POST /extract/batch
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/extract/batch")
async def extract_batch(file: UploadFile = File(...)):
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
        with zipfile.ZipFile(tmp_zip, "r") as zf:
            zf.extractall(extract_dir)

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
        return JSONResponse(status_code=500, content={"error": str(e)})
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
        return JSONResponse(status_code=500, content={"error": str(e)})


# ═══════════════════════════════════════════════════════════════════════════
#  POST /ask
# ═══════════════════════════════════════════════════════════════════════════

class AskRequest(BaseModel):
    question: str


@app.post("/ask")
async def ask_question(request: AskRequest):
    """Ask a natural-language question about indexed invoices."""
    if not request.question.strip():
        raise HTTPException(
            status_code=400,
            detail={"error": "EMPTY_QUESTION", "message": "Question cannot be empty"},
        )
    try:
        from rag.qa_chain import answer
        result = answer(request.question)
        return result
    except Exception as e:
        logger.error("[api] Q&A failed: %s", e, exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})


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
