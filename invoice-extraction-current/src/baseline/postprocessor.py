"""
Post-Processor for Baseline Invoice Extraction.

After fields and line items are extracted, this module cleans,
normalizes, and validates the results.

POST-PROCESSING PIPELINE:
  1. DATE NORMALIZATION
     - Converts all dates to ISO format (YYYY-MM-DD)
     - Handles Indian date formats (DD/MM/YYYY), US (MM/DD/YYYY), ISO
     - Resolves ambiguous dates (e.g., 01/02/2026)

  2. AMOUNT NORMALIZATION
     - Removes currency symbols (₹, $, Rs.)
     - Standardizes to 2 decimal places
     - Handles Indian number format (12,34,567.89 → 1234567.89)

  3. TEXT CLEANUP
     - Trims whitespace, normalizes spaces
     - Removes control characters
     - Title-cases names

  4. CROSS-VALIDATION
     - Verifies: subtotal + tax ≈ total
     - Verifies: sum of line_totals ≈ subtotal or total
     - Verifies: qty × price ≈ line_total for each line item
     - Flags mismatches with confidence reduction

  5. CONFIDENCE SCORING
     - Adjusts confidence based on validation results
     - Fields that pass cross-validation get a boost
     - Fields that fail get reduced

WHY CROSS-VALIDATION MATTERS:
  OCR and regex extraction can make errors. Cross-validation catches
  mistakes like:
  - Misread digit: "5000" read as "8000" → sum doesn't match
  - Wrong label: "Subtotal" value assigned to "Total"
  - Missing tax: CGST extracted but SGST missed → tax too low

Author: ML Engineering Team
Date: 2026-02-19
Version: 3.0.0 (Baseline)
"""

import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from src.baseline.result import InvoiceResult, HEADER_FIELD_NAMES

logger = logging.getLogger("invoice_extraction.baseline.postprocessor")


# =============================================================================
# DATE PARSING CONFIGURATION
# =============================================================================
# Month name → number mapping (handles abbreviations and full names)
MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

# Date format patterns to try, in priority order
# Each entry: (regex, group_order, format_description)
DATE_PATTERNS = [
    # ISO: 2026-01-15
    (r"(\d{4})[/\-\.](\d{1,2})[/\-\.](\d{1,2})", "YMD"),
    # DD-Mon-YYYY: 15-Jan-2026
    (r"(\d{1,2})[/\-\.\s]+([A-Za-z]{3,9})[/\-\.\s,]+(\d{2,4})", "DMY_NAME"),
    # Mon DD, YYYY: January 15, 2026
    (r"([A-Za-z]{3,9})[/\-\.\s]+(\d{1,2})[/\-\.\s,]+(\d{2,4})", "MDY_NAME"),
    # DD/MM/YYYY (Indian format - preferred) or MM/DD/YYYY
    (r"(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})", "DMY_OR_MDY"),
]


# =============================================================================
# POST-PROCESSOR CLASS
# =============================================================================

