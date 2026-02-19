"""
Layer 5: Calibrated Confidence Scorer

Dynamically scores confidence for each field based on:
- Model raw confidence
- Validation results from layers 1-4
- Field criticality (critical / important / normal)
- Historical accuracy patterns

Produces three decision levels:
- auto_accept (≥ threshold_high)
- review (between thresholds)
- reject (< threshold_low)

Author: ML Engineering Team
Version: 2.0.0
"""

import logging
from typing import Any, Dict, List, Optional

from src.models.base_extractor import ExtractionOutput, FieldValue

logger = logging.getLogger("invoice_extraction.validation.confidence_scorer")


# Field criticality levels with corresponding thresholds
FIELD_CRITICALITY = {
    "invoice_number": "critical",
    "invoice_date": "critical",
    "total_amount": "critical",
    "vendor_name": "critical",
    "subtotal": "important",
    "tax_amount": "important",
    "due_date": "important",
    "customer_name": "important",
    "currency": "important",
    "vendor_address": "normal",
    "vendor_email": "normal",
    "vendor_phone": "normal",
    "customer_address": "normal",
    "shipping": "normal",
}

# Default thresholds by criticality
DEFAULT_THRESHOLDS = {
    "critical": {"auto_accept": 95, "review": 80, "reject": 60},
    "important": {"auto_accept": 90, "review": 70, "reject": 50},
    "normal": {"auto_accept": 85, "review": 60, "reject": 40},
}


