"""
Layer 3: Question-Answer-Evaluation (Q-A-E) Validation

For critical fields (invoice_number, total_amount, invoice_date),
the model is re-queried with targeted questions to confirm answers.
If the answers diverge, the field is marked uncertain.

Based on DeepMind / AlphaProof approach to self-consistency (2026).

Author: ML Engineering Team
Version: 2.0.0
"""

import logging
from typing import Any, Dict, List, Optional, Callable

from src.models.base_extractor import ExtractionOutput, BaseExtractor

logger = logging.getLogger("invoice_extraction.validation.qae")


class QAEValidator:
    """
    Question-Answer-Evaluation validation layer.

    For every critical field, asks the extractor 2-3 targeted questions.
    If answers are inconsistent with the extraction, flags as uncertain.
    """

    CRITICAL_FIELDS = {
        "invoice_number": {
            "questions": [
                "What is the invoice number or invoice ID on this document?",
                "What reference number is printed at the top of this invoice?",
            ],
            "match_type": "exact",
        },
        "total_amount": {
            "questions": [
                "What is the total amount due on this invoice?",
                "What is the grand total or balance due shown on this invoice?",
            ],
            "match_type": "numeric",
        },
        "invoice_date": {
            "questions": [
                "What is the date of this invoice?",
                "When was this invoice issued?",
            ],
            "match_type": "date",
        },
        "vendor_name": {
            "questions": [
                "What company or vendor issued this invoice?",
                "What is the seller or supplier name on this invoice?",
            ],
            "match_type": "fuzzy",
        },
    }

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get("enabled", True)
        self.agreement_threshold = config.get("agreement_threshold", 0.5)
        self.max_questions = config.get("max_questions_per_field", 2)

    def validate(
        self,
        extraction: ExtractionOutput,
        extractor: Optional[BaseExtractor] = None,
        image=None,
    ) -> Dict[str, Any]:
        """
        Validate critical fields using Q-A-E.

        If no extractor is provided or answer_question is not available,
        only performs self-consistency checks on extracted data.
        """
        if not self.enabled:
            return {"enabled": False, "passed": True}

        result = {
            "layer": "qae_validation",
            "passed": True,
            "score": 0.0,
            "field_results": {},
            "issues": [],
        }

        can_question = (
            extractor is not None
            and image is not None
            and hasattr(extractor, "answer_question")
        )

        field_scores = []

        for field_name, field_config in self.CRITICAL_FIELDS.items():
            fv = extraction.get_field(field_name)
            if not fv or fv.value is None:
                continue

            field_result = {
                "original_value": str(fv.value),
                "original_confidence": fv.confidence,
                "questions_asked": 0,
                "agreements": 0,
                "disagreements": 0,
                "answers": [],
                "consistent": True,
            }

            if can_question:
                questions = field_config["questions"][:self.max_questions]
                match_type = field_config["match_type"]

                for q in questions:
                    try:
                        answer = extractor.answer_question(image, q)
                        field_result["questions_asked"] += 1
                        field_result["answers"].append(answer)

                        matches = self._compare_values(
                            str(fv.value), answer, match_type
                        )
                        if matches:
                            field_result["agreements"] += 1
                        else:
                            field_result["disagreements"] += 1

                    except Exception as e:
                        logger.warning(f"QAE question failed for {field_name}: {e}")

                # Determine consistency
                total = field_result["agreements"] + field_result["disagreements"]
                if total > 0:
                    agreement_ratio = field_result["agreements"] / total
                    field_result["consistent"] = agreement_ratio >= self.agreement_threshold
                    field_scores.append(agreement_ratio)
                else:
                    field_scores.append(0.5)  # Unknown

                if not field_result["consistent"]:
                    result["issues"].append(
                        f"QAE inconsistency for {field_name}: "
                        f"original='{fv.value}', QA answers={field_result['answers']}"
                    )
                    # Mark field as uncertain
                    fv.uncertain = True
                    fv.validation_method = "qae_failed"
            else:
                # Without extractor, perform self-consistency checks
                score = self._self_consistency_check(extraction, field_name)
                field_scores.append(score)
                if score < 0.8:
                    field_result["consistent"] = False
                    result["issues"].append(
                        f"Self-consistency check low for {field_name}: {score:.2f}"
                    )

            result["field_results"][field_name] = field_result

        # Overall score
        if field_scores:
            result["score"] = sum(field_scores) / len(field_scores)
        else:
            result["score"] = 1.0

        result["passed"] = result["score"] >= self.agreement_threshold

        return result

    def _compare_values(
        self, original: str, answer: str, match_type: str
    ) -> bool:
        """Compare extraction value with QA answer."""
        if not answer:
            return False

        original = original.strip()
        answer = answer.strip()

        if match_type == "exact":
            return self._normalize_string(original) == self._normalize_string(answer)

        elif match_type == "numeric":
            return self._compare_numeric(original, answer)

        elif match_type == "date":
            return self._compare_dates(original, answer)

        elif match_type == "fuzzy":
            return self._fuzzy_match(original, answer) >= 0.8

        return original.lower() == answer.lower()

    def _normalize_string(self, s: str) -> str:
        """Normalize a string for comparison."""
        import re
        return re.sub(r"[\s\-\/\.\#]+", "", s).lower()

    def _compare_numeric(self, orig: str, answer: str) -> bool:
        """Compare two numeric values."""
        import re

        def extract_number(s):
            nums = re.findall(r"[\d,]+\.?\d*", s.replace(",", ""))
            if nums:
                try:
                    return float(nums[-1])
                except ValueError:
                    return None
            return None

        n1 = extract_number(orig)
        n2 = extract_number(answer)

        if n1 is not None and n2 is not None:
            return abs(n1 - n2) < 0.02
        return False

    def _compare_dates(self, orig: str, answer: str) -> bool:
        """Compare two date strings."""
        try:
            from dateutil.parser import parse
            d1 = parse(orig).date()
            d2 = parse(answer).date()
            return d1 == d2
        except Exception:
            return self._normalize_string(orig) == self._normalize_string(answer)

    def _fuzzy_match(self, s1: str, s2: str) -> float:
        """Simple fuzzy matching using character overlap (Jaccard)."""
        s1_lower = s1.lower().strip()
        s2_lower = s2.lower().strip()

        if s1_lower == s2_lower:
            return 1.0

        # Check containment
        if s1_lower in s2_lower or s2_lower in s1_lower:
            return 0.9

        # Character n-gram Jaccard
        def ngrams(s, n=3):
            return set(s[i:i + n] for i in range(len(s) - n + 1))

        ng1 = ngrams(s1_lower)
        ng2 = ngrams(s2_lower)

        if not ng1 or not ng2:
            return 0.0

        intersection = ng1 & ng2
        union = ng1 | ng2
        return len(intersection) / len(union)

    def _self_consistency_check(
        self, extraction: ExtractionOutput, field_name: str
    ) -> float:
        """
        Perform consistency check without re-querying the model.
        Checks internal consistency based on relationships.
        """
        fv = extraction.get_field(field_name)
        if not fv or fv.value is None:
            return 0.5

        score = 1.0

        # Confidence-based penalty
        if fv.confidence < 80:
            score -= 0.2
        if fv.confidence < 60:
            score -= 0.3

        # Field-specific checks
        if field_name == "total_amount":
            subtotal = extraction.subtotal.value
            if subtotal is not None:
                try:
                    total = float(str(fv.value).replace(",", ""))
                    sub = float(str(subtotal).replace(",", ""))
                    if total < sub:
                        score -= 0.3  # Total less than subtotal
                except (ValueError, TypeError):
                    score -= 0.1

        elif field_name == "invoice_number":
            # Should be non-empty and not too long
            val = str(fv.value)
            if len(val) > 30:
                score -= 0.2
            if len(val) < 2:
                score -= 0.2

        return max(0.0, score)
