#!/usr/bin/env python3
"""
Invoice Extraction System - Unified Entry Point

Run this file to:
1. Check prerequisites (Ollama, Tesseract)
2. Initialize database and indexes if needed
3. Launch API server in background
4. Launch Streamlit frontend

Usage:
    python main.py              # Launch frontend + API (default)
    python main.py --api        # Launch API server only
    python main.py --setup      # Run setup only (no launch)
    python main.py --batch      # Process all invoices + launch frontend
"""

import logging
import os
import subprocess
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def check_prerequisites():
    """Check if Ollama and Tesseract are installed."""
    logger.info("🔍 Checking prerequisites...")

    # Check Tesseract
    try:
        result = subprocess.run(
            ["tesseract", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            logger.info("✅ Tesseract OCR found")
        else:
            logger.warning("⚠️  Tesseract not found. OCR may fail.")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        logger.warning("⚠️  Tesseract not found. Install: https://github.com/tesseract-ocr/tesseract")

    # Check Ollama
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            if "qwen2.5:3b" in result.stdout:
                logger.info("✅ Ollama found with qwen2.5:3b model")
            else:
                logger.warning("⚠️  Ollama found but qwen2.5:3b not installed. Run: ollama pull qwen2.5:3b")
        else:
            logger.warning("⚠️  Ollama not responding")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        logger.warning("⚠️  Ollama not found. Install: https://ollama.com")

    logger.info("")


def setup_database():
    """Initialize SQLite database if it doesn't exist."""
    from core.db import init_db
    from core.config import DATABASE_PATH

    db_path = Path(DATABASE_PATH)
    if not db_path.exists():
        logger.info("📊 Creating database...")
        init_db()
        logger.info("✅ Database created")
    else:
        logger.info("✅ Database exists")


def setup_indexes():
    """Build BM25 and ChromaDB indexes if they don't exist or are empty."""
    import chromadb
    from pathlib import Path

    # Check BM25 index
    bm25_path = Path("rag/bm25_index.pkl")
    chroma_path = Path("chroma_db")

    needs_indexing = False

    if not bm25_path.exists():
        logger.info("📇 BM25 index not found")
        needs_indexing = True
    else:
        logger.info("✅ BM25 index exists")

    # Check ChromaDB
    if not chroma_path.exists() or not any(chroma_path.iterdir()):
        logger.info("📇 ChromaDB index not found")
        needs_indexing = True
    else:
        try:
            client = chromadb.PersistentClient(path="chroma_db")
            coll = client.get_collection("invoices")
            count = coll.count()
            if count == 0:
                logger.info("📇 ChromaDB empty")
                needs_indexing = True
            else:
                logger.info(f"✅ ChromaDB exists ({count} documents)")
        except Exception:
            logger.info("📇 ChromaDB needs rebuild")
            needs_indexing = True

    if needs_indexing:
        # Check if we have extractions to index
        extractions_dir = Path("outputs/extractions")
        json_files = list(extractions_dir.glob("*.json"))

        if not json_files:
            logger.info("⚠️  No extractions found. Indexes will be empty.")
            logger.info("   💡 Upload invoices via the frontend to extract data.")
            return

        logger.info(f"🔨 Building indexes from {len(json_files)} extractions...")
        from rag.indexer import index_all_extractions
        from rag.bm25_retriever import build_bm25_index

        try:
            index_all_extractions()
            build_bm25_index()
            logger.info("✅ Indexes built successfully")
        except Exception as e:
            logger.error(f"❌ Index building failed: {e}")
            logger.info("   💡 You can still use the frontend to extract invoices.")


def run_batch_extraction():
    """Process all invoices in data/input/."""
    logger.info("🚀 Running batch extraction...")
    logger.info("   This may take a few minutes...\n")

    try:
        from run_batch_extract import main as batch_main
        batch_main()
        logger.info("✅ Batch extraction complete\n")
    except Exception as e:
        logger.error(f"❌ Batch extraction failed: {e}")
        logger.info("   💡 You can still use the frontend to extract invoices manually.\n")


def launch_frontend():
    """Launch API server in background, then Streamlit frontend."""
    logger.info("🚀 Starting API server in background...")

    # Start API server as background process
    api_process = subprocess.Popen(
        [sys.executable, "run_api.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait a bit for API to start
    import time
    time.sleep(3)

    logger.info("✅ API server running at http://localhost:8000")
    logger.info("🚀 Launching frontend...")
    logger.info("   Opening http://localhost:8501 in your browser...\n")
    logger.info("=" * 60)
    logger.info("📌 Frontend + API running. Press Ctrl+C to stop both.")
    logger.info("=" * 60)
    logger.info("")

    try:
        subprocess.run(
            [sys.executable, "run_frontend.py"],
            check=True,
        )
    except KeyboardInterrupt:
        logger.info("\n👋 Shutting down...")
    except Exception as e:
        logger.error(f"❌ Failed to launch frontend: {e}")
    finally:
        # Stop API server
        logger.info("🛑 Stopping API server...")
        api_process.terminate()
        try:
            api_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            api_process.kill()


def launch_api():
    """Launch FastAPI server."""
    logger.info("🚀 Launching API server...")
    logger.info("   Opening http://localhost:8000/docs in your browser...\n")
    logger.info("=" * 60)
    logger.info("📌 API running. Press Ctrl+C to stop.")
    logger.info("=" * 60)
    logger.info("")

    try:
        subprocess.run(
            [sys.executable, "run_api.py"],
            check=True,
        )
    except KeyboardInterrupt:
        logger.info("\n👋 Shutting down...")
    except Exception as e:
        logger.error(f"❌ Failed to launch API: {e}")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Invoice Extraction System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py              # Launch frontend + API (default)
  python main.py --api        # Launch API server only
  python main.py --batch      # Process all invoices first
  python main.py --setup      # Setup only (no launch)
        """,
    )
    parser.add_argument(
        "--api",
        action="store_true",
        help="Launch API server only (no frontend)",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Run batch extraction before launching",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Run setup only (database + indexes), don't launch",
    )

    args = parser.parse_args()

    print("")
    logger.info("=" * 60)
    logger.info("📄 Invoice Extraction + RAG System")
    logger.info("=" * 60)
    logger.info("")

    # 1. Check prerequisites
    check_prerequisites()

    # 2. Setup database
    setup_database()
    logger.info("")

    # 3. Build indexes if needed
    setup_indexes()
    logger.info("")

    # 4. Batch extraction if requested
    if args.batch:
        run_batch_extraction()

    # 5. Launch frontend or API (or exit if --setup)
    if args.setup:
        logger.info("✅ Setup complete!")
        logger.info("   Run 'python main.py' to launch the frontend.")
        return

    if args.api:
        launch_api()
    else:
        launch_frontend()


if __name__ == "__main__":
    main()
