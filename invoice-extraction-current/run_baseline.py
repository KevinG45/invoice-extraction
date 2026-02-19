"""
Baseline Invoice Extraction - Main Entry Point.

Processes invoice images and PDFs to extract:
  - Header fields (invoice number, dates, vendor/customer info, amounts)
  - Line items (description, quantity, price, tax, total)

USAGE:
  # Process all invoices in default directory:
  python run_baseline.py

  # Process specific directory:
  python run_baseline.py --input data/input/INVOICES

  # Process only PDFs, limit to 10 files:
  python run_baseline.py --input data/input/INVOICES/PDF --max-files 10

  # Process only images:
  python run_baseline.py --input data/input/INVOICES/IMAGES

  # Disable LayoutLM model (regex only, faster):
  python run_baseline.py --no-layoutlm

  # Custom output directory:
  python run_baseline.py --output outputs/my_run

  # Export only JSON:
  python run_baseline.py --format json

  # Process a single file:
  python run_baseline.py --file data/input/INVOICES/PDF/GST001.pdf

PIPELINE OVERVIEW:
  1. LOAD: Read PDF/Image files, detect digital vs scanned
  2. TEXT: Extract text via pdfplumber (digital PDFs) or Tesseract OCR (images)
  3. FIELDS: Extract 14 header fields using regex + LayoutLM Document QA
  4. ITEMS: Extract line items from tables (pdfplumber) or text (regex)
  5. VALIDATE: Cross-validate (subtotal + tax = total, qty × price = amount)
  6. EXPORT: Save results as JSON, Excel, CSV

REQUIREMENTS:
  - Python 3.8+
  - pdfplumber, PyMuPDF (fitz), pytesseract, Pillow, openpyxl
  - Tesseract OCR installed (for image extraction)
  - transformers (for LayoutLM model, optional)

Author: ML Engineering Team
Date: 2026-02-19
Version: 3.0.0 (Baseline)
"""

import argparse
import logging
import os
import sys
import time


