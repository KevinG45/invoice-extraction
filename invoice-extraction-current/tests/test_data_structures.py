"""
Test data structures: FieldValue, LineItemOutput, ExtractionOutput
"""
import json
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models.base_extractor import (
    FieldValue, LineItemOutput, ExtractionOutput,
)


class TestFieldValue:
    def test_default_creation(self):
        fv = FieldValue()
        assert fv.value is None
        assert fv.confidence == 0.0
        assert fv.uncertain is False
        assert fv.verified is False

    def test_creation_with_values(self):
        fv = FieldValue(value="INV-001", confidence=95.0, source_model="sarvam")
        assert fv.value == "INV-001"
        assert fv.confidence == 95.0
        assert fv.source_model == "sarvam"

    def test_mutable_fields(self):
        fv = FieldValue(value="test", confidence=80.0)
        fv.uncertain = True
        fv.verified = True
        fv.validation_method = "qae_passed"
        assert fv.uncertain is True
        assert fv.verified is True
        assert fv.validation_method == "qae_passed"


class TestLineItemOutput:
    def test_default_creation(self):
        item = LineItemOutput()
        assert item.line_number == 0
        assert item.description.value is None
        assert item.quantity.value is None
        assert item.unit_price.value is None
        assert item.line_total.value is None

    def test_from_dict(self):
        data = {
            "line_number": 1,
            "description": "Widget A",
            "quantity": 5,
            "unit_price": 10.00,
            "line_total": 50.00,
        }
        item = LineItemOutput.from_dict(data, confidence=90.0)
        assert item.line_number == 1
        assert item.description.value == "Widget A"
        assert item.quantity.value == 5
        assert item.unit_price.value == 10.00
        assert item.line_total.value == 50.00
        assert item.description.confidence == 90.0


class TestExtractionOutput:
    def test_default_creation(self):
        output = ExtractionOutput()
        assert output.invoice_number.value is None
        assert output.total_amount.value is None
        assert len(output.line_items) == 0

    def test_get_field(self):
        output = ExtractionOutput()
        output.invoice_number.value = "INV-001"
        fv = output.get_field("invoice_number")
        assert fv.value == "INV-001"

    def test_get_field_invalid(self):
        output = ExtractionOutput()
        fv = output.get_field("nonexistent_field")
        assert fv is None

    def test_calculate_confidence(self):
        output = ExtractionOutput()
        output.invoice_number = FieldValue(value="INV-001", confidence=90.0)
        output.total_amount = FieldValue(value=100.00, confidence=80.0)
        conf = output.calculate_overall_confidence()
        assert conf == pytest.approx(85.0, abs=0.1)

    def test_to_dict(self):
        output = ExtractionOutput()
        output.invoice_number = FieldValue(value="INV-001", confidence=95.0)
        output.vendor_name = FieldValue(value="Acme Corp", confidence=90.0)
        output.total_amount = FieldValue(value=500.00, confidence=88.0)
        output.source_file = "test.pdf"

        d = output.to_dict()
        assert d["headers"]["invoice_number"]["value"] == "INV-001"
        assert d["headers"]["vendor_name"]["value"] == "Acme Corp"
        assert d["source_file"] == "test.pdf"

    def test_to_json(self):
        output = ExtractionOutput()
        output.invoice_number = FieldValue(value="INV-001", confidence=95.0)
        j = output.to_json()
        parsed = json.loads(j)
        assert parsed["headers"]["invoice_number"]["value"] == "INV-001"

    def test_to_flat_dict(self):
        output = ExtractionOutput()
        output.invoice_number = FieldValue(value="INV-001", confidence=95.0)
        output.total_amount = FieldValue(value=100.0, confidence=85.0)
        flat = output.to_flat_dict()
        assert flat["invoice_number"] == "INV-001"
        assert flat["total_amount"] == 100.0

    def test_from_raw_json_basic(self):
        raw = {
            "invoice_number": "INV-123",
            "vendor_name": "Test Vendor",
            "total_amount": "1500.00",
            "line_items": [
                {
                    "description": "Service A",
                    "quantity": 2,
                    "unit_price": 750.00,
                    "line_total": 1500.00,
                }
            ],
        }
        output = ExtractionOutput.from_raw_json(raw, confidence=85.0)
        assert output.invoice_number.value == "INV-123"
        assert output.vendor_name.value == "Test Vendor"
        assert len(output.line_items) == 1
        assert output.line_items[0].description.value == "Service A"

    def test_header_fields_constant(self):
        assert "invoice_number" in ExtractionOutput.HEADER_FIELDS
        assert "total_amount" in ExtractionOutput.HEADER_FIELDS
        assert len(ExtractionOutput.HEADER_FIELDS) == 14
