"""
Invoice Extraction Pipeline — master orchestrator for all extraction modules.

Flow:
    Input (PDF or Image)
        → Stage 1: detect_file_type()
        → Stage 2: extract raw text (digital → pdfplumber, scanned/image → OCR)
        → Stage 3: extract tables
        → Stage 4: LLM key information extraction
        → Stage 5: merge table data into line_items if LLM found none
        → Stage 6: validation & post-processing
        → Add metadata section
        → Structured JSON output

RULES:
    - Does NOT re-implement any logic — calls existing modules.
    - No single module failure crashes the pipeline (try/except per stage).
    - Every stage is timed and logged.
    - Returns a dict with invoice fields + metadata + validation.
"""

import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.config import SUPPORTED_EXTENSIONS, OUTPUTS_DIR, OCR_ENGINE

logger = logging.getLogger(__name__)


class InvoicePipeline:
    """
    Main orchestrator for invoice extraction.

    Usage::

        pipeline = InvoicePipeline()
        result = pipeline.run("invoice.pdf")
        print(result)  # Full invoice JSON with metadata and validation
    """

    def run(self, path: str) -> Dict[str, Any]:
        """
        Process any invoice file (PDF or image) and return structured JSON.

        Args:
            path: absolute or relative path to the invoice file.

        Returns:
            dict: Extracted invoice fields + metadata + validation.

        Raises:
            FileNotFoundError: if path does not exist.
            ValueError: if file type not supported.
        """
        path = str(Path(path).resolve())
        start_time = time.time()
        logger.info("[pipeline] ═══ Starting extraction: %s ═══", Path(path).name)

        # ── Validate file ─────────────────────────────────────────────────
        if not os.path.exists(path):
            raise FileNotFoundError(f"Invoice file not found: {path}")

        ext = Path(path).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file type: {ext}")

        # ── Stage 1: Detect file type ─────────────────────────────────────
        t = time.time()
        from core.detector import detect_file_type
        _t_stage = time.time()
        pdf_type = detect_file_type(path)
        print(f"[TIMING] detect_file_type: {time.time()-_t_stage:.1f}s")
        logger.info("[pipeline] Stage 1 - Detection: '%s' (%.2fs)", pdf_type, time.time() - t)

        # ── Stage 2: Extract raw text ─────────────────────────────────────
        t = time.time()
        _t_stage = time.time()
        raw_data = self._extract_text(path, pdf_type)
        print(f"[TIMING] _extract_text: {time.time()-_t_stage:.1f}s")
        full_text = raw_data.get("full_text", "")
        page_count = raw_data.get("page_count", 1)
        logger.info(
            "[pipeline] Stage 2 - Text extraction: %d chars, %d pages (%.2fs)",
            len(full_text), page_count, time.time() - t,
        )

        # ── Stage 3: Extract tables ───────────────────────────────────────
        t = time.time()
        _t_stage = time.time()
        tables = self._extract_tables(path, pdf_type)
        print(f"[TIMING] _extract_tables: {time.time()-_t_stage:.1f}s")
        logger.info("[pipeline] Stage 3 - Tables: %d found (%.2fs)", len(tables), time.time() - t)

        # ── Stage 4: LLM Key Information Extraction ───────────────────────
        t = time.time()
        _t_stage = time.time()
        invoice_fields = self._extract_with_llm(full_text)
        print(f"[TIMING] _extract_with_llm: {time.time()-_t_stage:.1f}s")
        logger.info(
            "[pipeline] Stage 4 - LLM extraction: %d fields (%.2fs)",
            len(invoice_fields), time.time() - t,
        )

        # ── Stage 4b: Regex backfill for fields the LLM missed ────────────
        _t_stage = time.time()
        invoice_fields = self._backfill_from_regex(invoice_fields, full_text)
        print(f"[TIMING] _backfill_from_regex: {time.time()-_t_stage:.1f}s")

        # ── Stage 4c: Logo-based vendor name fallback ─────────────────────
        vendor_obj = invoice_fields.get("vendor") or {}
        if not vendor_obj.get("name") and pdf_type == "image":
            # Only run on image files — EasyOCR cannot process PDFs directly
            from core.logo_extractor import extract_vendor_from_logo
            _t_stage = time.time()
            logo_result = extract_vendor_from_logo(path)
            print(f"[TIMING] extract_vendor_from_logo: {time.time()-_t_stage:.1f}s")
            if logo_result["vendor_name"] is not None:
                vendor_obj["name"] = logo_result["vendor_name"]
                invoice_fields.setdefault("vendor", vendor_obj)
                logger.info(
                    "[pipeline] Stage 4c - Logo fallback: vendor.name='%s' (conf=%.2f, method=%s)",
                    logo_result["vendor_name"], logo_result["confidence"], logo_result["method"],
                )

        # ── Stage 4d: Focused LLM fallback for bill_to.name ──────────────
        bill_to_obj = invoice_fields.get("bill_to") or {}
        if not bill_to_obj.get("name"):
            from core.llm_extractor import extract_customer_name
            known_vendor = (invoice_fields.get("vendor") or {}).get("name")
            _t_stage = time.time()
            customer_name = extract_customer_name(full_text, vendor_name=known_vendor)
            print(f"[TIMING] extract_customer_name: {time.time()-_t_stage:.1f}s")
            if customer_name:
                bill_to_obj["name"] = customer_name
                invoice_fields.setdefault("bill_to", bill_to_obj)
                logger.info("[pipeline] Stage 4d - Customer name fallback: bill_to.name='%s'", customer_name)

        # ── Stage 5: Merge table data into line_items if needed ───────────
        t = time.time()
        _t_stage = time.time()
        invoice_fields = self._merge_tables_into_line_items(invoice_fields, tables)
        print(f"[TIMING] _merge_tables_into_line_items: {time.time()-_t_stage:.1f}s")
        logger.info(
            "[pipeline] Stage 5 - Merge: %d line items (%.2fs)",
            len(invoice_fields.get("line_items", [])), time.time() - t,
        )

        # ── Stage 5b: Enhance line items with text-based extraction ────
        t = time.time()
        _t_stage = time.time()
        invoice_fields = self._enhance_line_items_from_text(invoice_fields, full_text)
        print(f"[TIMING] _enhance_line_items_from_text: {time.time()-_t_stage:.1f}s")
        logger.info(
            "[pipeline] Stage 5b - Text enhancement: %d line items (%.2fs)",
            len(invoice_fields.get("line_items", [])), time.time() - t,
        )

        # ── Stage 6: Validate ─────────────────────────────────────────────
        t = time.time()
        from core.validator import validate_invoice
        _t_stage = time.time()
        invoice_fields = validate_invoice(invoice_fields)
        print(f"[TIMING] validate_invoice: {time.time()-_t_stage:.1f}s")
        validation = invoice_fields.get("validation", {})
        if validation.get("passed"):
            status = "PASSED"
        else:
            status = f"WARNINGS ({len(validation.get('warnings', []))})"
        logger.info("[pipeline] Stage 6 - Validation: %s (%.2fs)", status, time.time() - t)

        # ── Add metadata ──────────────────────────────────────────────────
        total_time = time.time() - start_time
        invoice_fields["metadata"] = {
            "source_file": Path(path).name,
            "source_path": path,
            "extraction_time": datetime.now().isoformat(),
            "processing_seconds": round(total_time, 2),
            "pdf_type": pdf_type,
            "page_count": page_count,
            "ocr_engine": OCR_ENGINE if pdf_type != "digital" else "none",
            "tables_found": len(tables),
            "text_length": len(full_text),
            "validation": validation,
        }

        logger.info("[pipeline] ═══ Complete in %.2fs ═══", total_time)
        return invoice_fields

    # ── Private helpers ────────────────────────────────────────────────────

    def _backfill_from_regex(self, fields: dict, text: str) -> dict:
        """Backfill null header fields and correct suspicious LLM amounts using regex."""
        from core.llm_extractor import extract_fields_with_regex

        regex_result = extract_fields_with_regex(text)

        # Backfill null scalar fields
        for key in ("invoice_number", "invoice_date", "due_date",
                     "subtotal", "tax_amount", "total_amount"):
            if fields.get(key) is None and regex_result.get(key) is not None:
                logger.info("[pipeline] Regex backfill: %s = %s", key, regex_result[key])
                fields[key] = regex_result[key]

        # Cross-check numeric fields: if regex found labeled amounts that differ
        # significantly from LLM values, prefer regex (regex matches explicit labels)
        rx_sub = regex_result.get("subtotal")
        rx_tax = regex_result.get("tax_amount")
        rx_tot = regex_result.get("total_amount")
        if rx_sub is not None and rx_tax is not None and rx_tot is not None:
            rx_expected = rx_sub + rx_tax - (regex_result.get("discount") or 0)
            if abs(rx_expected - rx_tot) < rx_tot * 0.05:  # regex is internally consistent
                llm_sub = fields.get("subtotal")
                # Override if LLM values differ from regex by more than 10%
                if llm_sub is not None and abs(llm_sub - rx_sub) > rx_sub * 0.10:
                    logger.info("[pipeline] Regex override: subtotal %s→%s, total %s→%s",
                                llm_sub, rx_sub, fields.get("total_amount"), rx_tot)
                    fields["subtotal"] = rx_sub
                    fields["total_amount"] = rx_tot
                    fields["tax_amount"] = rx_tax

        # Currency override: if regex detects INR signals (₹, GSTIN, Rs), force INR
        # regardless of what the LLM returned — GST invoices are always INR
        rx_currency = regex_result.get("currency")
        if rx_currency == "INR":
            if fields.get("currency") != "INR":
                logger.info("[pipeline] Currency override: %s → INR (GSTIN/₹ detected in text)",
                            fields.get("currency"))
            fields["currency"] = "INR"
        elif fields.get("currency") is None and rx_currency:
            fields["currency"] = rx_currency

        # Backfill null nested fields
        vendor = fields.get("vendor") or {}
        rx_vendor = regex_result.get("vendor") or {}
        for key in ("name", "email", "phone"):
            if not vendor.get(key) and rx_vendor.get(key):
                vendor[key] = rx_vendor[key]
                logger.info("[pipeline] Regex backfill vendor.%s = %s", key, rx_vendor[key])

        bill_to = fields.get("bill_to") or {}
        rx_bill = regex_result.get("bill_to") or {}
        for key in ("name",):
            if not bill_to.get(key) and rx_bill.get(key):
                bill_to[key] = rx_bill[key]
                logger.info("[pipeline] Regex backfill bill_to.%s = %s", key, rx_bill[key])

        return fields

    def _extract_text(self, path: str, pdf_type: str) -> dict:
        """Route to correct text extractor based on file type."""
        try:
            if pdf_type == "digital":
                from core.pdf_extractor import extract_digital_pdf
                return extract_digital_pdf(path)
            elif pdf_type == "scanned":
                from core.ocr_engine import run_ocr_on_pdf
                return run_ocr_on_pdf(path, engine=OCR_ENGINE)
            elif pdf_type == "image":
                from core.ocr_engine import run_ocr_on_image_file
                return run_ocr_on_image_file(path, engine=OCR_ENGINE)
            else:
                logger.warning("[pipeline] Unknown pdf_type: %s", pdf_type)
                return {"full_text": "", "pages": [], "page_count": 0}
        except Exception as e:
            logger.error("[pipeline] Text extraction failed: %s", e)
            return {"full_text": "", "pages": [], "page_count": 0, "error": str(e)}

    def _extract_tables(self, path: str, pdf_type: str) -> list:
        """Extract tables, returning empty list on any failure."""
        try:
            from core.table_extractor import extract_tables
            return extract_tables(path, pdf_type)
        except Exception as e:
            logger.warning("[pipeline] Table extraction failed (non-fatal): %s", e)
            return []

    def _extract_with_llm(self, text: str) -> dict:
        """Call LLM extractor, returning empty invoice on failure."""
        try:
            from core.llm_extractor import extract_invoice_fields
            return extract_invoice_fields(text)
        except ConnectionError as e:
            logger.error("[pipeline] Ollama not running: %s", e)
            raise  # Config error — re-raise
        except Exception as e:
            logger.error("[pipeline] LLM extraction failed: %s", e)
            from core.llm_extractor import _empty_invoice
            return _empty_invoice()

    def _merge_tables_into_line_items(self, invoice: dict, tables: list) -> dict:
        """
        If LLM found no line items but tables were extracted,
        attempt to interpret the first table as line items.
        Falls back to text-based regex extraction if structured tables fail.
        """
        if invoice.get("line_items"):
            return invoice  # LLM already found line items — trust it

        # Try structured table parsing first
        if tables:
            logger.info("[pipeline] LLM found no line items — attempting to parse from extracted tables")
            from core.table_extractor import parse_table_to_line_items
            for table in tables:
                rows = table.get("rows", [])
                if len(rows) < 2:
                    continue
                items = parse_table_to_line_items(rows)
                if items:
                    invoice["line_items"] = items
                    logger.info("[pipeline] Parsed %d line items from structured table", len(items))
                    return invoice

            # Fallback: manual column mapping for tables with proper headers
            for table in tables:
                rows = table.get("rows", [])
                if len(rows) < 2:
                    continue

                header = [str(cell).lower().strip() for cell in rows[0]]
                col_map: Dict[str, int] = {}
                for i, h in enumerate(header):
                    if any(kw in h for kw in ["desc", "item", "service", "product"]):
                        col_map["description"] = i
                    elif any(kw in h for kw in ["qty", "quantity", "units"]):
                        col_map["quantity"] = i
                    elif any(kw in h for kw in ["price", "rate", "unit"]):
                        col_map["unit_price"] = i
                    elif any(kw in h for kw in ["total", "amount", "subtotal"]):
                        col_map["total"] = i

                if "description" not in col_map:
                    continue

                line_items: List[dict] = []
                for row in rows[1:]:
                    if not any(str(cell).strip() for cell in row):
                        continue
                    item: Dict[str, Any] = {}
                    for field, idx in col_map.items():
                        if idx < len(row):
                            val: Any = str(row[idx]).strip()
                            if field in ("quantity", "unit_price", "total"):
                                try:
                                    val = float(re.sub(r"[,$€£¥₹%\s]", "", val))
                                except (ValueError, AttributeError):
                                    val = None
                            item[field] = val
                    if item:
                        line_items.append(item)

                if line_items:
                    invoice["line_items"] = line_items
                    logger.info("[pipeline] Merged %d line items from table", len(line_items))
                    return invoice

        return invoice

    def _enhance_line_items_from_text(self, invoice: dict, full_text: str) -> dict:
        """
        Use text-based regex extraction to fill missing fields or fix corrupted
        values (e.g. Unicode subscript digit corruption) in LLM-extracted line items.
        If LLM found no line items, use text extraction as the source.
        """
        try:
            from core.table_extractor import extract_line_items_from_text
        except ImportError:
            return invoice

        text_items = extract_line_items_from_text(full_text)
        if not text_items:
            return invoice

        llm_items = invoice.get("line_items", [])

        if not llm_items:
            # No LLM items — use text-extracted items directly
            invoice["line_items"] = text_items
            logger.info("[pipeline] Using %d text-extracted line items (LLM found none)", len(text_items))
            return invoice

        # Both LLM and text items exist — enhance LLM items with text data
        # Match by line_number and fix corrupted unit_price values
        text_by_num = {}
        for ti in text_items:
            ln = ti.get("line_number")
            if ln is not None:
                text_by_num[ln] = ti

        # If text regex found more items than LLM, the LLM likely missed rows.
        # Use text items as the base and enhance with LLM data instead.
        if len(text_items) > len(llm_items):
            logger.info(
                "[pipeline] Text regex found %d items vs LLM %d — using text as base",
                len(text_items), len(llm_items),
            )
            # Build LLM lookup by line_number or description similarity
            llm_by_num = {}
            for li in llm_items:
                ln = li.get("line_number")
                if ln is not None:
                    llm_by_num[ln] = li

            merged = []
            for ti in text_items:
                ln = ti.get("line_number")
                llm_item = llm_by_num.get(ln)
                # Start from text item, overlay non-null LLM fields
                item = dict(ti)
                if llm_item:
                    # Prefer LLM description if text description is garbled
                    llm_desc = llm_item.get("description") or ""
                    text_desc = item.get("description") or ""
                    if llm_desc and len(llm_desc) >= len(text_desc):
                        item["description"] = llm_desc
                    # Copy LLM-only fields (unit, tax_rate) if text doesn't have them
                    for key in ("unit", "tax_rate", "quantity"):
                        llm_val = llm_item.get(key)
                        text_val = item.get(key)
                        if llm_val is not None and text_val is None:
                            item[key] = llm_val
                merged.append(item)
            invoice["line_items"] = merged
            return invoice

        for i, item in enumerate(llm_items):
            ln = item.get("line_number", i + 1)
            text_item = text_by_num.get(ln)
            if not text_item:
                continue

            # Prefer text-extracted quantity/unit_price when LLM values
            # don't match the math (qty × unit_price ≈ line_total)
            llm_qty = item.get("quantity")
            llm_price = item.get("unit_price")
            llm_total = item.get("total") or item.get("line_total")
            text_qty = text_item.get("quantity")
            text_price = text_item.get("unit_price")
            text_total = text_item.get("line_total")

            # Use text total if available (regex is more reliable for amounts)
            total = text_total or llm_total

            # Decide which quantity to trust: check if text qty makes the math work
            qty = llm_qty
            if text_qty and total and text_qty > 0:
                text_expected = text_qty * (text_price or 0)
                llm_expected = (llm_qty or 0) * (llm_price or 0)
                # If text qty × text price ≈ total, trust text qty
                if abs(text_expected - total) < 1.0:
                    qty = text_qty
                elif llm_qty is None or (llm_qty and abs(llm_expected - total) > 1.0):
                    # LLM qty doesn't work either — use text qty
                    qty = text_qty

            if qty != llm_qty:
                item["quantity"] = qty
                logger.debug(
                    "[pipeline] Corrected quantity for line %d: %s → %s",
                    ln, llm_qty, qty,
                )
            elif llm_qty is None and text_qty:
                item["quantity"] = text_qty
                qty = text_qty
                logger.debug(
                    "[pipeline] Filled quantity for line %d: %s", ln, text_qty,
                )

            # Fix unit_price using the corrected quantity
            # Use tax_rate to strip GST before dividing (avoids 18%-inflated prices)
            if total and qty and qty > 0:
                tax_rate = item.get("tax_rate")
                if tax_rate and tax_rate > 0:
                    taxable = total / (1 + tax_rate / 100.0)
                else:
                    taxable = total
                expected_price = round(taxable / qty, 2)
                current_price = item.get("unit_price")
                if current_price is None or abs(qty * current_price - total) > 0.50:
                    item["unit_price"] = expected_price
                    logger.debug(
                        "[pipeline] Corrected unit_price for line %d: %s → %s",
                        ln, current_price, expected_price,
                    )

            # Fill or correct line_total from text extraction
            if text_total and (not llm_total or llm_total != text_total):
                if "total" in item:
                    item["total"] = text_total
                else:
                    item["line_total"] = text_total
                if llm_total and llm_total != text_total:
                    logger.debug(
                        "[pipeline] Corrected total for line %d: %s → %s",
                        ln, llm_total, text_total,
                    )

            # Fill missing hsn_sac from text
            if not item.get("hsn_sac") and text_item.get("hsn_sac"):
                item["hsn_sac"] = text_item["hsn_sac"]

            # Fill or correct tax_rate from text
            # LLM sometimes extracts component rates (CGST/SGST) instead of total GST
            llm_tax = item.get("tax_rate")
            text_tax = text_item.get("tax_rate")
            if text_tax is not None:
                if llm_tax is None:
                    # Fill missing tax_rate
                    item["tax_rate"] = text_tax
                    logger.debug(
                        "[pipeline] Filled tax_rate for line %d: %s",
                        ln, text_tax,
                    )
                elif llm_tax > 0 and text_tax > 0 and abs(llm_tax * 2 - text_tax) < 0.5:
                    # LLM likely extracted CGST/SGST (half rate) instead of total GST
                    item["tax_rate"] = text_tax
                    logger.debug(
                        "[pipeline] Corrected tax_rate for line %d: %s → %s (was component rate)",
                        ln, llm_tax, text_tax,
                    )

            # Enhance description with sub-description if text has it
            text_desc = text_item.get("description", "")
            llm_desc = item.get("description", "")
            if text_desc and " - " in text_desc and llm_desc and " - " not in llm_desc:
                item["description"] = text_desc

        return invoice

    # ── Batch & save helpers ──────────────────────────────────────────────

    def run_batch(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        """
        Run extraction on multiple files.

        Args:
            file_paths: List of file paths.

        Returns:
            List of extraction results.
        """
        results = []
        for i, fpath in enumerate(file_paths):
            logger.info("Batch progress: %d/%d", i + 1, len(file_paths))
            try:
                result = self.run(fpath)
                result["metadata"]["batch_index"] = i
                results.append(result)
            except Exception as e:
                logger.error("Failed to process '%s': %s", fpath, e)
                results.append({
                    "error": str(e),
                    "metadata": {
                        "source_file": os.path.basename(str(fpath)),
                        "source_path": str(fpath),
                        "batch_index": i,
                        "status": "failed",
                    },
                })
        return results

    def save_result(self, result: Dict[str, Any], output_path: Optional[str] = None) -> str:
        """
        Save extraction result as JSON.

        Args:
            result: Extraction result dictionary.
            output_path: Optional output file path. If None, auto-generates.

        Returns:
            Path to the saved JSON file.
        """
        if output_path is None:
            source = result.get("metadata", {}).get("source_file", "unknown")
            name = Path(source).stem
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_path = str(OUTPUTS_DIR / f"{name}_{timestamp}.json")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)

        logger.info("Result saved to: %s", output_path)
        return output_path


def discover_files(directory: str) -> List[str]:
    """
    Recursively discover all supported invoice files in a directory.

    Args:
        directory: Path to the directory to scan.

    Returns:
        Sorted list of absolute file paths.
    """
    files = []
    directory = Path(directory)
    if not directory.exists():
        logger.warning("Directory not found: %s", directory)
        return files

    for f in sorted(directory.rglob("*")):
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS:
            files.append(str(f.resolve()))

    logger.info("Discovered %d invoice files in '%s'", len(files), directory)
    return files
