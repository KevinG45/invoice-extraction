"""
Batch extraction runner — processes all invoices in data/input/INVOICES/
and writes individual JSON results to outputs/extractions/.

Usage:
    python run_batch_extract.py
"""

import sys
import os
import logging
import time
import glob as globmod

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Speed up: fail fast on LLM JSON errors → use regex fallback after 1 try
os.environ.setdefault("LLM_MAX_RETRIES", "1")

from core.config import DATA_DIR, OUTPUTS_DIR
from core.pipeline import InvoicePipeline, discover_files

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _already_extracted(fname: str) -> bool:
    """Check if a JSON output already exists for this file."""
    stem = os.path.splitext(fname)[0]
    pattern = os.path.join(str(OUTPUTS_DIR), f"{stem}_*.json")
    return len(globmod.glob(pattern)) > 0


def main():
    pdf_dir = str(DATA_DIR / "PDF")
    img_dir = str(DATA_DIR / "IMAGES")

    files = discover_files(pdf_dir) + discover_files(img_dir)
    total = len(files)

    if total == 0:
        logger.error("No invoice files found in %s", DATA_DIR)
        sys.exit(1)

    # Filter out already-processed files
    to_process = []
    skipped = 0
    for fpath in files:
        fname = os.path.basename(fpath)
        if _already_extracted(fname):
            skipped += 1
        else:
            to_process.append(fpath)

    logger.info("Found %d invoice files. %d already extracted, %d to process.",
                total, skipped, len(to_process))

    if not to_process:
        logger.info("All files already extracted. Nothing to do.")
        return

    pipeline = InvoicePipeline()
    succeeded = 0
    failed = 0
    failures = []
    start = time.time()

    for i, fpath in enumerate(to_process, 1):
        fname = os.path.basename(fpath)
        logger.info("[%d/%d] Processing: %s", i, len(to_process), fname)
        try:
            result = pipeline.run(fpath)
            out_path = pipeline.save_result(result)
            logger.info("[%d/%d] OK  → %s", i, len(to_process), out_path)
            succeeded += 1
        except Exception as exc:
            logger.error("[%d/%d] FAIL → %s: %s", i, len(to_process), fname, exc)
            failed += 1
            failures.append((fname, str(exc)))

    elapsed = time.time() - start

    print("\n" + "=" * 60)
    print(f"BATCH EXTRACTION COMPLETE  ({elapsed:.1f}s)")
    print(f"  Total files  : {total}")
    print(f"  Skipped      : {skipped}")
    print(f"  Processed    : {succeeded + failed}")
    print(f"  Succeeded    : {succeeded}")
    print(f"  Failed       : {failed}")
    print(f"  Output dir   : {OUTPUTS_DIR}")
    print("=" * 60)

    if failures:
        print("\nFailures:")
        for fname, err in failures:
            print(f"  - {fname}: {err}")

    if succeeded == 0 and skipped == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
