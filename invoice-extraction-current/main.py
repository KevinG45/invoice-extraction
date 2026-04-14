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
    """
    Check if Ollama and Tesseract are installed.
    FIXED: Bug P0-4 - Exit with helpful message if prerequisites missing.
    """
    logger.info("Checking prerequisites...")
    
    errors = []

    # Check Tesseract
    try:
        result = subprocess.run(
            ["tesseract", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            logger.info("  Tesseract OCR: OK")
        else:
            errors.append("Tesseract OCR not working properly")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        errors.append("Tesseract OCR not found")

    # Check Ollama
    ollama_ok = False
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            ollama_ok = True
            if "qwen2.5:3b" in result.stdout or "qwen" in result.stdout:
                logger.info("  Ollama + qwen2.5:3b model: OK")
            else:
                errors.append("Ollama model 'qwen2.5:3b' not found")
        else:
            errors.append("Ollama not responding")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        errors.append("Ollama not found")

    # FIXED: Bug P0-4 - Show helpful error and exit if prerequisites missing
    if errors:
        logger.error("")
        logger.error("=" * 60)
        logger.error("PREREQUISITES MISSING")
        logger.error("=" * 60)
        for err in errors:
            logger.error(f"  {err}")
        logger.error("")
        logger.error("Please install missing prerequisites:")
        logger.error("")
        if "Tesseract" in " ".join(errors):
            logger.error("  Tesseract OCR:")
            logger.error("    Windows: https://github.com/UB-Mannheim/tesseract/wiki")
            logger.error("    Ubuntu:  sudo apt install tesseract-ocr")
            logger.error("    macOS:   brew install tesseract")
            logger.error("")
        if "Ollama" in " ".join(errors):
            logger.error("  Ollama:")
            logger.error("    Install: https://ollama.com")
            logger.error("    Then run: ollama pull qwen2.5:3b")
            logger.error("")
        logger.error("=" * 60)
        sys.exit(1)

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


def launch_frontend(api_port: int = 8000, frontend_port: int = 8501):
    """Launch API server in background, then Streamlit frontend."""
    import time
    import requests

    logger.info("Starting API server in background on port %d...", api_port)

    # Pass API_PORT via environment so config.py picks it up
    env = os.environ.copy()
    env["API_PORT"] = str(api_port)

    api_log_path = f"api_{api_port}.log"
    api_log = open(api_log_path, "w")
    api_process = subprocess.Popen(
        [sys.executable, "run_api.py"],
        stdout=api_log,
        stderr=subprocess.STDOUT,
        env=env,
    )

    # Wait and verify API actually started
    logger.info("   Waiting for API to initialize...")
    api_ready = False
    for attempt in range(15):
        time.sleep(1)
        try:
            response = requests.get(f"http://localhost:{api_port}/health", timeout=2)
            if response.status_code == 200:
                api_ready = True
                break
        except requests.RequestException:
            pass

    if not api_ready:
        logger.error("API server failed to start! Check %s for errors", api_log_path)
        api_process.terminate()
        sys.exit(1)

    logger.info("API server running at http://localhost:%d", api_port)
    logger.info("Launching frontend on port %d...", frontend_port)
    logger.info("=" * 60)
    logger.info("Frontend + API running. Press Ctrl+C to stop both.")
    logger.info("=" * 60)
    logger.info("")

    try:
        subprocess.run(
            [
                sys.executable, "-m", "streamlit", "run", "frontend/app.py",
                "--server.port", str(frontend_port),
                "--server.headless", "true",
            ],
            env={**env, "API_PORT": str(api_port), "API_URL": f"http://localhost:{api_port}"},
            check=True,
        )
    except KeyboardInterrupt:
        logger.info("\nShutting down...")
    except Exception as e:
        logger.error("Failed to launch frontend: %s", e)
    finally:
        logger.info("Stopping API server...")
        api_process.terminate()
        try:
            api_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            api_process.kill()
        api_log.close()


def launch_api(api_port: int = 8000):
    """Launch FastAPI server."""
    logger.info("Launching API server on port %d...", api_port)
    logger.info("=" * 60)
    logger.info("API running. Press Ctrl+C to stop.")
    logger.info("=" * 60)
    logger.info("")

    env = os.environ.copy()
    env["API_PORT"] = str(api_port)

    try:
        subprocess.run(
            [sys.executable, "run_api.py"],
            env=env,
            check=True,
        )
    except KeyboardInterrupt:
        logger.info("\nShutting down...")
    except Exception as e:
        logger.error("Failed to launch API: %s", e)


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
    parser.add_argument(
        "--api-port",
        type=int,
        default=int(os.getenv("API_PORT", "8000")),
        help="Port for the API server (default: 8000)",
    )
    parser.add_argument(
        "--frontend-port",
        type=int,
        default=8501,
        help="Port for the Streamlit frontend (default: 8501)",
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
        launch_api(api_port=args.api_port)
    else:
        launch_frontend(api_port=args.api_port, frontend_port=args.frontend_port)


if __name__ == "__main__":
    main()
