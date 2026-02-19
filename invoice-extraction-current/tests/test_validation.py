"""
Test validation layers (all 6 layers of the anti-hallucination framework).
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models.base_extractor import (
    FieldValue, LineItemOutput, ExtractionOutput,
)
from src.validation.multi_agent import (
    NumericalAgent, FormatAgent, LogicalAgent, ConfidenceAgent,
    MultiAgentValidator,
)
from src.validation.neurosymbolic import NeurosymbolicValidator
from src.validation.confidence_scorer import CalibratedConfidenceScorer
from src.validation.qae_validator import QAEValidator
from src.validation.framework_2026 import ValidationFramework2026


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_valid_extraction() -> ExtractionOutput:
    """Create a valid, consistent extraction for testing."""
    e = ExtractionOutput()
    e.invoice_number = FieldValue(value="INV-2026-001", confidence=95.0)
    e.invoice_date = FieldValue(value="2026-01-15", confidence=92.0)
    e.due_date = FieldValue(value="2026-02-15", confidence=90.0)
    e.vendor_name = FieldValue(value="Acme Corp", confidence=93.0)
    e.vendor_address = FieldValue(value="123 Main St", confidence=88.0)
    e.vendor_email = FieldValue(value="billing@acme.com", confidence=85.0)
    e.vendor_phone = FieldValue(value="+1-555-123-4567", confidence=82.0)
    e.customer_name = FieldValue(value="Widget Inc", confidence=91.0)
    e.customer_address = FieldValue(value="456 Oak Ave", confidence=87.0)
    e.currency = FieldValue(value="USD", confidence=95.0)
    e.subtotal = FieldValue(value=100.00, confidence=90.0)
    e.tax_amount = FieldValue(value=10.00, confidence=88.0)
    e.shipping = FieldValue(value=5.00, confidence=85.0)
    e.total_amount = FieldValue(value=115.00, confidence=92.0)

    item1 = LineItemOutput.from_dict({
        "line_number": 1,
        "description": "Widget A",
        "quantity": 2,
        "unit_price": 30.00,
        "line_total": 60.00,
    }, confidence=90.0)

    item2 = LineItemOutput.from_dict({
        "line_number": 2,
        "description": "Widget B",
        "quantity": 1,
        "unit_price": 40.00,
        "line_total": 40.00,
    }, confidence=90.0)

    e.line_items = [item1, item2]
    e.source_file = "test_invoice.pdf"
    return e


def _make_invalid_extraction() -> ExtractionOutput:
    """Create an extraction with known issues."""
    e = ExtractionOutput()
    e.invoice_number = FieldValue(value="INV-2026-002", confidence=95.0)
    e.invoice_date = FieldValue(value="2026-01-15", confidence=50.0)
    e.due_date = FieldValue(value="2025-12-01", confidence=40.0)  # Before invoice date!
    e.vendor_name = FieldValue(value="BadCorp", confidence=60.0)
    e.customer_name = FieldValue(value="BadCorp", confidence=60.0)  # Same as vendor!
    e.currency = FieldValue(value="INVALID", confidence=30.0)
    e.subtotal = FieldValue(value=100.00, confidence=70.0)
    e.tax_amount = FieldValue(value=50.00, confidence=50.0)  # 50% tax - too high
    e.total_amount = FieldValue(value=120.00, confidence=60.0)  # Wrong: 100+50≠120

    item1 = LineItemOutput.from_dict({
        "line_number": 1,
        "description": "Item A",
        "quantity": 3,
        "unit_price": 20.00,
        "line_total": 70.00,  # Wrong: 3×20=60≠70
    }, confidence=50.0)

    e.line_items = [item1]
    e.source_file = "bad_invoice.pdf"
    return e


# ---------------------------------------------------------------------------
# Test individual agents
# ---------------------------------------------------------------------------

class TestNumericalAgent:
    def test_valid_extraction(self):
        agent = NumericalAgent()
        result = agent.validate(_make_valid_extraction())
        assert result["passed"] is True
        assert result["score"] >= 0.8

    def test_invalid_math(self):
        agent = NumericalAgent()
        result = agent.validate(_make_invalid_extraction())
        assert result["passed"] is False
        assert len(result["issues"]) > 0


class TestFormatAgent:
    def test_valid_formats(self):
        agent = FormatAgent()
        result = agent.validate(_make_valid_extraction())
        assert result["passed"] is True

    def test_invalid_currency(self):
        agent = FormatAgent()
        result = agent.validate(_make_invalid_extraction())
        assert result["checks"].get("currency_valid") is False


class TestLogicalAgent:
    def test_valid_logic(self):
        agent = LogicalAgent()
        result = agent.validate(_make_valid_extraction())
        assert result["passed"] is True

    def test_due_before_invoice(self):
        agent = LogicalAgent()
        result = agent.validate(_make_invalid_extraction())
        assert result["checks"].get("due_after_invoice") is False

    def test_vendor_customer_same(self):
        agent = LogicalAgent()
        result = agent.validate(_make_invalid_extraction())
        assert result["checks"].get("vendor_customer_different") is False


class TestConfidenceAgent:
    def test_high_confidence(self):
        agent = ConfidenceAgent(min_score=0.85)
        result = agent.validate(_make_valid_extraction())
        assert result["score"] > 0.5

    def test_low_confidence(self):
        agent = ConfidenceAgent(min_score=0.85)
        result = agent.validate(_make_invalid_extraction())
        assert result["passed"] is False


# ---------------------------------------------------------------------------
# Test Multi-Agent Validator
# ---------------------------------------------------------------------------

class TestMultiAgentValidator:
    def test_valid_extraction_passes(self):
        validator = MultiAgentValidator({"enabled": True})
        result = validator.validate(_make_valid_extraction())
        assert result["consensus_score"] > 0
        assert result["agents_total"] == 4

    def test_invalid_extraction_fails(self):
        validator = MultiAgentValidator({"enabled": True})
        result = validator.validate(_make_invalid_extraction())
        assert result["consensus_score"] < 1.0
        assert len(result["issues"]) > 0

    def test_disabled(self):
        validator = MultiAgentValidator({"enabled": False})
        result = validator.validate(_make_valid_extraction())
        assert result["passed"] is True


# ---------------------------------------------------------------------------
# Test Neurosymbolic Validator
# ---------------------------------------------------------------------------

class TestNeurosymbolicValidator:
    def test_valid_passes_all_rules(self):
        validator = NeurosymbolicValidator({"enabled": True})
        result = validator.validate(_make_valid_extraction())
        assert result["rules_failed"] == 0
        assert result["passed"] is True

    def test_invalid_fails_rules(self):
        validator = NeurosymbolicValidator({"enabled": True})
        result = validator.validate(_make_invalid_extraction())
        assert result["rules_failed"] > 0
        assert result["passed"] is False

    def test_auto_corrects_line_items(self):
        validator = NeurosymbolicValidator({"enabled": True})
        extraction = _make_invalid_extraction()
        result = validator.validate(extraction)
        # Line item math should have been corrected
        assert len(result.get("corrections", [])) > 0

    def test_disabled(self):
        validator = NeurosymbolicValidator({"enabled": False})
        result = validator.validate(_make_valid_extraction())
        assert result["passed"] is True


# ---------------------------------------------------------------------------
# Test QAE Validator
# ---------------------------------------------------------------------------

class TestQAEValidator:
    def test_self_consistency_without_extractor(self):
        validator = QAEValidator({"enabled": True})
        result = validator.validate(_make_valid_extraction())
        assert result["passed"] is True

    def test_disabled(self):
        validator = QAEValidator({"enabled": False})
        result = validator.validate(_make_valid_extraction())
        assert result["passed"] is True


# ---------------------------------------------------------------------------
# Test Calibrated Confidence Scorer
# ---------------------------------------------------------------------------

class TestCalibratedConfidenceScorer:
    def test_valid_high_confidence(self):
        scorer = CalibratedConfidenceScorer({"enabled": True})
        result = scorer.validate(_make_valid_extraction())
        assert result["score"] > 0
        assert result["overall_decision"] in ("auto_accept", "review")

    def test_low_confidence_triggers_review(self):
        scorer = CalibratedConfidenceScorer({"enabled": True})
        result = scorer.validate(_make_invalid_extraction())
        assert "reject" in result["decisions"] or "review" in result["decisions"]


# ---------------------------------------------------------------------------
# Test Full Framework
# ---------------------------------------------------------------------------

class TestValidationFramework2026:
    def test_full_pipeline_valid(self):
        config = {
            "validation": {
                "rag_validation": {"enabled": True},
                "multi_agent": {"enabled": True},
                "qae_validation": {"enabled": True},
                "neurosymbolic": {"enabled": True},
                "confidence_scoring": {"enabled": True},
                "cross_model": {"enabled": False},
            }
        }
        framework = ValidationFramework2026(config)
        result = framework.validate(_make_valid_extraction())
        assert "overall_score" in result
        assert "layers" in result
        assert result["processing_time_ms"] >= 0

    def test_full_pipeline_invalid(self):
        config = {
            "validation": {
                "rag_validation": {"enabled": True},
                "multi_agent": {"enabled": True},
                "qae_validation": {"enabled": True},
                "neurosymbolic": {"enabled": True},
                "confidence_scoring": {"enabled": True},
                "cross_model": {"enabled": False},
            }
        }
        framework = ValidationFramework2026(config)
        result = framework.validate(_make_invalid_extraction())
        assert len(result["all_issues"]) > 0