class CalibratedConfidenceScorer:
    """
    Produces calibrated, field-level confidence scores.

    Takes raw model confidence and adjusts based on validation layer
    results to produce realistic, well-calibrated confidence scores.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get("enabled", True)
        self.thresholds = config.get("thresholds", DEFAULT_THRESHOLDS)
        self.field_criticality = config.get("field_criticality", FIELD_CRITICALITY)

        # Weights for combining signals
        self.model_weight = config.get("model_weight", 0.40)
        self.rag_weight = config.get("rag_weight", 0.15)
        self.multi_agent_weight = config.get("multi_agent_weight", 0.15)
        self.qae_weight = config.get("qae_weight", 0.15)
        self.neuro_weight = config.get("neuro_weight", 0.15)

    def validate(
        self,
        extraction: ExtractionOutput,
        layer_results: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Score confidence for all fields and produce decisions.

        Args:
            extraction: The extraction output
            layer_results: Results from layers 1-4 for context

        Returns:
            Validation result with per-field decisions
        """
        if not self.enabled:
            return {"enabled": False, "passed": True}

        layer_results = layer_results or {}

        result = {
            "layer": "calibrated_confidence",
            "passed": True,
            "score": 0.0,
            "field_scores": {},
            "decisions": {
                "auto_accept": [],
                "review": [],
                "reject": [],
            },
            "overall_decision": "auto_accept",
            "issues": [],
        }

        all_scores = []

        # Score each header field
        for field_name in ExtractionOutput.HEADER_FIELDS:
            fv = extraction.get_field(field_name)
            if not fv or fv.value is None:
                continue

            field_score = self._score_field(
                field_name, fv, extraction, layer_results
            )
            result["field_scores"][field_name] = field_score
            all_scores.append(field_score["calibrated_confidence"])

            # Apply decision
            decision = field_score["decision"]
            result["decisions"][decision].append(field_name)

            # Update the field's confidence with calibrated value
            fv.confidence = field_score["calibrated_confidence"]
            fv.validation_method = f"calibrated_{decision}"

            if decision == "reject":
                result["issues"].append(
                    f"Field '{field_name}' rejected: "
                    f"confidence={field_score['calibrated_confidence']:.1f}%"
                )
                fv.uncertain = True

        # Score line items collectively
        if extraction.line_items:
            item_scores = self._score_line_items(
                extraction, layer_results
            )
            result["line_item_scores"] = item_scores
            all_scores.append(item_scores["avg_confidence"])

        # Overall score
        if all_scores:
            result["score"] = sum(all_scores) / len(all_scores)
        else:
            result["score"] = 0.0

        # Overall decision
        if result["decisions"]["reject"]:
            result["overall_decision"] = "reject"
            result["passed"] = False
        elif result["decisions"]["review"]:
            result["overall_decision"] = "review"
            result["passed"] = True  # Pass but flag for review
        else:
            result["overall_decision"] = "auto_accept"
            result["passed"] = True

        return result

    def _score_field(
        self,
        field_name: str,
        fv: FieldValue,
        extraction: ExtractionOutput,
        layer_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Score a single field."""
        criticality = self.field_criticality.get(field_name, "normal")
        thresholds = self.thresholds.get(criticality, DEFAULT_THRESHOLDS["normal"])

        # Base: model confidence
        model_conf = fv.confidence  # Already 0-100 scale

        # Adjust based on layer results
        adjustments = []

        # Layer 1: RAG adjustment
        rag_result = layer_results.get("rag_validation", {})
        if rag_result.get("enabled", True):
            rag_score = rag_result.get("score", 0.5) * 100
            adjustments.append(("rag", rag_score, self.rag_weight))

        # Layer 2: Multi-agent adjustment
        ma_result = layer_results.get("multi_agent_validation", {})
        if ma_result.get("enabled", True):
            # Check if field had specific issues in multi-agent
            field_penalty = 0
            for issue in ma_result.get("issues", []):
                if field_name in issue.lower():
                    field_penalty += 5

            ma_score = ma_result.get("consensus_score", 0.5) * 100 - field_penalty
            adjustments.append(("multi_agent", ma_score, self.multi_agent_weight))

        # Layer 3: QAE adjustment  
        qae_result = layer_results.get("qae_validation", {})
        if qae_result.get("enabled", True):
            field_qae = qae_result.get("field_results", {}).get(field_name, {})
            if field_qae:
                qae_consistent = field_qae.get("consistent", True)
                qae_score = 100 if qae_consistent else 40
            else:
                qae_score = 70  # Neutral for fields not checked by QAE
            adjustments.append(("qae", qae_score, self.qae_weight))

        # Layer 4: Neurosymbolic adjustment
        neuro_result = layer_results.get("neurosymbolic_validation", {})
        if neuro_result.get("enabled", True):
            # Check if field was involved in any rule failures
            neuro_issues = neuro_result.get("issues", [])
            field_involved = any(
                field_name in issue.lower() for issue in neuro_issues
            )
            neuro_score = 40 if field_involved else 100
            adjustments.append(("neurosymbolic", neuro_score, self.neuro_weight))

        # Calculate calibrated confidence
        total_weight = self.model_weight
        weighted_sum = model_conf * self.model_weight

        for adj_name, adj_score, adj_weight in adjustments:
            weighted_sum += adj_score * adj_weight
            total_weight += adj_weight

        calibrated = weighted_sum / total_weight if total_weight > 0 else model_conf

        # Clamp to 0-100
        calibrated = max(0.0, min(100.0, calibrated))

        # Determine decision
        if calibrated >= thresholds["auto_accept"]:
            decision = "auto_accept"
        elif calibrated >= thresholds["review"]:
            decision = "review"
        else:
            decision = "reject"

        return {
            "field": field_name,
            "criticality": criticality,
            "model_confidence": model_conf,
            "calibrated_confidence": round(calibrated, 1),
            "adjustments": {name: score for name, score, _ in adjustments},
            "thresholds": thresholds,
            "decision": decision,
        }

    def _score_line_items(
        self,
        extraction: ExtractionOutput,
        layer_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Score line items collectively."""
        if not extraction.line_items:
            return {"avg_confidence": 0, "count": 0}

        confidences = []
        for item in extraction.line_items:
            item_confs = []
            for attr_name in ["description", "quantity", "unit_price", "line_total"]:
                fv = getattr(item, attr_name, None)
                if fv and fv.value is not None:
                    item_confs.append(fv.confidence)
            if item_confs:
                confidences.append(sum(item_confs) / len(item_confs))

        avg = sum(confidences) / len(confidences) if confidences else 0

        # Penalize if neurosymbolic found issues
        neuro_result = layer_results.get("neurosymbolic_validation", {})
        neuro_rules = neuro_result.get("rule_results", {})

        if neuro_rules.get("line_item_math", {}).get("passed") is False:
            avg *= 0.8  # 20% penalty for math errors

        if neuro_rules.get("subtotal_sum", {}).get("passed") is False:
            avg *= 0.9  # 10% penalty

        return {
            "avg_confidence": round(avg, 1),
            "count": len(extraction.line_items),
            "item_confidences": confidences,
        }
