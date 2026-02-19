"""
Pipeline Orchestrator for Baseline Invoice Extraction.

This is the CENTRAL MODULE that ties everything together.
It orchestrates the complete extraction flow:

  ┌─────────────────────────────────────────────────────────────────────┐
  │                    BASELINE EXTRACTION PIPELINE                     │
  │                                                                     │
  │   ╔═══════════════╗                                                │
  │   ║ 1. LOAD       ║  DocumentLoader: Load PDF/Image, detect type   │
  │   ╚══════╤════════╝                                                │
  │          │                                                          │
  │   ╔══════╧════════╗                                                │
  │   ║ 2. EXTRACT    ║  TextExtractor: pdfplumber (PDF) / OCR (Image) │
  │   ║    TEXT        ║  → full_text, text_blocks, tables              │
  │   ╚══════╤════════╝                                                │
  │          │                                                          │
  │   ╔══════╧════════╗                                                │
  │   ║ 3. EXTRACT    ║  FieldExtractor: Regex + LayoutLM QA           │
  │   ║    FIELDS     ║  → 14 header fields with confidence            │
  │   ╚══════╤════════╝                                                │
  │          │                                                          │
  │   ╔══════╧════════╗                                                │
  │   ║ 4. EXTRACT    ║  TableExtractor: pdfplumber tables / text rows  │
  │   ║    LINE ITEMS ║  → line items with qty, price, amount           │
  │   ╚══════╤════════╝                                                │
  │          │                                                          │
  │   ╔══════╧════════╗                                                │
  │   ║ 5. POST-      ║  PostProcessor: Normalize + Validate           │
  │   ║    PROCESS    ║  → dates, amounts, cross-validation             │
  │   ╚══════╤════════╝                                                │
  │          │                                                          │
  │   ╔══════╧════════╗                                                │
  │   ║ 6. EXPORT     ║  ExportManager: JSON, Excel, CSV               │
  │   ╚═══════════════╝                                                │
  └─────────────────────────────────────────────────────────────────────┘

DESIGN DECISIONS:
  - Each step is a separate module for testability and modularity
  - Pipeline stops gracefully if a step fails for one invoice
  - Errors are caught per-invoice so one bad file doesn't crash the batch
  - Timing is recorded for performance analysis

Author: ML Engineering Team
Date: 2026-02-19
Version: 3.0.0 (Baseline)
"""

import logging
import os
import time
from typing import Any, Dict, List, Optional

from PIL import Image

from src.baseline.document_loader import DocumentLoader, LoadedDocument, discover_files
from src.baseline.text_extractor import TextExtractor, ExtractedText
from src.baseline.field_extractor import FieldExtractor
from src.baseline.table_extractor import TableExtractor
from src.baseline.postprocessor import PostProcessor
from src.baseline.export import ExportManager
from src.baseline.result import InvoiceResult, ExtractionMetadata

logger = logging.getLogger("invoice_extraction.baseline.pipeline")


# =============================================================================
# PIPELINE CONFIGURATION
# =============================================================================