class PostProcessor:
    """
    Cleans, normalizes, and validates extraction results.

    Usage:
        processor = PostProcessor()
        processor.process(result)

    After processing, the result's headers and line items will be cleaned,
    and validation_results will be populated with any issues found.
    """

    def __init__(self, config: Optional[Dict] = None):
        config = config or {}
        # Tolerance for cross-validation comparisons (5% default)
        self.tolerance = config.get("validation_tolerance", 0.05)
        # Whether to prefer DD/MM/YYYY (Indian) over MM/DD/YYYY (US)
        self.prefer_dmy = config.get("prefer_dmy", True)

    # =========================================================================
    # MAIN PROCESSING METHOD
    # =========================================================================

    def process(self, result: InvoiceResult) -> None:
        """
        Run all post-processing steps on the extraction result.

        Modifies the result in-place:
        - Normalizes dates, amounts, text
        - Runs cross-validation
        - Updates confidence scores
        - Adds validation results
        """
        logger.info("Running post-processing...")

        # Step 1: Normalize dates
        self._normalize_dates(result)

        # Step 2: Normalize amounts
        self._normalize_amounts(result)

        # Step 3: Clean text fields
        self._clean_text_fields(result)

        # Step 4: Cross-validation
        validations = self._cross_validate(result)
        result.validation_results = validations

        # Step 5: Adjust confidence
        self._adjust_confidence(result, validations)

        logger.info(f"Post-processing complete. {len(validations)} validation notes.")

    # =========================================================================
    # STEP 1: DATE NORMALIZATION
    # =========================================================================

    def _normalize_dates(self, result: InvoiceResult) -> None:
        """
        Normalize all date fields to ISO format (YYYY-MM-DD).
        """
        date_fields = ["invoice_date", "due_date"]

        for field_name in date_fields:
            header = result.get_header(field_name)
            if header and header.value:
                normalized = self._parse_date(header.value)
                if normalized:
                    header.value = normalized
                    logger.debug(f"Normalized {field_name}: {header.value} → {normalized}")

    def _parse_date(self, date_str: str) -> Optional[str]:
        """
        Parse a date string into ISO format (YYYY-MM-DD).

        Handles many formats:
        - 15/01/2026 → 2026-01-15 (DD/MM/YYYY, Indian)
        - 2026-01-15 → 2026-01-15 (already ISO)
        - January 15, 2026 → 2026-01-15
        - 15-Jan-2026 → 2026-01-15
        - 01/15/26 → 2026-01-15 (with 2-digit year)
        """
        date_str = date_str.strip()

        for pattern, format_type in DATE_PATTERNS:
            match = re.match(pattern, date_str)
            if not match:
                continue

            try:
                if format_type == "YMD":
                    year = int(match.group(1))
                    month = int(match.group(2))
                    day = int(match.group(3))

                elif format_type == "DMY_NAME":
                    day = int(match.group(1))
                    month_name = match.group(2).lower().rstrip(".")
                    month = MONTH_MAP.get(month_name)
                    if month is None:
                        continue
                    year = int(match.group(3))

                elif format_type == "MDY_NAME":
                    month_name = match.group(1).lower().rstrip(".")
                    month = MONTH_MAP.get(month_name)
                    if month is None:
                        continue
                    day = int(match.group(2))
                    year = int(match.group(3))

                elif format_type == "DMY_OR_MDY":
                    first = int(match.group(1))
                    second = int(match.group(2))
                    year = int(match.group(3))

                    # Resolve DD/MM vs MM/DD ambiguity
                    if self.prefer_dmy:
                        # Indian format: DD/MM/YYYY
                        day, month = first, second
                    else:
                        day, month = second, first

                    # If the preferred interpretation is invalid, try the other
                    if month > 12:
                        day, month = month, day
                    if day > 31:
                        continue

                else:
                    continue

                # Fix 2-digit years
                if year < 100:
                    year += 2000 if year < 50 else 1900

                # Validate the date
                dt = datetime(year, month, day)
                return dt.strftime("%Y-%m-%d")

            except (ValueError, TypeError):
                continue

        return None

    # =========================================================================
    # STEP 2: AMOUNT NORMALIZATION
    # =========================================================================

    def _normalize_amounts(self, result: InvoiceResult) -> None:
        """
        Normalize all amount fields to standard decimal format.
        """
        amount_fields = ["subtotal", "tax_amount", "total_amount"]

        for field_name in amount_fields:
            header = result.get_header(field_name)
            if header and header.value:
                normalized = self._parse_amount(header.value)
                if normalized is not None:
                    header.value = f"{normalized:.2f}"

        # Also normalize line item amounts
        for item in result.line_items:
            if item.quantity is not None:
                item.quantity = round(item.quantity, 3)
            if item.unit_price is not None:
                item.unit_price = round(item.unit_price, 2)
            if item.discount is not None:
                item.discount = round(item.discount, 2)
            if item.tax_amount is not None:
                item.tax_amount = round(item.tax_amount, 2)
            if item.line_total is not None:
                item.line_total = round(item.line_total, 2)

    def _parse_amount(self, amount_str: str) -> Optional[float]:
        """
        Parse an amount string into a float.

        Handles:
        - "₹1,234.56" → 1234.56
        - "Rs. 12,34,567.89" → 1234567.89 (Indian numbering)
        - "5000" → 5000.0
        - "$1,234" → 1234.0
        """
        if not amount_str:
            return None

        # Remove currency symbols and whitespace
        clean = re.sub(r"[₹$€£¥]", "", amount_str)
        clean = re.sub(r"(?i)rs\.?\s*", "", clean)
        clean = clean.strip()

        # Remove commas (handles both Western and Indian numbering)
        clean = clean.replace(",", "")

        try:
            return float(clean)
        except ValueError:
            return None

    # =========================================================================
    # STEP 3: TEXT CLEANUP
    # =========================================================================

    def _clean_text_fields(self, result: InvoiceResult) -> None:
        """
        Clean text-based fields (names, addresses, etc.).
        """
        text_fields = [
            "vendor_name", "vendor_address", "vendor_email", "vendor_phone",
            "customer_name", "customer_address",
        ]

        for field_name in text_fields:
            header = result.get_header(field_name)
            if header and header.value:
                cleaned = self._clean_text(header.value, field_name)
                header.value = cleaned

        # Clean line item descriptions
        for item in result.line_items:
            if item.description:
                item.description = self._clean_text(item.description, "description")

    def _clean_text(self, text: str, field_name: str) -> str:
        """
        Clean a text value.

        - Remove control characters
        - Normalize whitespace
        - Title-case names
        """
        # Remove control characters (newlines, tabs, etc.)
        text = re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", text)
        # Normalize multiple spaces to single
        text = re.sub(r"\s+", " ", text).strip()

        # Title-case for name fields
        if field_name in ("vendor_name", "customer_name"):
            # Don't title-case if it's all caps (might be intentional branding)
            if not text.isupper():
                text = text.title()

        # Lowercase for email
        if field_name == "vendor_email":
            text = text.lower()

        return text

    # =========================================================================
    # STEP 4: CROSS-VALIDATION
    # =========================================================================

    def _cross_validate(self, result: InvoiceResult) -> List[Dict[str, str]]:
        """
        Cross-validate extracted data for consistency.

        Returns a list of validation results, each containing:
        - "check": Name of the validation check
        - "status": "PASS", "FAIL", or "SKIP" (not enough data)
        - "message": Human-readable description
        """
        validations: List[Dict[str, str]] = []

        # Check 1: subtotal + tax ≈ total
        validations.append(self._check_total_consistency(result))

        # Check 2: sum of line_totals ≈ subtotal or total
        validations.append(self._check_line_items_sum(result))

        # Check 3: qty × price ≈ line_total for each item
        item_checks = self._check_line_item_math(result)
        validations.extend(item_checks)

        # Check 4: date consistency (due_date >= invoice_date)
        validations.append(self._check_date_order(result))

        # Check 5: GSTIN format validation
        validations.append(self._check_gstin_format(result))

        return validations

    def _check_total_consistency(self, result: InvoiceResult) -> Dict[str, str]:
        """
        Check: subtotal + tax_amount ≈ total_amount
        """
        subtotal = self._get_amount(result, "subtotal")
        tax = self._get_amount(result, "tax_amount")
        total = self._get_amount(result, "total_amount")

        if subtotal is None or total is None:
            return {
                "check": "total_consistency",
                "status": "SKIP",
                "message": "Missing subtotal or total - cannot verify",
            }

        if tax is None:
            tax = 0.0

        expected_total = subtotal + tax
        if total > 0:
            difference = abs(expected_total - total) / total
        else:
            difference = 1.0

        if difference <= self.tolerance:
            return {
                "check": "total_consistency",
                "status": "PASS",
                "message": (
                    f"subtotal({subtotal:.2f}) + tax({tax:.2f}) = "
                    f"{expected_total:.2f} ≈ total({total:.2f})"
                ),
            }
        else:
            return {
                "check": "total_consistency",
                "status": "FAIL",
                "message": (
                    f"MISMATCH: subtotal({subtotal:.2f}) + tax({tax:.2f}) = "
                    f"{expected_total:.2f} ≠ total({total:.2f}) "
                    f"[diff: {difference*100:.1f}%]"
                ),
            }

    def _check_line_items_sum(self, result: InvoiceResult) -> Dict[str, str]:
        """
        Check: sum of line item totals ≈ subtotal (or total if no subtotal)
        """
        if not result.line_items:
            return {
                "check": "line_items_sum",
                "status": "SKIP",
                "message": "No line items to validate",
            }

        line_sum = sum(
            item.line_total for item in result.line_items
            if item.line_total is not None
        )

        if line_sum == 0:
            return {
                "check": "line_items_sum",
                "status": "SKIP",
                "message": "Line items have no totals",
            }

        # Compare against subtotal first, then total
        target_name = "subtotal"
        target = self._get_amount(result, "subtotal")
        if target is None:
            target_name = "total_amount"
            target = self._get_amount(result, "total_amount")

        if target is None:
            return {
                "check": "line_items_sum",
                "status": "SKIP",
                "message": f"Line items sum = {line_sum:.2f} (no subtotal/total to compare)",
            }

        if target > 0:
            difference = abs(line_sum - target) / target
        else:
            difference = 1.0

        # Use a larger tolerance here since tax might be included
        tolerance = self.tolerance * 2  # Allow 10% for tax inclusion

        if difference <= tolerance:
            return {
                "check": "line_items_sum",
                "status": "PASS",
                "message": (
                    f"sum(line_totals) = {line_sum:.2f} ≈ "
                    f"{target_name}({target:.2f})"
                ),
            }
        else:
            return {
                "check": "line_items_sum",
                "status": "FAIL",
                "message": (
                    f"MISMATCH: sum(line_totals) = {line_sum:.2f} ≠ "
                    f"{target_name}({target:.2f}) [diff: {difference*100:.1f}%]"
                ),
            }

    def _check_line_item_math(self, result: InvoiceResult) -> List[Dict[str, str]]:
        """
        Check: qty × unit_price ≈ line_total for each line item.
        """
        checks = []

        for item in result.line_items:
            if item.quantity and item.unit_price and item.line_total:
                expected = item.quantity * item.unit_price
                actual = item.line_total
                if actual > 0:
                    diff = abs(expected - actual) / actual
                else:
                    diff = 1.0

                if diff <= self.tolerance:
                    status = "PASS"
                    msg = (
                        f"Line {item.line_number}: {item.quantity} × "
                        f"{item.unit_price:.2f} = {expected:.2f} ≈ {actual:.2f}"
                    )
                else:
                    status = "FAIL"
                    msg = (
                        f"Line {item.line_number}: {item.quantity} × "
                        f"{item.unit_price:.2f} = {expected:.2f} ≠ {actual:.2f} "
                        f"[diff: {diff*100:.1f}%]"
                    )

                checks.append({
                    "check": f"line_item_math_{item.line_number}",
                    "status": status,
                    "message": msg,
                })

        return checks

    def _check_date_order(self, result: InvoiceResult) -> Dict[str, str]:
        """
        Check: due_date >= invoice_date
        """
        inv_date_field = result.get_header("invoice_date")
        due_date_field = result.get_header("due_date")

        if not inv_date_field or not due_date_field:
            return {
                "check": "date_order",
                "status": "SKIP",
                "message": "Missing invoice date or due date",
            }

        try:
            inv_date = datetime.strptime(inv_date_field.value, "%Y-%m-%d")
            due_date = datetime.strptime(due_date_field.value, "%Y-%m-%d")
        except (ValueError, TypeError):
            return {
                "check": "date_order",
                "status": "SKIP",
                "message": "Dates not in parseable format",
            }

        if due_date >= inv_date:
            return {
                "check": "date_order",
                "status": "PASS",
                "message": (
                    f"due_date({due_date_field.value}) >= "
                    f"invoice_date({inv_date_field.value})"
                ),
            }
        else:
            return {
                "check": "date_order",
                "status": "FAIL",
                "message": (
                    f"due_date({due_date_field.value}) < "
                    f"invoice_date({inv_date_field.value}) - due date before invoice!"
                ),
            }

    def _check_gstin_format(self, result: InvoiceResult) -> Dict[str, str]:
        """
        Validate GSTIN format for Indian invoices.

        GSTIN format: DDAAAAA####A#ZA
        - DD = 2-digit state code (01-37)
        - AAAAA####A = 10-char PAN
        - # = entity number
        - Z = literal 'Z'
        - A = check digit
        """
        gstin_fields = ["vendor_gstin", "customer_gstin"]
        issues = []

        for field_name in gstin_fields:
            header = result.get_header(field_name)
            if header and header.value:
                gstin = header.value
                # Full GSTIN validation pattern
                pattern = r"^(\d{2})[A-Z]{5}\d{4}[A-Z][A-Z0-9][Z][A-Z0-9]$"
                if re.match(pattern, gstin):
                    # Check state code (01-37 for Indian states)
                    state_code = int(gstin[:2])
                    if 1 <= state_code <= 37:
                        continue
                    else:
                        issues.append(f"{field_name}: invalid state code {state_code}")
                else:
                    issues.append(f"{field_name}: invalid format '{gstin}'")

        if not issues:
            has_gstin = any(
                result.get_header(f) and result.get_header(f).value
                for f in gstin_fields
            )
            return {
                "check": "gstin_format",
                "status": "PASS" if has_gstin else "SKIP",
                "message": "GSTIN format valid" if has_gstin else "No GSTIN found",
            }
        else:
            return {
                "check": "gstin_format",
                "status": "FAIL",
                "message": "; ".join(issues),
            }

    # =========================================================================
    # STEP 5: CONFIDENCE ADJUSTMENT
    # =========================================================================

    def _adjust_confidence(
        self,
        result: InvoiceResult,
        validations: List[Dict[str, str]],
    ) -> None:
        """
        Adjust confidence scores based on validation results.

        - Fields that pass cross-validation get a confidence boost
        - Fields that fail get reduced confidence
        """
        # Count passes and fails
        passes = sum(1 for v in validations if v["status"] == "PASS")
        fails = sum(1 for v in validations if v["status"] == "FAIL")

        # If total consistency passes, boost amount fields
        total_check = next(
            (v for v in validations if v["check"] == "total_consistency"), None
        )
        if total_check:
            amount_fields = ["subtotal", "tax_amount", "total_amount"]
            for field_name in amount_fields:
                header = result.get_header(field_name)
                if header:
                    if total_check["status"] == "PASS":
                        # Boost by up to 10 points
                        header.confidence = min(100.0, header.confidence + 10.0)
                        header.uncertain = False
                    elif total_check["status"] == "FAIL":
                        # Reduce by up to 15 points
                        header.confidence = max(20.0, header.confidence - 15.0)
                        header.uncertain = True

        # If line item math passes, boost item confidence
        for validation in validations:
            if validation["check"].startswith("line_item_math_"):
                try:
                    line_num = int(validation["check"].split("_")[-1])
                    for item in result.line_items:
                        if item.line_number == line_num:
                            if validation["status"] == "PASS":
                                item.confidence = min(100.0, item.confidence + 10.0)
                            elif validation["status"] == "FAIL":
                                item.confidence = max(20.0, item.confidence - 15.0)
                except (ValueError, IndexError):
                    pass

    # =========================================================================
    # UTILITY
    # =========================================================================

    def _get_amount(self, result: InvoiceResult, field_name: str) -> Optional[float]:
        """Get an amount field as a float, or None."""
        header = result.get_header(field_name)
        if header and header.value:
            try:
                return float(header.value.replace(",", ""))
            except (ValueError, TypeError):
                return None
        return None
