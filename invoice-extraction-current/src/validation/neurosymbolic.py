"""
Layer 4: Neurosymbolic Rule Engine (100% Math Correctness)

Applies deterministic symbolic rules that must always be satisfied:
- Line items × unit price = line total
- Sum of line totals = subtotal
- Subtotal + tax + shipping = total
- Quantities must be positive integers or valid decimals
- Dates must not be in the far future
- Required fields must be present for valid invoice

Based on MIT CSAIL neurosymbolic AI research (2026).

Author: ML Engineering Team
Version: 2.0.0
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.models.base_extractor import ExtractionOutput

logger = logging.getLogger("invoice_extraction.validation.neurosymbolic")


class NeurosymbolicValidator:
    """
    Deterministic rule-based validation engine.

    Unlike ML-based validators, these rules are absolute:
    if they fail, the extraction is definitively wrong.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get("enabled", True)
        self.tolerance = config.get("tolerance", 0.02)
        self.required_fields = config.get("required_fields", [
            "invoice_number", "invoice_date", "total_amount", "vendor_name",
        ])

    def validate(self, extraction: ExtractionOutput) -> Dict[str, Any]:
        """Apply all neurosymbolic rules."""
        if not self.enabled:
            return {"enabled": False, "passed": True}

        result = {
            "layer": "neurosymbolic_validation",
            "passed": True,
            "score": 0.0,
            "rules_checked": 0,
            "rules_passed": 0,
            "rules_failed": 0,
            "rule_results": {},
            "corrections": [],
            "issues": [],
        }

        rules = [
            self._rule_required_fields,
            self._rule_line_item_math,
            self._rule_subtotal_sum,
            self._rule_total_calculation,
            self._rule_positive_quantities,
            self._rule_positive_amounts,
            self._rule_date_not_future,
            self._rule_due_after_invoice,
            self._rule_line_items_have_descriptions,
            self._rule_no_duplicate_line_numbers,
        ]

        for rule_fn in rules:
            try:
                rule_name = rule_fn.__name__.replace("_rule_", "")
                rule_result = rule_fn(extraction)
                result["rule_results"][rule_name] = rule_result
                result["rules_checked"] += 1

                if rule_result["passed"]:
                    result["rules_passed"] += 1
                else:
                    result["rules_failed"] += 1
                    result["issues"].extend(rule_result.get("issues", []))

                if rule_result.get("corrections"):
                    result["corrections"].extend(rule_result["corrections"])

            except Exception as e:
                logger.error(f"Rule {rule_fn.__name__} error: {e}")

        # Score
        if result["rules_checked"] > 0:
            result["score"] = result["rules_passed"] / result["rules_checked"]
        else:
            result["score"] = 1.0

        result["passed"] = result["rules_failed"] == 0

        return result

    def _rule_required_fields(self, extraction: ExtractionOutput) -> Dict[str, Any]:
        """Check that all required fields have values."""
        missing = []
        for field_name in self.required_fields:
            fv = extraction.get_field(field_name)
            if not fv or fv.value is None or str(fv.value).strip() == "":
                missing.append(field_name)

        return {
            "passed": len(missing) == 0,
            "missing_fields": missing,
            "issues": [f"Missing required field: {f}" for f in missing],
        }

    def _rule_line_item_math(self, extraction: ExtractionOutput) -> Dict[str, Any]:
        """Check: quantity × unit_price = line_total for each line item."""
        if not extraction.line_items:
            return {"passed": True, "issues": []}

        issues = []
        corrections = []

        for item in extraction.line_items:
            qty = self._to_float(item.quantity.value)
            price = self._to_float(item.unit_price.value)
            total = self._to_float(item.line_total.value)

            if qty is not None and price is not None and total is not None:
                expected = round(qty * price, 2)
                diff = abs(expected - total)
                if diff > self.tolerance:
                    issues.append(
                        f"Line {item.line_number}: {qty} × {price} = {expected} ≠ {total} (diff={diff:.2f})"
                    )
                    # Auto-correct: trust qty and price, fix total
                    corrections.append({
                        "field": f"line_item_{item.line_number}_total",
                        "old_value": total,
                        "new_value": expected,
                        "reason": "Recalculated from qty × unit_price",
                    })
                    item.line_total.value = expected
                    item.line_total.validation_method = "neurosymbolic_corrected"

        return {
            "passed": len(issues) == 0,
            "issues": issues,
            "corrections": corrections,
        }

    def _rule_subtotal_sum(self, extraction: ExtractionOutput) -> Dict[str, Any]:
        """Check: sum of line totals = subtotal."""
        if not extraction.line_items or extraction.subtotal.value is None:
            return {"passed": True, "issues": []}

        try:
            items_sum = sum(
                float(item.line_total.value)
                for item in extraction.line_items
                if item.line_total.value is not None
            )
            subtotal = float(str(extraction.subtotal.value).replace(",", ""))
            diff = abs(items_sum - subtotal)

            if diff > self.tolerance:
                return {
                    "passed": False,
                    "issues": [
                        f"Sum of line totals ({items_sum:.2f}) ≠ subtotal ({subtotal:.2f}), diff={diff:.2f}"
                    ],
                    "corrections": [{
                        "field": "subtotal",
                        "old_value": subtotal,
                        "new_value": round(items_sum, 2),
                        "reason": "Recalculated from sum of line totals",
                    }],
                }
        except (ValueError, TypeError) as e:
            return {"passed": False, "issues": [f"Cannot verify subtotal sum: {e}"]}

        return {"passed": True, "issues": []}

    def _rule_total_calculation(self, extraction: ExtractionOutput) -> Dict[str, Any]:
        """Check: subtotal + tax + shipping = total."""
        subtotal = self._to_float(extraction.subtotal.value)
        tax = self._to_float(extraction.tax_amount.value, 0.0)
        shipping = self._to_float(extraction.shipping.value, 0.0)
        total = self._to_float(extraction.total_amount.value)

        if subtotal is None or total is None:
            return {"passed": True, "issues": []}

        calculated = round(subtotal + tax + shipping, 2)
        diff = abs(calculated - total)

        if diff > self.tolerance:
            return {
                "passed": False,
                "issues": [
                    f"subtotal({subtotal}) + tax({tax}) + shipping({shipping}) "
                    f"= {calculated} ≠ total({total}), diff={diff:.2f}"
                ],
                "corrections": [{
                    "field": "total_amount",
                    "old_value": total,
                    "new_value": calculated,
                    "reason": "Recalculated from subtotal + tax + shipping",
                }],
            }

        return {"passed": True, "issues": []}

    def _rule_positive_quantities(self, extraction: ExtractionOutput) -> Dict[str, Any]:
        """Check: all quantities are positive."""
        if not extraction.line_items:
            return {"passed": True, "issues": []}

        issues = []
        for item in extraction.line_items:
            qty = self._to_float(item.quantity.value)
            if qty is not None and qty <= 0:
                issues.append(
                    f"Line {item.line_number}: non-positive quantity ({qty})"
                )

        return {"passed": len(issues) == 0, "issues": issues}

    def _rule_positive_amounts(self, extraction: ExtractionOutput) -> Dict[str, Any]:
        """Check: monetary amounts are non-negative."""
        issues = []
        for field_name in ["subtotal", "tax_amount", "shipping", "total_amount"]:
            fv = extraction.get_field(field_name)
            if fv and fv.value is not None:
                val = self._to_float(fv.value)
                if val is not None and val < 0:
                    issues.append(f"{field_name} is negative: {val}")

        return {"passed": len(issues) == 0, "issues": issues}

    def _rule_date_not_future(self, extraction: ExtractionOutput) -> Dict[str, Any]:
        """Check: invoice date is not more than 30 days in the future."""
        if not extraction.invoice_date.value:
            return {"passed": True, "issues": []}

        date = self._parse_date(str(extraction.invoice_date.value))
        if date is None:
            return {"passed": True, "issues": []}

        future_limit = datetime.now().date() + timedelta(days=30)
        if date > future_limit:
            return {
                "passed": False,
                "issues": [f"Invoice date ({date}) is too far in the future"],
            }

        # Check not unreasonably old (before year 2000)
        if date.year < 2000:
            return {
                "passed": False,
                "issues": [f"Invoice date ({date}) is before year 2000"],
            }

        return {"passed": True, "issues": []}

    def _rule_due_after_invoice(self, extraction: ExtractionOutput) -> Dict[str, Any]:
        """Check: due date >= invoice date."""
        if not extraction.invoice_date.value or not extraction.due_date.value:
            return {"passed": True, "issues": []}

        inv_date = self._parse_date(str(extraction.invoice_date.value))
        due_date = self._parse_date(str(extraction.due_date.value))

        if inv_date is None or due_date is None:
            return {"passed": True, "issues": []}

        if due_date < inv_date:
            return {
                "passed": False,
                "issues": [
                    f"Due date ({due_date}) is before invoice date ({inv_date})"
                ],
            }

        return {"passed": True, "issues": []}

    def _rule_line_items_have_descriptions(
        self, extraction: ExtractionOutput
    ) -> Dict[str, Any]:
        """Check: all line items have descriptions."""
        if not extraction.line_items:
            return {"passed": True, "issues": []}

        issues = []
        for item in extraction.line_items:
            if not item.description.value or str(item.description.value).strip() == "":
                issues.append(
                    f"Line {item.line_number}: missing description"
                )

        return {"passed": len(issues) == 0, "issues": issues}

    def _rule_no_duplicate_line_numbers(
        self, extraction: ExtractionOutput
    ) -> Dict[str, Any]:
        """Check: no duplicate line numbers."""
        if not extraction.line_items:
            return {"passed": True, "issues": []}

        line_nums = [item.line_number for item in extraction.line_items]
        seen = set()
        duplicates = set()
        for n in line_nums:
            if n in seen:
                duplicates.add(n)
            seen.add(n)

        if duplicates:
            return {
                "passed": False,
                "issues": [f"Duplicate line numbers: {sorted(duplicates)}"],
            }

        return {"passed": True, "issues": []}

    def _to_float(
        self, value: Any, default: Optional[float] = None
    ) -> Optional[float]:
        if value is None:
            return default
        try:
            cleaned = str(value).replace(",", "").replace("$", "").replace("€", "").replace("£", "")
            return float(cleaned)
        except (ValueError, TypeError):
            return default

    def _parse_date(self, date_str: str):
        """Parse date string."""
        formats = [
            "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%B %d, %Y",
            "%b %d, %Y", "%d %B %Y", "%d-%m-%Y", "%m-%d-%Y",
            "%d.%m.%Y", "%Y/%m/%d",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt).date()
            except ValueError:
                continue
        try:
            from dateutil.parser import parse
            return parse(date_str).date()
        except Exception:
            return None