DEFAULT_CONFIG = {
    # Document loading
    "supported_extensions": [".pdf", ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp"],

    # Text extraction
    "tesseract_lang": "eng",
    "tesseract_psm": 6,
    "min_text_length": 50,

    # Field extraction
    "use_layoutlm": True,  # Use LayoutLM Document QA model

    # Table extraction
    "min_table_columns": 3,
    "min_table_rows": 1,

    # Post-processing
    "prefer_dmy": True,           # Indian date format DD/MM/YYYY
    "validation_tolerance": 0.05,  # 5% tolerance for cross-validation

    # Export
    "export_formats": ["json", "excel", "csv"],
    "output_dir": "outputs/extractions",
}


# =============================================================================
# PIPELINE CLASS
# =============================================================================

class BaselinePipeline:
    """
    Orchestrates the complete invoice extraction pipeline.

    Usage:
        pipeline = BaselinePipeline()
        results = pipeline.run(input_dir="data/input/INVOICES")
        pipeline.export(results)

    Or process a single file:
        result = pipeline.process_single("data/input/INVOICES/PDF/GST001.pdf")
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize pipeline with configuration.

        Args:
            config: Optional configuration dictionary.
                    Missing keys will use DEFAULT_CONFIG values.
        """
        self.config = {**DEFAULT_CONFIG, **(config or {})}

        # Initialize sub-modules (lazy loading where possible)
        self.loader = DocumentLoader(config=self.config)
        self.text_extractor = TextExtractor(config=self.config)
        self.field_extractor = FieldExtractor(config=self.config)
        self.table_extractor = TableExtractor(config=self.config)
        self.postprocessor = PostProcessor(config=self.config)
        self.export_manager = ExportManager(
            output_dir=self.config["output_dir"]
        )

        logger.info("Baseline pipeline initialized")
        logger.info(f"  LayoutLM: {'enabled' if self.config['use_layoutlm'] else 'disabled'}")
        logger.info(f"  Date format: {'DD/MM/YYYY' if self.config['prefer_dmy'] else 'MM/DD/YYYY'}")
        logger.info(f"  Output: {self.config['output_dir']}")

    # =========================================================================
    # BATCH PROCESSING
    # =========================================================================

    def run(
        self,
        input_dir: str,
        max_files: Optional[int] = None,
    ) -> List[InvoiceResult]:
        """
        Process all invoices in a directory.

        Args:
            input_dir: Path to directory containing invoices.
            max_files: Optional limit on number of files to process.

        Returns:
            List of InvoiceResult objects (one per successfully processed file).
        """
        pipeline_start = time.time()

        # Discover files
        files = discover_files(input_dir)

        if max_files:
            files = files[:max_files]

        logger.info(f"Found {len(files)} invoice files in {input_dir}")

        # Process each file
        results: List[InvoiceResult] = []
        errors: List[Dict[str, str]] = []

        for idx, file_path in enumerate(files, 1):
            logger.info(f"[{idx}/{len(files)}] Processing: {os.path.basename(file_path)}")

            try:
                result = self.process_single(file_path)
                results.append(result)
                logger.info(
                    f"  → Extracted {self._count_fields(result)} fields, "
                    f"{len(result.line_items)} line items"
                )
            except Exception as e:
                logger.error(f"  → FAILED: {e}")
                errors.append({
                    "file": file_path,
                    "error": str(e),
                })

        # Summary
        pipeline_time = time.time() - pipeline_start
        logger.info("=" * 60)
        logger.info("PIPELINE COMPLETE")
        logger.info(f"  Processed: {len(results)}/{len(files)} files")
        logger.info(f"  Errors: {len(errors)}")
        logger.info(f"  Total time: {pipeline_time:.1f}s")
        if results:
            logger.info(
                f"  Avg time/file: {pipeline_time/len(results):.1f}s"
            )
        logger.info("=" * 60)

        return results

    # =========================================================================
    # SINGLE FILE PROCESSING
    # =========================================================================

    def process_single(self, file_path: str) -> InvoiceResult:
        """
        Process a single invoice file through the complete pipeline.

        Args:
            file_path: Path to the invoice file (PDF or image).

        Returns:
            InvoiceResult with extracted data.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If the file type is not supported.
            RuntimeError: If extraction fails completely.
        """
        total_start = time.time()

        # Initialize result
        result = InvoiceResult()
        result.metadata.source_file = os.path.basename(file_path)

        # =====================================================================
        # Step 1: LOAD DOCUMENT
        # =====================================================================
        logger.debug(f"Step 1: Loading document...")
        doc: LoadedDocument = self.loader.load(file_path)
        result.metadata.document_type = doc.document_type
        result.metadata.page_count = doc.page_count

        # =====================================================================
        # Step 2: EXTRACT TEXT
        # =====================================================================
        logger.debug(f"Step 2: Extracting text ({doc.document_type})...")
        text_start = time.time()

        extracted: ExtractedText = self.text_extractor.extract(
            document_type=doc.document_type,
            pdfplumber_doc=doc.pdfplumber_doc,
            images=doc.images,
        )
        result.metadata.text_extraction_method = extracted.method
        result.metadata.text_extraction_time_ms = int(
            (time.time() - text_start) * 1000
        )
        result.metadata.average_text_confidence = extracted.avg_confidence

        if len(extracted.full_text.strip()) < 20:
            logger.warning(
                f"Very little text extracted ({len(extracted.full_text)} chars). "
                f"Results may be poor."
            )

        # =====================================================================
        # Step 3: EXTRACT HEADER FIELDS
        # =====================================================================
        logger.debug(f"Step 3: Extracting header fields...")
        field_start = time.time()

        # Get first page image for LayoutLM (if available)
        first_image = doc.images[0] if doc.images else None

        self.field_extractor.extract_fields(
            result=result,
            full_text=extracted.full_text,
            image=first_image,
        )
        result.metadata.field_extraction_time_ms = int(
            (time.time() - field_start) * 1000
        )

        # =====================================================================
        # Step 4: EXTRACT LINE ITEMS
        # =====================================================================
        logger.debug(f"Step 4: Extracting line items...")

        self.table_extractor.extract_line_items(
            result=result,
            full_text=extracted.full_text,
            tables=extracted.tables if extracted.tables else None,
        )

        # =====================================================================
        # Step 5: POST-PROCESS
        # =====================================================================
        logger.debug(f"Step 5: Post-processing...")

        self.postprocessor.process(result)

        # =====================================================================
        # FINALIZE
        # =====================================================================
        result.metadata.total_extraction_time_ms = int(
            (time.time() - total_start) * 1000
        )

        # Clean up document resources (close pdfplumber doc)
        doc.close()

        return result

    # =========================================================================
    # EXPORT
    # =========================================================================

    def export(
        self,
        results: List[InvoiceResult],
        formats: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """
        Export results to file(s).

        Args:
            results: List of extraction results.
            formats: List of formats ("json", "excel", "csv").

        Returns:
            Dictionary mapping format to output file path.
        """
        if formats is None:
            formats = self.config["export_formats"]

        output_files = self.export_manager.export_all(results, formats)

        for fmt, path in output_files.items():
            logger.info(f"Exported {fmt}: {path}")

        return output_files

    # =========================================================================
    # UTILITY
    # =========================================================================

    def _count_fields(self, result: InvoiceResult) -> int:
        """Count how many header fields were extracted."""
        from src.baseline.result import HEADER_FIELD_NAMES
        return sum(
            1 for name in HEADER_FIELD_NAMES
            if result.get_header(name) and result.get_header(name).value
        )


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def run_baseline_pipeline(
    input_dir: str,
    output_dir: str = "outputs/extractions",
    max_files: Optional[int] = None,
    use_layoutlm: bool = True,
    export_formats: Optional[List[str]] = None,
) -> List[InvoiceResult]:
    """
    Convenience function to run the baseline pipeline.

    Args:
        input_dir: Path to directory with invoice files.
        output_dir: Path to output directory.
        max_files: Optional limit on files to process.
        use_layoutlm: Whether to use LayoutLM model.
        export_formats: List of export formats.

    Returns:
        List of InvoiceResult objects.
    """
    config = {
        "output_dir": output_dir,
        "use_layoutlm": use_layoutlm,
        "export_formats": export_formats or ["json", "excel", "csv"],
    }

    pipeline = BaselinePipeline(config=config)
    results = pipeline.run(input_dir=input_dir, max_files=max_files)
    pipeline.export(results)

    return results