def setup_logging(log_level: str = "INFO", log_file: str = "logs/baseline.log") -> None:
    """
    Configure logging for the pipeline.

    Logs to both console (colored) and file.
    """
    # Create logs directory if needed
    log_dir = os.path.dirname(log_file)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    # Root logger for our modules
    root_logger = logging.getLogger("invoice_extraction")
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Console handler (human-readable)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        "%(asctime)s │ %(levelname)-8s │ %(message)s",
        datefmt="%H:%M:%S",
    )
    console_handler.setFormatter(console_format)

    # File handler (detailed)
    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        "%(asctime)s │ %(name)s │ %(levelname)-8s │ %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_format)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Reduce noise from external libraries
    logging.getLogger("pdfminer").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("transformers").setLevel(logging.WARNING)
    logging.getLogger("torch").setLevel(logging.WARNING)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Baseline Invoice Extraction Pipeline v3.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_baseline.py
  python run_baseline.py --input data/input/INVOICES/PDF --max-files 5
  python run_baseline.py --file data/input/INVOICES/PDF/GST001.pdf
  python run_baseline.py --no-layoutlm --format json
        """,
    )

    parser.add_argument(
        "--input", "-i",
        default="data/input/INVOICES",
        help="Input directory containing invoices (default: data/input/INVOICES)",
    )

    parser.add_argument(
        "--file", "-f",
        default=None,
        help="Process a single file instead of a directory",
    )

    parser.add_argument(
        "--output", "-o",
        default="outputs/extractions",
        help="Output directory for results (default: outputs/extractions)",
    )

    parser.add_argument(
        "--format",
        nargs="+",
        default=["json", "excel", "csv"],
        choices=["json", "excel", "csv"],
        help="Export formats (default: json excel csv)",
    )

    parser.add_argument(
        "--max-files", "-m",
        type=int,
        default=None,
        help="Maximum number of files to process",
    )

    parser.add_argument(
        "--no-layoutlm",
        action="store_true",
        help="Disable LayoutLM model (use regex only, faster)",
    )

    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )

    parser.add_argument(
        "--prefer-mdy",
        action="store_true",
        help="Prefer MM/DD/YYYY date format instead of DD/MM/YYYY (Indian)",
    )

    return parser.parse_args()


def print_banner() -> None:
    """Print a startup banner."""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║           BASELINE INVOICE EXTRACTION PIPELINE              ║
║                       Version 3.0.0                         ║
║                                                              ║
║   Strategies:  pdfplumber + Tesseract OCR + Regex + LayoutLM ║
║   Output:      JSON, Excel, CSV                              ║
╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)


def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Setup
    setup_logging(log_level=args.log_level)
    logger = logging.getLogger("invoice_extraction.baseline.main")
    print_banner()

    # Import pipeline (after logging is configured)
    from src.baseline.pipeline import BaselinePipeline

    # Configuration
    config = {
        "output_dir": args.output,
        "use_layoutlm": not args.no_layoutlm,
        "export_formats": args.format,
        "prefer_dmy": not args.prefer_mdy,
    }

    # Initialize pipeline
    pipeline = BaselinePipeline(config=config)

    start_time = time.time()

    # ==========================================================================
    # SINGLE FILE MODE
    # ==========================================================================
    if args.file:
        if not os.path.isfile(args.file):
            logger.error(f"File not found: {args.file}")
            sys.exit(1)

        logger.info(f"Processing single file: {args.file}")
        result = pipeline.process_single(args.file)
        results = [result]

        # Print result summary
        _print_single_result(result)

    # ==========================================================================
    # BATCH MODE
    # ==========================================================================
    else:
        if not os.path.isdir(args.input):
            logger.error(f"Input directory not found: {args.input}")
            sys.exit(1)

        logger.info(f"Processing directory: {args.input}")
        results = pipeline.run(
            input_dir=args.input,
            max_files=args.max_files,
        )

    # ==========================================================================
    # EXPORT
    # ==========================================================================
    if results:
        output_files = pipeline.export(results, formats=args.format)

        # Print summary
        elapsed = time.time() - start_time
        print("\n" + "=" * 60)
        print("EXTRACTION COMPLETE")
        print("=" * 60)
        print(f"  Files processed: {len(results)}")
        print(f"  Total time: {elapsed:.1f}s")
        print(f"  Average time/file: {elapsed/len(results):.1f}s")
        print()
        print("  Output files:")
        for fmt, path in output_files.items():
            print(f"    {fmt}: {path}")
        print("=" * 60)
    else:
        logger.warning("No results to export")


def _print_single_result(result) -> None:
    """Print a summary of a single file extraction."""
    from src.baseline.result import HEADER_FIELD_NAMES

    print("\n" + "-" * 60)
    print(f"FILE: {result.metadata.source_file}")
    print(f"TYPE: {result.metadata.document_type}")
    print(f"TEXT METHOD: {result.metadata.text_extraction_method}")
    print("-" * 60)

    print("\nHEADER FIELDS:")
    for field_name in HEADER_FIELD_NAMES:
        header = result.get_header(field_name)
        if header and header.value:
            conf_bar = "█" * int(header.confidence / 10)
            uncertain_mark = " ⚠" if header.uncertain else ""
            print(
                f"  {field_name:20s} │ {header.value:30s} │ "
                f"{header.confidence:5.1f}% {conf_bar}{uncertain_mark}"
            )
        else:
            print(f"  {field_name:20s} │ {'(not found)':30s} │")

    if result.line_items:
        print(f"\nLINE ITEMS ({len(result.line_items)}):")
        print(f"  {'#':>3s}  {'Description':30s}  {'Qty':>8s}  {'Price':>10s}  {'Total':>12s}  {'Conf':>5s}")
        print("  " + "-" * 75)
        for item in result.line_items:
            desc = (item.description or "")[:30]
            qty = f"{item.quantity:.0f}" if item.quantity else "-"
            price = f"{item.unit_price:.2f}" if item.unit_price else "-"
            total = f"{item.line_total:.2f}" if item.line_total else "-"
            print(
                f"  {item.line_number:3d}  {desc:30s}  {qty:>8s}  {price:>10s}  "
                f"{total:>12s}  {item.confidence:5.1f}%"
            )

    if result.validation_results:
        print(f"\nVALIDATION ({len(result.validation_results)} checks):")
        for v in result.validation_results:
            status_icon = {"PASS": "✓", "FAIL": "✗", "SKIP": "–"}.get(
                v["status"], "?"
            )
            print(f"  {status_icon} [{v['status']}] {v['message']}")


if __name__ == "__main__":
    main()
