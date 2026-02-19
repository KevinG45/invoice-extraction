#!/usr/bin/env python3
"""
Invoice Extraction System v2.0.0 - Main Entrypoint (2026)

Production-ready invoice extraction using:
  - Sarvam Vision 3B (primary)
  - DeepSeek-OCR 2 (verification)
  - PaddleOCR-VL 1.5 (fallback)
  - 6-layer anti-hallucination validation
  - JSON/Excel/CSV export with full metadata

Usage:
  python main_2026.py --input data/input/INVOICES --output outputs/extractions
  python main_2026.py --input invoice.pdf --format json excel
  python main_2026.py --api --port 8000
  python main_2026.py --input data/input --model sarvam_vision --skip-validation

Author: ML Engineering Team
Version: 2.0.0
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)


# ---------------------------------------------------------------------------
# Logger setup
# ---------------------------------------------------------------------------

def setup_logging(log_level: str = "INFO", log_dir: str = "logs") -> logging.Logger:
    """Configure logging."""
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    logger = logging.getLogger("invoice_extraction")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Console handler
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    ))
    logger.addHandler(console)

    # File handler
    file_handler = logging.FileHandler(
        os.path.join(log_dir, f"extraction_{timestamp}.log"),
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s",
    ))
    logger.addHandler(file_handler)

    return logger


# ---------------------------------------------------------------------------
# Load configuration
# ---------------------------------------------------------------------------

def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load configuration from YAML."""
    if config_path is None:
        config_path = os.path.join(PROJECT_ROOT, "config", "models_2026.yaml")

    if not os.path.exists(config_path):
        logger.warning(f"Config not found at {config_path}, using defaults")
        return {}

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    logger.info(f"Config loaded from {config_path}")
    return config


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

SUPPORTED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp",
    ".pdf",
}


def discover_files(input_path: str) -> List[str]:
    """Find all supported invoice files in input path."""
    input_path = os.path.abspath(input_path)

    if os.path.isfile(input_path):
        ext = os.path.splitext(input_path)[1].lower()
        if ext in SUPPORTED_EXTENSIONS:
            return [input_path]
        else:
            logger.warning(f"Unsupported file type: {ext}")
            return []

    if os.path.isdir(input_path):
        files = []
        for root, _, filenames in os.walk(input_path):
            for fn in sorted(filenames):
                ext = os.path.splitext(fn)[1].lower()
                if ext in SUPPORTED_EXTENSIONS:
                    files.append(os.path.join(root, fn))
        logger.info(f"Discovered {len(files)} invoice files in {input_path}")
        return files

    logger.error(f"Input path not found: {input_path}")
    return []


# ---------------------------------------------------------------------------
# Image loading
# ---------------------------------------------------------------------------

def load_image(file_path: str):
    """Load image from file path. For PDFs, converts first page."""
    from PIL import Image

    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        return _load_pdf_page(file_path)
    else:
        return Image.open(file_path).convert("RGB")


