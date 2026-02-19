"""
6-Layer Anti-Hallucination Validation Framework (2026)

Orchestrates all 6 validation layers in sequence:
  Layer 1: RAG Validator (vendor pattern matching)
  Layer 2: Multi-Agent Validator (4 agents, 75%+ consensus)
  Layer 3: Q-A-E Validator (re-query for critical fields)
  Layer 4: Neurosymbolic Rules (deterministic math / logic)
  Layer 5: Calibrated Confidence Scorer
  Layer 6: Cross-Model Consistency (embedded in this orchestrator)

Target: ≥95% hallucination detection, ≤8% false positives.

Author: ML Engineering Team
Version: 2.0.0
"""

import logging
import time
from typing import Any, Dict, List, Optional

from src.models.base_extractor import ExtractionOutput, BaseExtractor
from src.validation.rag_validator import RAGValidator
from src.validation.multi_agent import MultiAgentValidator
from src.validation.qae_validator import QAEValidator
from src.validation.neurosymbolic import NeurosymbolicValidator
from src.validation.confidence_scorer import CalibratedConfidenceScorer

logger = logging.getLogger("invoice_extraction.validation.framework_2026")


class ValidationFramework2026:
    """
    Unified 6-layer anti-hallucination framework.

    Runs all validation layers sequentially, passing accumulated
    context between layers so downstream layers benefit from
    upstream findings.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        validation_config = config.get("validation", {})

        # Initialize all layers
        self.rag_validator = RAGValidator(
            validation_config.get("rag_validation", {})
        )
        self.multi_agent_validator = MultiAgentValidator(
            validation_config.get("multi_agent", {})
        )
        self.qae_validator = QAEValidator(
            validation_config.get("qae_validation", {})
        )
        self.neurosymbolic_validator = NeurosymbolicValidator(
            validation_config.get("neurosymbolic", {})
        )
        self.confidence_scorer = CalibratedConfidenceScorer(
            validation_config.get("confidence_scoring", {})
        )

        # Cross-model settings (Layer 6)
        cross_config = validation_config.get("cross_model", {})
        self.cross_model_enabled = cross_config.get("enabled", True)
        self.cross_agreement_threshold = cross_config.get(
            "agreement_threshold", 0.90
        )

        # Framework-level settings
        self.fail_fast = validation_config.get("fail_fast", False)
        self.min_overall_score = validation_config.get(
            "min_overall_score", 0.70
        )

        logger.info("ValidationFramework2026 initialized with all 6 layers")

    def validate(
        self,
        extraction: ExtractionOutput,
        extractor: Optional[BaseExtractor] = None,
        image=None,
        secondary_extractions: Optional[List[ExtractionOutput]] = None,
    ) -> Dict[str, Any]:
        """
        Run the full 6-layer validation pipeline.

        Args:
            extraction: Primary extraction output to validate
            extractor: The primary model extractor (for QAE re-querying)
            image: Original image (for QAE re-querying)
            secondary_extractions: Results from other models (for cross-model)

        Returns:
            Comprehensive validation report
        """
        start_time = time.time()

        report = {
            "framework": "anti_hallucination_6layer_2026",
            "version": "2.0.0",
            "overall_passed": True,
            "overall_score": 0.0,
            "overall_decision": "auto_accept",
            "layers": {},
            "layer_scores": {},
            "all_issues": [],
            "corrections_applied": [],
            "processing_time_ms": 0,
        }

        layer_results = {}  # Accumulated results for downstream layers

        # === Layer 1: RAG Validation ===
        logger.info("Running Layer 1: RAG Validation")
        try:
            rag_result = self.rag_validator.validate(extraction)
            report["layers"]["rag_validation"] = rag_result
            report["layer_scores"]["rag"] = rag_result.get("score", 0)
            layer_results["rag_validation"] = rag_result

            if rag_result.get("issues"):
                report["all_issues"].extend(rag_result["issues"])

            if self.fail_fast and not rag_result.get("passed", True):
                report["overall_passed"] = False
                report["overall_score"] = rag_result.get("score", 0)
                report["processing_time_ms"] = int(
                    (time.time() - start_time) * 1000
                )
                return report

        except Exception as e:
            logger.error(f"Layer 1 (RAG) error: {e}")
            report["layers"]["rag_validation"] = {"error": str(e)}

        # === Layer 2: Multi-Agent Validation ===
        logger.info("Running Layer 2: Multi-Agent Validation")
        try:
            ma_result = self.multi_agent_validator.validate(extraction)
            report["layers"]["multi_agent_validation"] = ma_result
            report["layer_scores"]["multi_agent"] = ma_result.get(
                "consensus_score", 0
            )
            layer_results["multi_agent_validation"] = ma_result

            if ma_result.get("issues"):
                report["all_issues"].extend(ma_result["issues"])

            if self.fail_fast and not ma_result.get("passed", True):
                report["overall_passed"] = False
                report["overall_score"] = self._calculate_overall(report)
                report["processing_time_ms"] = int(
                    (time.time() - start_time) * 1000
                )
                return report

        except Exception as e:
            logger.error(f"Layer 2 (Multi-Agent) error: {e}")
            report["layers"]["multi_agent_validation"] = {"error": str(e)}

        # === Layer 3: Q-A-E Validation ===
        logger.info("Running Layer 3: Q-A-E Validation")
        try:
            qae_result = self.qae_validator.validate(
                extraction, extractor=extractor, image=image
            )
            report["layers"]["qae_validation"] = qae_result
            report["layer_scores"]["qae"] = qae_result.get("score", 0)
            layer_results["qae_validation"] = qae_result

            if qae_result.get("issues"):
                report["all_issues"].extend(qae_result["issues"])

        except Exception as e:
            logger.error(f"Layer 3 (QAE) error: {e}")
            report["layers"]["qae_validation"] = {"error": str(e)}

        # === Layer 4: Neurosymbolic Validation ===
        logger.info("Running Layer 4: Neurosymbolic Validation")
        try:
            neuro_result = self.neurosymbolic_validator.validate(extraction)
            report["layers"]["neurosymbolic_validation"] = neuro_result
            report["layer_scores"]["neurosymbolic"] = neuro_result.get(
                "score", 0
            )
            layer_results["neurosymbolic_validation"] = neuro_result

            if neuro_result.get("issues"):
                report["all_issues"].extend(neuro_result["issues"])

            if neuro_result.get("corrections"):
                report["corrections_applied"].extend(
                    neuro_result["corrections"]
                )

        except Exception as e:
            logger.error(f"Layer 4 (Neurosymbolic) error: {e}")
            report["layers"]["neurosymbolic_validation"] = {"error": str(e)}

        # === Layer 5: Calibrated Confidence ===
        logger.info("Running Layer 5: Calibrated Confidence")
        try:
            conf_result = self.confidence_scorer.validate(
                extraction, layer_results=layer_results
            )
            report["layers"]["calibrated_confidence"] = conf_result
            report["layer_scores"]["confidence"] = conf_result.get("score", 0)
            layer_results["calibrated_confidence"] = conf_result

            if conf_result.get("issues"):
                report["all_issues"].extend(conf_result["issues"])

            report["overall_decision"] = conf_result.get(
                "overall_decision", "review"
            )

        except Exception as e:
            logger.error(f"Layer 5 (Confidence) error: {e}")
            report["layers"]["calibrated_confidence"] = {"error": str(e)}

        # === Layer 6: Cross-Model Consistency ===
        if secondary_extractions and self.cross_model_enabled:
            logger.info("Running Layer 6: Cross-Model Consistency")
            try:
                cross_result = self._cross_model_validate(
                    extraction, secondary_extractions
                )
                report["layers"]["cross_model_consistency"] = cross_result
                report["layer_scores"]["cross_model"] = cross_result.get(
                    "score", 0
                )

                if cross_result.get("issues"):
                    report["all_issues"].extend(cross_result["issues"])

            except Exception as e:
                logger.error(f"Layer 6 (Cross-Model) error: {e}")
                report["layers"]["cross_model_consistency"] = {
                    "error": str(e)
                }
        else:
            report["layers"]["cross_model_consistency"] = {
                "enabled": False,
                "reason": "no_secondary_extractions"
                if not secondary_extractions
                else "disabled",
            }

        # === Final Scoring ===
        report["overall_score"] = self._calculate_overall(report)
        report["overall_passed"] = (
            report["overall_score"] >= self.min_overall_score
        )

        # Deduplicate issues
        report["all_issues"] = list(dict.fromkeys(report["all_issues"]))

        report["processing_time_ms"] = int(
            (time.time() - start_time) * 1000
        )

        # Store validation results in extraction
        extraction.validation_results = report

        logger.info(
            f"Validation complete: score={report['overall_score']:.2f}, "
            f"passed={report['overall_passed']}, "
            f"decision={report['overall_decision']}, "
            f"issues={len(report['all_issues'])}, "
            f"time={report['processing_time_ms']}ms"
        )

        return report

    def _cross_model_validate(
        self,
        primary: ExtractionOutput,
        secondaries: List[ExtractionOutput],
    ) -> Dict[str, Any]:
        """
        Layer 6: Cross-model consistency checking.

        Compares primary extraction against secondary extractions.
        Fields where models agree get boosted confidence;
        disagreements trigger review.
        """
        result = {
            "layer": "cross_model_consistency",
            "passed": True,
            "score": 0.0,
            "field_agreements": {},
            "field_disagreements": {},
            "issues": [],
        }

        agreements = 0
        total_comparisons = 0

        for field_name in ExtractionOutput.HEADER_FIELDS:
            primary_fv = primary.get_field(field_name)
            if not primary_fv or primary_fv.value is None:
                continue

            field_agreements = 0
            field_values = [str(primary_fv.value)]

            for secondary in secondaries:
                sec_fv = secondary.get_field(field_name)
                if not sec_fv or sec_fv.value is None:
                    continue

                total_comparisons += 1
                field_values.append(str(sec_fv.value))

                if self._values_match(
                    primary_fv.value, sec_fv.value, field_name
                ):
                    agreements += 1
                    field_agreements += 1

            if len(field_values) > 1:
                agreement_ratio = field_agreements / (len(field_values) - 1)
                if agreement_ratio >= self.cross_agreement_threshold:
                    result["field_agreements"][field_name] = {
                        "values": field_values,
                        "agreement": agreement_ratio,
                    }
                    # Boost confidence for agreed fields
                    primary_fv.confidence = min(
                        100, primary_fv.confidence * 1.05
                    )
                    primary_fv.verified = True
                    primary_fv.validation_method = "cross_model_verified"
                else:
                    result["field_disagreements"][field_name] = {
                        "values": field_values,
                        "agreement": agreement_ratio,
                    }
                    result["issues"].append(
                        f"Cross-model disagreement on {field_name}: "
                        f"values={field_values}"
                    )
                    primary_fv.uncertain = True

        # Score
        if total_comparisons > 0:
            result["score"] = agreements / total_comparisons
        else:
            result["score"] = 1.0

        result["passed"] = result["score"] >= self.cross_agreement_threshold

        return result

    def _values_match(
        self, val1: Any, val2: Any, field_name: str
    ) -> bool:
        """Compare two field values accounting for field type."""
        s1 = str(val1).strip()
        s2 = str(val2).strip()

        # Exact match
        if s1.lower() == s2.lower():
            return True

        # Numeric fields - compare as numbers
        numeric_fields = {
            "subtotal", "tax_amount", "shipping", "total_amount",
        }
        if field_name in numeric_fields:
            try:
                n1 = float(s1.replace(",", ""))
                n2 = float(s2.replace(",", ""))
                return abs(n1 - n2) < 0.02
            except (ValueError, TypeError):
                return False

        # Date fields
        if "date" in field_name:
            try:
                from dateutil.parser import parse
                d1 = parse(s1).date()
                d2 = parse(s2).date()
                return d1 == d2
            except Exception:
                return False

        # Fuzzy match for text fields
        return self._fuzzy_match(s1, s2) >= 0.85

    def _fuzzy_match(self, s1: str, s2: str) -> float:
        """Trigram Jaccard similarity."""
        s1 = s1.lower().strip()
        s2 = s2.lower().strip()

        if s1 == s2:
            return 1.0
        if s1 in s2 or s2 in s1:
            return 0.9

        def trigrams(s):
            return set(s[i:i + 3] for i in range(len(s) - 2))

        t1 = trigrams(s1)
        t2 = trigrams(s2)

        if not t1 or not t2:
            return 0.0

        return len(t1 & t2) / len(t1 | t2)

    def _calculate_overall(self, report: Dict[str, Any]) -> float:
        """Calculate weighted overall validation score."""
        weights = {
            "rag": 0.10,
            "multi_agent": 0.20,
            "qae": 0.15,
            "neurosymbolic": 0.25,
            "confidence": 0.20,
            "cross_model": 0.10,
        }

        total_weight = 0
        weighted_sum = 0

        for layer_name, weight in weights.items():
            score = report["layer_scores"].get(layer_name)
            if score is not None:
                weighted_sum += score * weight
                total_weight += weight

        if total_weight > 0:
            return weighted_sum / total_weight
        return 0.0
