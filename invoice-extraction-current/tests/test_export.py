"""
Test export handlers (JSON, Excel, CSV).
"""
import json
import os
import tempfile
import pytest
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models.base_extractor import (
    FieldValue, LineItemOutput, ExtractionOutput,
)
from src.export.export_handlers_2026 import (
    JSONExporter2026, ExcelExporter2026, CSVExporter2026, ExportManager2026,
)


def _make_extraction() -> ExtractionOutput:
    e = ExtractionOutput()
    e.invoice_number = FieldValue(value="INV-001", confidence=95.0)
    e.invoice_date = FieldValue(value="2026-01-15", confidence=92.0)
    e.vendor_name = FieldValue(value="Acme Corp", confidence=93.0)
    e.total_amount = FieldValue(value=150.00, confidence=90.0)
    e.subtotal = FieldValue(value=130.00, confidence=88.0)
    e.tax_amount = FieldValue(value=15.00, confidence=85.0)
    e.shipping = FieldValue(value=5.00, confidence=82.0)
    e.currency = FieldValue(value="USD", confidence=95.0)

    item = LineItemOutput.from_dict({
        "line_number": 1,
        "description": "Widget",
        "quantity": 5,
        "unit_price": 26.00,
        "line_total": 130.00,
    }, confidence=90.0)
    e.line_items = [item]
    e.source_file = "test.pdf"
    e.model_used = "sarvam_vision"
    return e


class TestJSONExporter:
    def test_export_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.json")
            exporter = JSONExporter2026()
            result = exporter.export([_make_extraction()], path)
            assert os.path.exists(result)

    def test_export_valid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.json")
            exporter = JSONExporter2026()
            exporter.export([_make_extraction()], path)

            with open(path, "r") as f:
                data = json.load(f)

            assert data["metadata"]["total_invoices"] == 1
            assert len(data["invoices"]) == 1
            assert data["invoices"][0]["headers"]["invoice_number"]["value"] == "INV-001"
            assert len(data["invoices"][0]["line_items"]) == 1

    def test_export_multiple(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.json")
            exporter = JSONExporter2026()
            exporter.export([_make_extraction(), _make_extraction()], path)

            with open(path, "r") as f:
                data = json.load(f)
            assert data["metadata"]["total_invoices"] == 2

    def test_summary_statistics(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.json")
            exporter = JSONExporter2026()
            exporter.export([_make_extraction()], path)

            with open(path, "r") as f:
                data = json.load(f)
            assert "summary" in data
            assert data["summary"]["total_invoices"] == 1
            assert data["summary"]["total_line_items"] == 1


class TestExcelExporter:
    def test_export_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.xlsx")
            exporter = ExcelExporter2026()
            result = exporter.export([_make_extraction()], path)
            assert os.path.exists(result)

    def test_export_has_all_sheets(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.xlsx")
            exporter = ExcelExporter2026()
            exporter.export([_make_extraction()], path)

            import openpyxl
            wb = openpyxl.load_workbook(path)
            sheet_names = wb.sheetnames
            assert "Headers" in sheet_names
            assert "Line Items" in sheet_names
            assert "Validation Report" in sheet_names
            assert "Confidence Scores" in sheet_names
            assert "Model Metadata" in sheet_names
            assert len(sheet_names) == 5
            wb.close()


class TestCSVExporter:
    def test_export_headers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "headers.csv")
            exporter = CSVExporter2026()
            result = exporter.export_headers([_make_extraction()], path)
            assert os.path.exists(result)

            import csv
            with open(result, "r") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            assert len(rows) == 1
            assert rows[0]["invoice_number"] == "INV-001"

    def test_export_line_items(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "items.csv")
            exporter = CSVExporter2026()
            result = exporter.export_line_items([_make_extraction()], path)
            assert os.path.exists(result)


class TestExportManager:
    def test_export_all_formats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                "output": {
                    "formats": ["json", "excel", "csv"],
                    "output_dir": tmpdir,
                },
            }
            manager = ExportManager2026(config)
            results = manager.export_all([_make_extraction()])
            assert "json" in results
            assert "excel" in results
            assert "csv_headers" in results
            assert "csv_line_items" in results