def _load_pdf_page(pdf_path: str, page_num: int = 0):
    """Convert a PDF page to PIL Image."""
    try:
        import fitz
        doc = fitz.open(pdf_path)
        page = doc[page_num]
        pix = page.get_pixmap(dpi=300)
        from PIL import Image
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        doc.close()
        return img
    except ImportError:
        pass

    try:
        from pdf2image import convert_from_path
        images = convert_from_path(pdf_path, dpi=300, first_page=page_num + 1, last_page=page_num + 1)
        return images[0] if images else None
    except ImportError:
        logger.error("Neither PyMuPDF nor pdf2image installed for PDF support")
        return None


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_extraction_pipeline(
    files: List[str],
    config: Dict[str, Any],
    force_model: Optional[str] = None,
    skip_validation: bool = False,
    output_dir: str = "outputs/extractions",
    output_formats: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Run the full extraction pipeline on a list of files.

    Returns summary dict.
    """
    from src.models.model_router import ModelRouter
    from src.preprocessing.pipeline_2026 import PreprocessingPipeline2026
    from src.validation.framework_2026 import ValidationFramework2026
    from src.export.export_handlers_2026 import ExportManager2026

    if output_formats is None:
        output_formats = config.get("output", {}).get("formats", ["json", "excel"])

    pipeline_start = time.time()

    # Initialize components
    logger.info("=" * 60)
    logger.info("Invoice Extraction System v2.0.0")
    logger.info("=" * 60)

    logger.info("Initializing preprocessing pipeline...")
    preprocessor = PreprocessingPipeline2026(config)

    logger.info("Initializing model router...")
    router = ModelRouter(config)
    router.initialize_models()

    if not skip_validation:
        logger.info("Initializing 6-layer validation framework...")
        validator = ValidationFramework2026(config)
    else:
        validator = None
        logger.info("Validation skipped by user request")

    # Override output dir in config
    export_config = dict(config)
    export_config.setdefault("output", {})["output_dir"] = output_dir
    export_config["output"]["formats"] = output_formats
    exporter = ExportManager2026(export_config)

    # Process files
    extractions = []
    validation_reports = []
    errors = []

    logger.info(f"\nProcessing {len(files)} files...")
    logger.info("-" * 40)

    for idx, file_path in enumerate(files, 1):
        file_name = os.path.basename(file_path)
        logger.info(f"[{idx}/{len(files)}] Processing: {file_name}")
        file_start = time.time()

        try:
            # Step 1: Load image
            image = load_image(file_path)
            if image is None:
                errors.append((file_path, "Failed to load image"))
                continue

            # Step 2: Preprocess
            processed, quality = preprocessor.process(image)
            logger.info(
                f"  Quality: {quality.overall_quality:.2f} "
                f"(noise={quality.noise_score:.2f}, "
                f"blur={quality.blur_score:.2f})"
            )

            # Step 3: Extract
            extraction = router.extract(
                processed,
                source_file=file_name,
                quality_score=quality.overall_quality,
                force_model=force_model,
            )
            logger.info(
                f"  Extracted: {len(extraction.line_items)} line items, "
                f"model={extraction.model_used}"
            )

            # Step 4: Validate
            if validator:
                report = validator.validate(
                    extraction,
                    image=processed,
                )
                validation_reports.append(report)
                logger.info(
                    f"  Validation: score={report['overall_score']:.2f}, "
                    f"decision={report['overall_decision']}, "
                    f"issues={len(report['all_issues'])}"
                )
            else:
                validation_reports.append(None)

            # Record timing
            file_time = int((time.time() - file_start) * 1000)
            extraction.processing_time_ms = file_time
            logger.info(f"  Time: {file_time}ms")

            extractions.append(extraction)

        except Exception as e:
            logger.error(f"  ERROR: {e}", exc_info=True)
            errors.append((file_path, str(e)))

    # Step 5: Export
    logger.info("-" * 40)
    if extractions:
        logger.info(f"Exporting {len(extractions)} results...")
        export_paths = exporter.export_all(
            extractions,
            validation_reports=[r for r in validation_reports if r],
            metadata={
                "input_path": str(files[0]) if len(files) == 1 else f"{len(files)} files",
                "model_forced": force_model,
                "validation_enabled": not skip_validation,
            },
        )

        for fmt, path in export_paths.items():
            logger.info(f"  {fmt}: {path}")
    else:
        export_paths = {}
        logger.warning("No successful extractions to export")

    # Summary
    total_time = time.time() - pipeline_start
    summary = {
        "total_files": len(files),
        "successful": len(extractions),
        "failed": len(errors),
        "errors": errors,
        "total_time_seconds": round(total_time, 2),
        "avg_time_per_file_ms": round(
            (total_time * 1000) / len(files), 0
        ) if files else 0,
        "export_paths": export_paths,
    }

    logger.info("")
    logger.info("=" * 60)
    logger.info("EXTRACTION COMPLETE")
    logger.info(f"  Total files: {summary['total_files']}")
    logger.info(f"  Successful:  {summary['successful']}")
    logger.info(f"  Failed:      {summary['failed']}")
    logger.info(f"  Total time:  {summary['total_time_seconds']:.1f}s")
    logger.info(f"  Avg/file:    {summary['avg_time_per_file_ms']:.0f}ms")
    logger.info("=" * 60)

    if errors:
        logger.warning("Failed files:")
        for fp, err in errors:
            logger.warning(f"  {os.path.basename(fp)}: {err}")

    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Invoice Extraction System v2.0.0 (2026)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --input data/input/INVOICES
  %(prog)s --input invoice.pdf --format json excel csv
  %(prog)s --input data/input --model sarvam_vision
  %(prog)s --api --port 8000
  %(prog)s --input data/input --skip-validation
        """,
    )

    parser.add_argument(
        "--input", "-i",
        help="Input file or directory path",
    )
    parser.add_argument(
        "--output", "-o",
        default="outputs/extractions",
        help="Output directory (default: outputs/extractions)",
    )
    parser.add_argument(
        "--format", "-f",
        nargs="+",
        choices=["json", "excel", "csv"],
        default=["json", "excel"],
        help="Output formats (default: json excel)",
    )
    parser.add_argument(
        "--model", "-m",
        choices=["sarvam_vision", "deepseek_ocr2", "paddleocr_vl", "qwen3_vl"],
        help="Force a specific model (default: auto-route)",
    )
    parser.add_argument(
        "--config", "-c",
        help="Path to config YAML file",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip 6-layer validation (faster but less reliable)",
    )
    parser.add_argument(
        "--api",
        action="store_true",
        help="Run as REST API server",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="API server host (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="API server port (default: 8000)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )

    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    args = parse_args()

    # Setup logging
    logger = setup_logging(args.log_level)

    # Load config
    config = load_config(args.config)

    # API mode
    if args.api:
        from src.api.api_service_2026 import run_api
        run_api(config, host=args.host, port=args.port)
        sys.exit(0)

    # CLI mode - require input
    if not args.input:
        print("Error: --input is required (or use --api for server mode)")
        print("Run with --help for usage")
        sys.exit(1)

    # Discover files
    files = discover_files(args.input)
    if not files:
        print(f"No supported files found in: {args.input}")
        sys.exit(1)

    # Run pipeline
    summary = run_extraction_pipeline(
        files=files,
        config=config,
        force_model=args.model,
        skip_validation=args.skip_validation,
        output_dir=args.output,
        output_formats=args.format,
    )

    # Exit code
    sys.exit(0 if summary["failed"] == 0 else 1)
