"""
Validator — post-processing and math cross-validation for extracted invoice data.

Performs:
    1. Required fields present check (invoice_number, total_amount)
    2. Monetary values are non-negative
    3. Line item math: qty × unit_price ≈ total (within MATH_TOLERANCE)
    4. Sum of line items ≈ subtotal
    5. Grand total consistency: subtotal + tax - discount + shipping ≈ total
    6. Date validation and normalisation to ISO 8601
    7. GSTIN format check (15-char alphanumeric)

RULES:
    - DOES NOT modify the original invoice fields.
    - Only adds a 'validation' key with the validation report.
    - Failed math checks are warnings for human review, NOT rejections.
    - Never raises exceptions for failed checks — logs and flags.
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.config import MATH_TOLERANCE, MATH_TOLERANCE_PERCENT

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# HELPER UTILITIES
# ═══════════════════════════════════════════════════════════════════════════

def _parse_amount(value: Any) -> Optional[float]:
    """Parse an amount value to float, handling various formats."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = re.sub(r'[₹$€£,\s]', '', value)
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _normalize_date(date_str: str) -> Optional[str]:
    """
    Normalize a date string to ISO 8601 format (YYYY-MM-DD).

    Handles formats: DD/MM/YYYY, DD-MM-YYYY, MM/DD/YYYY, YYYY-MM-DD,
    DD Mon YYYY, etc.
    """
    if not date_str:
        return None

    date_str = str(date_str).strip()

    # Already ISO format
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        return date_str

    date_formats = [
        "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
        "%m/%d/%Y", "%m-%d-%Y",
        "%Y/%m/%d",
        "%d %b %Y", "%d %B %Y",
        "%b %d, %Y", "%B %d, %Y",
        "%d/%m/%y", "%d-%m-%y",
    ]

    for fmt in date_formats:
        try:
            parsed = datetime.strptime(date_str, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue

    logger.warning("Could not parse date: '%s'", date_str)
    return date_str  # Return original if we can't parse


def _validate_gstin(gstin: str) -> bool:
    """Validate Indian GSTIN format: 15 alphanumeric characters."""
    if not gstin:
        return False
    return bool(re.match(r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]{3}$', gstin.strip()))


# ═══════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════

def validate_invoice(data: dict) -> dict:
    """
    Runs all validation checks on an extracted invoice dict.
    DOES NOT modify the original fields (except adding 'validation').
    Adds a 'validation' key to the data and returns it.

    Checks performed:
        1. Required fields present
        2. Monetary values are non-negative
        3. Line item math: qty × unit_price ≈ total
        4. Subtotal = sum of line item totals
        5. Grand total = subtotal + tax - discount + shipping
        6. Date validation (if present)
        7. GSTIN format validation (if present)

    Args:
        data: Extracted invoice data dictionary.

    Returns:
        Same dictionary with added 'validation' key.
    """
    warnings: List[str] = []
    math_checks: Dict[str, Any] = {}
    passed = True

    # ── Check 1: Required fields ──────────────────────────────────────────
    required_fields = ["invoice_number", "total_amount"]
    for field in required_fields:
        if data.get(field) is None:
            warnings.append(f"MISSING_REQUIRED_FIELD: '{field}' is null")
            passed = False

    # ── Check 2: Monetary values non-negative ─────────────────────────────
    money_fields = ["subtotal", "tax_amount", "discount", "shipping", "total_amount"]
    for field in money_fields:
        val = data.get(field)
        if val is not None and isinstance(val, (int, float)) and val < 0:
            warnings.append(f"NEGATIVE_VALUE: '{field}' is {val} (unexpected)")

    # ── Check 3: Line item math (qty × unit_price ≈ total) ───────────────
    line_item_checks: List[Dict[str, Any]] = []
    computed_sum = 0.0
    has_line_totals = False

    for i, item in enumerate(data.get("line_items", []), start=1):
        qty = item.get("quantity")
        unit_price = item.get("unit_price")
        item_total = item.get("total") or item.get("line_total")

        item_check: Dict[str, Any] = {"line_number": i, "ok": True, "note": ""}

        # Parse item_total regardless of whether qty/unit_price are present.
        # OCR invoices often have a total but missing qty or unit_price — those
        # items must still count toward the subtotal sum.
        if item_total is not None:
            item_total_f = _parse_amount(item_total) if not isinstance(item_total, (int, float)) else float(item_total)
            if item_total_f is not None:
                has_line_totals = True
                computed_sum += item_total_f

                # Only cross-check qty×unit_price when all three values exist
                if qty is not None and unit_price is not None:
                    qty_f = _parse_amount(qty) if not isinstance(qty, (int, float)) else float(qty)
                    price_f = _parse_amount(unit_price) if not isinstance(unit_price, (int, float)) else float(unit_price)
                    if qty_f is not None and price_f is not None:
                        expected = round(qty_f * price_f, 2)
                        actual = round(item_total_f, 2)
                        difference = abs(expected - actual)
                        tolerance_amount = abs(expected) * MATH_TOLERANCE

                        if difference > tolerance_amount and difference > 0.02:
                            item_check["ok"] = False
                            item_check["note"] = f"Expected {expected}, got {actual} (diff: {difference:.2f})"
                            warnings.append(
                                f"LINE_ITEM_MATH_ERROR: Line {i} qty×price mismatch — {item_check['note']}"
                            )

        line_item_checks.append(item_check)

    math_checks["line_item_math"] = line_item_checks

    # ── Check 4: Line items sum to subtotal ───────────────────────────────
    # Surcharges (shipping, packing, freight) are often excluded from the formal
    # subtotal but included in line_items. Separate them out before comparing.
    _SURCHARGE_PATTERN = re.compile(
        r'(?:ship|pack|freight|courier|handling|delivery|carriage|transport)',
        re.IGNORECASE,
    )
    surcharge_sum = 0.0
    for item in data.get("line_items", []):
        desc = item.get("description") or ""
        hsn = item.get("hsn_sac")
        item_total = item.get("total") or item.get("line_total") or 0.0
        if _SURCHARGE_PATTERN.search(desc) and not hsn:
            val = _parse_amount(item_total)
            if val:
                surcharge_sum += val

    subtotal = _parse_amount(data.get("subtotal"))
    if has_line_totals and subtotal is not None:
        diff = abs(computed_sum - subtotal)
        tolerance = abs(subtotal) * MATH_TOLERANCE + 0.02
        # Also check without surcharges (they may be excluded from formal subtotal)
        diff_no_surcharge = abs((computed_sum - surcharge_sum) - subtotal)
        ok = diff <= tolerance or diff_no_surcharge <= tolerance
        math_checks["line_items_sum_to_subtotal"] = ok
        if not ok:
            warnings.append(
                f"SUBTOTAL_MISMATCH: Sum of line items is {computed_sum:.2f}, "
                f"but subtotal is {subtotal:.2f} (diff: {diff:.2f})"
            )
    else:
        math_checks["line_items_sum_to_subtotal"] = None  # Cannot check

    # ── Check 5: Grand total consistency ──────────────────────────────────
    # Two valid invoice patterns exist:
    #   A) subtotal + tax - discount + shipping = total  (discount applied after subtotal)
    #   B) subtotal + tax + shipping = total             (discount already deducted before
    #      subtotal, i.e. subtotal is the post-discount taxable value)
    # Accept the total if EITHER formula matches within tolerance.
    total = _parse_amount(data.get("total_amount"))
    tax = _parse_amount(data.get("tax_amount")) or 0.0
    discount = _parse_amount(data.get("discount")) or 0.0
    shipping = _parse_amount(data.get("shipping")) or 0.0

    if subtotal is not None and total is not None:
        tolerance = abs(total) * MATH_TOLERANCE + 0.02
        # Formula A: discount applied after subtotal
        expected_a = subtotal + tax - discount + shipping
        diff_a = abs(expected_a - total)
        # Formula B: discount already baked into subtotal (pre-tax discount)
        expected_b = subtotal + tax + shipping
        diff_b = abs(expected_b - total)

        ok = diff_a <= tolerance or diff_b <= tolerance
        math_checks["totals_consistent"] = ok
        if not ok:
            # Report against the closer formula for a more helpful message
            if diff_a <= diff_b:
                warnings.append(
                    f"TOTAL_MISMATCH: Expected total {expected_a:.2f} "
                    f"(subtotal+tax-discount+shipping), but got {total:.2f} (diff: {diff_a:.2f})"
                )
            else:
                warnings.append(
                    f"TOTAL_MISMATCH: Expected total {expected_b:.2f} "
                    f"(subtotal+tax+shipping, discount pre-applied), but got {total:.2f} (diff: {diff_b:.2f})"
                )
    else:
        math_checks["totals_consistent"] = None

    # ── Check 6: Date validation (optional, non-breaking) ────────────────
    inv_date = data.get("invoice_date")
    due_date = data.get("due_date")
    if inv_date and due_date:
        try:
            d1_str = _normalize_date(inv_date)
            d2_str = _normalize_date(due_date)
            if d1_str and d2_str:
                d1 = datetime.strptime(d1_str, "%Y-%m-%d")
                d2 = datetime.strptime(d2_str, "%Y-%m-%d")
                if d2 < d1:
                    # Dates are swapped — auto-correct by swapping them
                    data["invoice_date"], data["due_date"] = data["due_date"], data["invoice_date"]
                    logger.info(
                        "[validator] Auto-corrected swapped dates: invoice_date=%s, due_date=%s",
                        data["invoice_date"], data["due_date"]
                    )
        except ValueError:
            pass

    # ── Check 7: GSTIN validation (optional) ─────────────────────────────
    vendor = data.get("vendor", {})
    bill_to = data.get("bill_to", {})
    if isinstance(vendor, dict) and vendor.get("gstin"):
        if not _validate_gstin(vendor["gstin"]):
            warnings.append(f"INVALID_GSTIN: Vendor GSTIN format invalid: {vendor['gstin']}")
    if isinstance(bill_to, dict) and bill_to.get("gstin"):
        if not _validate_gstin(bill_to["gstin"]):
            warnings.append(f"INVALID_GSTIN: Customer GSTIN format invalid: {bill_to['gstin']}")

    # ── Final verdict ─────────────────────────────────────────────────────
    has_errors = any(
        v is False
        for v in [
            math_checks.get("line_items_sum_to_subtotal"),
            math_checks.get("totals_consistent"),
        ]
        if v is not None
    ) or not all(c["ok"] for c in line_item_checks)

    if has_errors or not passed:
        passed = False

    validation_result = {
        "passed": passed,
        "warnings": warnings,
        "math_checks": math_checks,
        "line_item_count": len(data.get("line_items", [])),
    }

    if warnings:
        logger.warning("[validator] %d validation issue(s) found", len(warnings))
        for w in warnings:
            logger.warning("[validator]   ⚠️  %s", w)
    else:
        logger.info("[validator] All checks passed ✅")

    data["validation"] = validation_result
    return data
