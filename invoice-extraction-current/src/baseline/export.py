"""
Export Module for Baseline Invoice Extraction.

Exports extraction results in three formats:

  1. JSON  - Machine-readable, preserves all metadata and confidence scores
  2. EXCEL - Human-readable, two sheets: "Headers" and "Line Items"
  3. CSV   - Flat format, easy to import into other tools

OUTPUT DIRECTORY STRUCTURE:
  outputs/
    extractions/
      baseline_YYYYMMDD_HHMMSS.json     # All invoices, full metadata
      baseline_YYYYMMDD_HHMMSS.xlsx     # Excel workbook
      baseline_headers_YYYYMMDD.csv     # Header fields (one row per invoice)
      baseline_items_YYYYMMDD.csv       # Line items (one row per item)

Author: ML Engineering Team
Date: 2026-02-19
Version: 3.0.0 (Baseline)
"""

import csv
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.baseline.result import InvoiceResult, HEADER_FIELD_NAMES

logger = logging.getLogger("invoice_extraction.baseline.export")


class ExportManager:
    """
    Exports extraction results to JSON, Excel, and CSV.

    Usage:
        manager = ExportManager(output_dir="outputs/extractions")
        manager.export_all(results, formats=["json", "excel", "csv"])
    """

    def __init__(self, output_dir: str = "outputs/extractions"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        # Timestamp for file naming
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # =========================================================================
    # MAIN EXPORT METHOD
    # =========================================================================

    def export_all(
        self,
        results: List[InvoiceResult],
        formats: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """
        Export results in the specified formats.

        Args:
            results: List of InvoiceResult objects to export.
            formats: List of format strings: "json", "excel", "csv".
                     Defaults to all three.

        Returns:
            Dictionary mapping format name to output file path.
        """
        if formats is None:
            formats = ["json", "excel", "csv"]

        output_files = {}

        for fmt in formats:
            try:
                if fmt == "json":
                    path = self._export_json(results)
                    output_files["json"] = path
                elif fmt == "excel":
                    path = self._export_excel(results)
                    output_files["excel"] = path
                elif fmt == "csv":
                    paths = self._export_csv(results)
                    output_files["csv_headers"] = paths[0]
                    output_files["csv_items"] = paths[1]
                else:
                    logger.warning(f"Unknown export format: {fmt}")
            except Exception as e:
                logger.error(f"Export failed for {fmt}: {e}")

        return output_files

    # =========================================================================
    # JSON EXPORT
    # =========================================================================

    def _export_json(self, results: List[InvoiceResult]) -> str:
        """
        Export results to JSON with full metadata.

        JSON structure:
        {
          "export_timestamp": "2026-02-19T14:30:00",
          "total_invoices": 96,
          "pipeline": "baseline_v3.0",
          "invoices": [
            {
              "source_file": "GST001.pdf",
              "headers": {
                "invoice_number": {
                  "value": "INV-001",
                  "confidence": 92.0,
                  "source": "regex"
                }, ...
              },
              "line_items": [
                {
                  "line_number": 1,
                  "description": "Widget A",
                  "quantity": 10, ...
                }, ...
              ],
              "metadata": { ... },
              "validation": [ ... ]
            }, ...
          ]
        }
        """
        filename = f"baseline_{self.timestamp}.json"
        filepath = os.path.join(self.output_dir, filename)

        export_data = {
            "export_timestamp": datetime.now().isoformat(),
            "total_invoices": len(results),
            "pipeline": "baseline_v3.0",
            "extraction_summary": self._generate_summary(results),
            "invoices": [],
        }

        for result in results:
            invoice_data = {
                "source_file": result.metadata.source_file,
                "document_type": result.metadata.document_type,
                "headers": {},
                "line_items": [],
                "metadata": {
                    "page_count": result.metadata.page_count,
                    "text_extraction_method": result.metadata.text_extraction_method,
                    "text_extraction_time_ms": result.metadata.text_extraction_time_ms,
                    "field_extraction_time_ms": result.metadata.field_extraction_time_ms,
                    "total_extraction_time_ms": result.metadata.total_extraction_time_ms,
                    "average_text_confidence": result.metadata.average_text_confidence,
                },
                "validation": result.validation_results or [],
            }

            # Headers
            for field_name in HEADER_FIELD_NAMES:
                header = result.get_header(field_name)
                if header:
                    invoice_data["headers"][field_name] = {
                        "value": header.value,
                        "confidence": round(header.confidence, 1),
                        "source": header.source,
                        "uncertain": header.uncertain,
                    }

            # Line items
            for item in result.line_items:
                item_data = {
                    "line_number": item.line_number,
                    "description": item.description,
                    "item_code": item.item_code,
                    "hsn_sac": item.hsn_sac,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "discount": item.discount,
                    "tax_rate": item.tax_rate,
                    "tax_amount": item.tax_amount,
                    "line_total": item.line_total,
                    "confidence": round(item.confidence, 1),
                }
                invoice_data["line_items"].append(item_data)

            export_data["invoices"].append(invoice_data)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        logger.info(f"JSON exported: {filepath}")
        return filepath

    # =========================================================================
    # EXCEL EXPORT
    # =========================================================================

    def _export_excel(self, results: List[InvoiceResult]) -> str:
        """
        Export to Excel with two sheets:
        - "Headers": One row per invoice, columns for each field
        - "Line Items": One row per line item, with invoice reference
        """
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        except ImportError:
            logger.error("openpyxl not installed. Install: pip install openpyxl")
            raise

        filename = f"baseline_{self.timestamp}.xlsx"
        filepath = os.path.join(self.output_dir, filename)

        wb = openpyxl.Workbook()

        # =====================================================================
        # Sheet 1: Headers
        # =====================================================================
        ws_headers = wb.active
        ws_headers.title = "Headers"

        # Style definitions
        header_font = Font(bold=True, color="FFFFFF", size=11)
        header_fill = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
        thin_border = Border(
            left=Side(style="thin"),
            right=Side(style="thin"),
            top=Side(style="thin"),
            bottom=Side(style="thin"),
        )

        # Write header row
        header_columns = ["Source File", "Document Type"] + [
            name.replace("_", " ").title() for name in HEADER_FIELD_NAMES
        ] + ["Fields Extracted", "Avg Confidence"]

        for col_idx, col_name in enumerate(header_columns, 1):
            cell = ws_headers.cell(row=1, column=col_idx, value=col_name)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")
            cell.border = thin_border

        # Write data rows
        for row_idx, result in enumerate(results, 2):
            ws_headers.cell(row=row_idx, column=1, value=result.metadata.source_file)
            ws_headers.cell(row=row_idx, column=2, value=result.metadata.document_type)

            confidences = []
            for field_idx, field_name in enumerate(HEADER_FIELD_NAMES):
                header = result.get_header(field_name)
                col = field_idx + 3
                if header and header.value:
                    ws_headers.cell(row=row_idx, column=col, value=header.value)
                    confidences.append(header.confidence)
                else:
                    ws_headers.cell(row=row_idx, column=col, value="")

            # Statistics columns
            fields_found = sum(
                1 for name in HEADER_FIELD_NAMES
                if result.get_header(name) and result.get_header(name).value
            )
            ws_headers.cell(
                row=row_idx,
                column=len(HEADER_FIELD_NAMES) + 3,
                value=f"{fields_found}/{len(HEADER_FIELD_NAMES)}",
            )
            avg_conf = sum(confidences) / len(confidences) if confidences else 0
            ws_headers.cell(
                row=row_idx,
                column=len(HEADER_FIELD_NAMES) + 4,
                value=round(avg_conf, 1),
            )

            # Apply border to all cells
            for col in range(1, len(header_columns) + 1):
                ws_headers.cell(row=row_idx, column=col).border = thin_border

        # Auto-size columns
        for col in ws_headers.columns:
            max_length = 0
            column_letter = col[0].column_letter
            for cell in col:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            adjusted_width = min(max_length + 2, 40)
            ws_headers.column_dimensions[column_letter].width = adjusted_width

        # =====================================================================
        # Sheet 2: Line Items
        # =====================================================================
        ws_items = wb.create_sheet("Line Items")

        item_columns = [
            "Source File", "Line #", "Item Code", "Description", "HSN/SAC",
            "Quantity", "Unit Price", "Discount", "Tax Rate", "Tax Amount",
            "Line Total", "Confidence",
        ]

        for col_idx, col_name in enumerate(item_columns, 1):
            cell = ws_items.cell(row=1, column=col_idx, value=col_name)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")
            cell.border = thin_border

        row_idx = 2
        for result in results:
            for item in result.line_items:
                ws_items.cell(row=row_idx, column=1, value=result.metadata.source_file)
                ws_items.cell(row=row_idx, column=2, value=item.line_number)
                ws_items.cell(row=row_idx, column=3, value=item.item_code or "")
                ws_items.cell(row=row_idx, column=4, value=item.description or "")
                ws_items.cell(row=row_idx, column=5, value=item.hsn_sac or "")
                ws_items.cell(row=row_idx, column=6, value=item.quantity)
                ws_items.cell(row=row_idx, column=7, value=item.unit_price)
                ws_items.cell(row=row_idx, column=8, value=item.discount)
                ws_items.cell(row=row_idx, column=9, value=item.tax_rate)
                ws_items.cell(row=row_idx, column=10, value=item.tax_amount)
                ws_items.cell(row=row_idx, column=11, value=item.line_total)
                ws_items.cell(row=row_idx, column=12, value=round(item.confidence, 1))

                for col in range(1, len(item_columns) + 1):
                    ws_items.cell(row=row_idx, column=col).border = thin_border

                row_idx += 1

        # Auto-size item columns
        for col in ws_items.columns:
            max_length = 0
            column_letter = col[0].column_letter
            for cell in col:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            adjusted_width = min(max_length + 2, 50)
            ws_items.column_dimensions[column_letter].width = adjusted_width

        wb.save(filepath)
        logger.info(f"Excel exported: {filepath}")
        return filepath

    # =========================================================================
    # CSV EXPORT
    # =========================================================================

    def _export_csv(self, results: List[InvoiceResult]) -> tuple:
        """
        Export to CSV (two files: headers and line items).
        """
        # File 1: Headers
        headers_filename = f"baseline_headers_{self.timestamp}.csv"
        headers_filepath = os.path.join(self.output_dir, headers_filename)

        with open(headers_filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # Header row
            columns = ["source_file", "document_type"] + list(HEADER_FIELD_NAMES)
            writer.writerow(columns)

            # Data rows
            for result in results:
                row = [result.metadata.source_file, result.metadata.document_type]
                for field_name in HEADER_FIELD_NAMES:
                    header = result.get_header(field_name)
                    row.append(header.value if header and header.value else "")
                writer.writerow(row)

        logger.info(f"CSV headers exported: {headers_filepath}")

        # File 2: Line Items
        items_filename = f"baseline_items_{self.timestamp}.csv"
        items_filepath = os.path.join(self.output_dir, items_filename)

        with open(items_filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # Header row
            writer.writerow([
                "source_file", "line_number", "item_code", "description",
                "hsn_sac", "quantity", "unit_price", "discount",
                "tax_rate", "tax_amount", "line_total", "confidence",
            ])

            # Data rows
            for result in results:
                for item in result.line_items:
                    writer.writerow([
                        result.metadata.source_file,
                        item.line_number,
                        item.item_code or "",
                        item.description or "",
                        item.hsn_sac or "",
                        item.quantity if item.quantity is not None else "",
                        item.unit_price if item.unit_price is not None else "",
                        item.discount if item.discount is not None else "",
                        item.tax_rate if item.tax_rate is not None else "",
                        item.tax_amount if item.tax_amount is not None else "",
                        item.line_total if item.line_total is not None else "",
                        round(item.confidence, 1),
                    ])

        logger.info(f"CSV items exported: {items_filepath}")

        return headers_filepath, items_filepath

    # =========================================================================
    # SUMMARY GENERATION
    # =========================================================================

    def _generate_summary(self, results: List[InvoiceResult]) -> Dict[str, Any]:
        """
        Generate extraction summary statistics for the export.
        """
        total_invoices = len(results)
        total_items = sum(len(r.line_items) for r in results)

        # Field extraction rates
        field_rates = {}
        for field_name in HEADER_FIELD_NAMES:
            extracted = sum(
                1 for r in results
                if r.get_header(field_name) and r.get_header(field_name).value
            )
            field_rates[field_name] = {
                "extracted": extracted,
                "total": total_invoices,
                "rate": round(extracted / total_invoices * 100, 1) if total_invoices else 0,
            }

        # Average confidence
        all_confidences = []
        for result in results:
            for field_name in HEADER_FIELD_NAMES:
                header = result.get_header(field_name)
                if header and header.value:
                    all_confidences.append(header.confidence)

        # Validation pass rate
        all_validations = [v for r in results for v in (r.validation_results or [])]
        passes = sum(1 for v in all_validations if v.get("status") == "PASS")
        fails = sum(1 for v in all_validations if v.get("status") == "FAIL")

        return {
            "total_invoices": total_invoices,
            "total_line_items": total_items,
            "avg_items_per_invoice": round(total_items / total_invoices, 1) if total_invoices else 0,
            "avg_confidence": round(
                sum(all_confidences) / len(all_confidences), 1
            ) if all_confidences else 0,
            "field_extraction_rates": field_rates,
            "validation_passes": passes,
            "validation_fails": fails,
            "validation_pass_rate": round(
                passes / (passes + fails) * 100, 1
            ) if (passes + fails) else 0,
        }
