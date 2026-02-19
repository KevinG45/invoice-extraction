"""
Table & Line Item Extractor for Baseline Invoice Extraction.

Extracts line items (product rows) from invoices using two approaches:

  APPROACH 1: PDFPLUMBER TABLE DETECTION (Digital PDFs)
    - pdfplumber can detect tables in PDFs using ruling lines or spacing
    - Extracts perfectly formatted rows with columns already separated
    - This is the MOST ACCURATE method for digital PDFs

  APPROACH 2: TEXT-BASED TABLE PARSING (OCR Text / Any Source)
    - Uses regex to find rows that look like table data
    - Identifies table header row first, then parses subsequent rows
    - Works with OCR output from Tesseract
    - Less accurate but works with any text source

TABLE STRUCTURE (typical Indian GST invoice):
  ┌────┬──────────────┬──────┬─────┬────────┬──────┬──────┬──────┬────────┐
  │ No │ Description  │ HSN  │ Qty │ Rate   │ Disc │ CGST │ SGST │ Amount │
  ├────┼──────────────┼──────┼─────┼────────┼──────┼──────┼──────┼────────┤
  │ 1  │ Widget A     │ 8471 │ 10  │ 500.00 │ 5%   │ 9%   │ 9%   │ 5000   │
  │ 2  │ Widget B     │ 8472 │ 5   │ 300.00 │ 0%   │ 9%   │ 9%   │ 1500   │
  └────┴──────────────┴──────┴─────┴────────┴──────┴──────┴──────┴────────┘

Column names vary across invoices but typically include:
  - S.No / Sr. / # / Sl.
  - Description / Particulars / Item / Product / Service
  - HSN / SAC (Indian GST product codes)
  - Qty / Quantity / Nos
  - Rate / Price / Unit Price / MRP
  - Discount / Disc
  - Tax Rate / GST / CGST / SGST / IGST
  - Tax Amount
  - Amount / Total / Net Amount / Value

Author: ML Engineering Team
Date: 2026-02-19
Version: 3.0.0 (Baseline)
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from src.baseline.result import InvoiceResult, LineItem

logger = logging.getLogger("invoice_extraction.baseline.table_extractor")


# =============================================================================
# COLUMN HEADER KEYWORDS
# =============================================================================
# Maps internal field names to possible column header texts.
# Used to identify which column contains which data.

COLUMN_KEYWORDS = {
    "serial": [
        "s.no", "sr.no", "sr no", "sno", "sl", "sl.no", "sl no",
        "#", "no.", "no", "item no", "line",
    ],
    "item_code": [
        "item code", "product code", "part no", "sku", "code",
        "material code", "catalogue",
    ],
    "description": [
        "description", "particulars", "item", "product", "service",
        "goods", "material", "name of product", "name of service",
        "items", "details", "commodity",
    ],
    "hsn_sac": [
        "hsn", "sac", "hsn/sac", "hsn code", "sac code",
        "hsn/sac code", "tariff",
    ],
    "quantity": [
        "qty", "quantity", "nos", "units", "pcs", "pieces", "no of",
        "number", "count",
    ],
    "unit_price": [
        "rate", "price", "unit price", "mrp", "unit rate", "rate/unit",
        "price/unit", "unit cost", "per unit",
    ],
    "discount": [
        "discount", "disc", "disc%", "discount%", "rebate",
    ],
    "tax_rate": [
        "gst", "gst%", "tax rate", "tax%", "cgst", "sgst", "igst",
        "vat", "vat%", "rate of tax", "tax rate%",
    ],
    "tax_amount": [
        "tax amount", "tax amt", "gst amount", "gst amt",
        "cgst amt", "sgst amt", "igst amt", "tax value",
    ],
    "line_total": [
        "amount", "total", "net amount", "value", "net value",
        "total amount", "line total", "amt", "net amt",
        "taxable value", "taxable amount", "assessable value",
    ],
}


# =============================================================================
# TABLE EXTRACTOR CLASS
# =============================================================================

class TableExtractor:
    """
    Extracts line items (product/service rows) from invoices.

    Usage:
        extractor = TableExtractor()
        result = InvoiceResult()

        # For digital PDFs with pre-extracted tables:
        extractor.extract_from_tables(result, pdfplumber_tables)

        # For OCR text:
        extractor.extract_from_text(result, full_text)
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {}
        # Minimum number of columns to consider a row as table data
        self.min_columns = config.get("min_columns", 3)
        # Minimum number of rows to consider a valid table
        self.min_rows = config.get("min_rows", 1)

    # =========================================================================
    # MAIN EXTRACTION METHOD
    # =========================================================================

    def extract_line_items(
        self,
        result: InvoiceResult,
        full_text: str,
        tables: Optional[List[List[List[Optional[str]]]]] = None,
    ) -> None:
        """
        Extract line items using the best available method.

        Args:
            result: InvoiceResult to populate with line items.
            full_text: Full text of the invoice.
            tables: Optional pdfplumber tables (list of tables,
                     each table is a list of rows,
                     each row is a list of cell values).
        """
        # Strategy 1: pdfplumber tables (most accurate for digital PDFs)
        if tables:
            logger.info(f"Extracting line items from {len(tables)} table(s)...")
            items = self._extract_from_pdfplumber_tables(tables)
            if items:
                for item in items:
                    result.add_line_item(item)
                logger.info(f"Extracted {len(items)} line items from pdfplumber tables")
                return

        # Strategy 2: Text-based parsing (fallback for OCR text)
        if full_text.strip():
            logger.info("Extracting line items from text (regex-based)...")
            items = self._extract_from_text(full_text)
            if items:
                for item in items:
                    result.add_line_item(item)
                logger.info(f"Extracted {len(items)} line items from text")
                return

        logger.warning("No line items could be extracted")

    # =========================================================================
    # STRATEGY 1: PDFPLUMBER TABLE EXTRACTION
    # =========================================================================

    def _extract_from_pdfplumber_tables(
        self,
        tables: List[List[List[Optional[str]]]],
    ) -> List[LineItem]:
        """
        Extract line items from pdfplumber-detected tables.

        pdfplumber returns tables as:
          [
            [['S.No', 'Description', 'Qty', 'Rate', 'Amount'],   # header
             ['1',    'Widget A',    '10',  '500',  '5000'],      # row 1
             ['2',    'Widget B',    '5',   '300',  '1500']],     # row 2
          ]

        This method:
        1. Identifies the header row (matches column keywords)
        2. Maps columns to internal field names
        3. Parses each data row into a LineItem
        """
        all_items: List[LineItem] = []

        for table_idx, table in enumerate(tables):
            if not table or len(table) < 2:
                continue

            # Find the header row (contains column names)
            header_row_idx, column_map = self._find_header_row(table)
            if header_row_idx is None:
                logger.debug(f"Table {table_idx}: No header row found, trying heuristic")
                column_map = self._guess_columns(table)
                header_row_idx = 0  # Assume first row is header

            if not column_map:
                logger.debug(f"Table {table_idx}: Could not map columns, skipping")
                continue

            logger.debug(
                f"Table {table_idx}: Header at row {header_row_idx}, "
                f"columns: {column_map}"
            )

            # Parse data rows
            line_number = 1
            for row_idx in range(header_row_idx + 1, len(table)):
                row = table[row_idx]
                if not row or all(cell is None or str(cell).strip() == "" for cell in row):
                    continue

                item = self._parse_table_row(row, column_map, line_number)
                if item:
                    all_items.append(item)
                    line_number += 1

        return all_items

    def _find_header_row(
        self,
        table: List[List[Optional[str]]],
    ) -> Tuple[Optional[int], Dict[str, int]]:
        """
        Find the table header row by matching keywords.

        Returns:
            (header_row_index, column_mapping) or (None, {}).
            column_mapping maps field names to column indices.
        """
        for row_idx, row in enumerate(table):
            if row_idx > 5:  # Header should be in first 5 rows
                break

            column_map = {}
            for col_idx, cell in enumerate(row):
                if cell is None:
                    continue
                cell_text = str(cell).strip().lower()
                if not cell_text:
                    continue

                # Try to match this cell to a known column type
                for field_name, keywords in COLUMN_KEYWORDS.items():
                    for keyword in keywords:
                        if keyword in cell_text or cell_text in keyword:
                            # Avoid duplicate field mappings - take the first match
                            if field_name not in column_map:
                                column_map[field_name] = col_idx
                            break

            # A valid header should have at least 3 recognized columns
            # and MUST include either description or line_total
            if (len(column_map) >= 3 and
                    ("description" in column_map or "line_total" in column_map)):
                return row_idx, column_map

        return None, {}

    def _guess_columns(
        self,
        table: List[List[Optional[str]]],
    ) -> Dict[str, int]:
        """
        Heuristic column mapping when no header row is found.

        Analyzes data patterns:
        - Short numbers → serial
        - Long text → description
        - Small integers → quantity
        - Decimal numbers → prices/amounts
        - Largest number → line_total
        """
        if not table or len(table) < 2:
            return {}

        # Use the first few data rows to analyze patterns
        sample_rows = table[:min(5, len(table))]
        num_cols = max(len(row) for row in sample_rows if row)

        column_map = {}

        # Analyze each column
        for col_idx in range(num_cols):
            values = []
            for row in sample_rows:
                if row and col_idx < len(row) and row[col_idx]:
                    values.append(str(row[col_idx]).strip())

            if not values:
                continue

            # Check if column is mostly numeric
            numeric_count = sum(
                1 for v in values
                if re.match(r"^[\d,]+\.?\d*$", v.replace(",", ""))
            )
            is_numeric = numeric_count > len(values) * 0.6

            # Check if column has long text (descriptions)
            avg_length = sum(len(v) for v in values) / len(values)

            if not is_numeric and avg_length > 15:
                column_map["description"] = col_idx
            elif is_numeric and avg_length < 4:
                if "serial" not in column_map:
                    column_map["serial"] = col_idx
                elif "quantity" not in column_map:
                    column_map["quantity"] = col_idx
            elif is_numeric:
                if "line_total" not in column_map:
                    column_map["line_total"] = col_idx
                elif "unit_price" not in column_map:
                    column_map["unit_price"] = col_idx

        return column_map

    def _parse_table_row(
        self,
        row: List[Optional[str]],
        column_map: Dict[str, int],
        line_number: int,
    ) -> Optional[LineItem]:
        """
        Parse a single table row into a LineItem.

        Skips rows that appear to be:
        - Sub-totals, totals, or summary rows
        - Empty rows or separator lines
        """
        # Check if this is a summary/total row (skip these)
        row_text = " ".join(str(c) for c in row if c).lower()
        skip_keywords = [
            "total", "subtotal", "sub total", "grand total",
            "tax", "cgst", "sgst", "igst", "round off",
            "net amount", "amount in words", "balance",
        ]
        if any(kw in row_text for kw in skip_keywords):
            return None

        item = LineItem(line_number=line_number)

        # Extract each field from the row
        for field_name, col_idx in column_map.items():
            if col_idx >= len(row) or row[col_idx] is None:
                continue

            cell_value = str(row[col_idx]).strip()
            if not cell_value:
                continue

            # Map to LineItem attributes
            if field_name == "description":
                item.description = cell_value
            elif field_name == "item_code":
                item.item_code = cell_value
            elif field_name == "hsn_sac":
                item.hsn_sac = cell_value
            elif field_name == "quantity":
                item.quantity = self._parse_number(cell_value)
            elif field_name == "unit_price":
                item.unit_price = self._parse_number(cell_value)
            elif field_name == "discount":
                item.discount = self._parse_number(cell_value)
            elif field_name == "tax_rate":
                item.tax_rate = self._parse_number(cell_value)
            elif field_name == "tax_amount":
                item.tax_amount = self._parse_number(cell_value)
            elif field_name == "line_total":
                item.line_total = self._parse_number(cell_value)

        # Validate: must have at least a description or an amount
        if item.description or item.line_total:
            # Calculate confidence
            item.confidence = self._item_confidence(item)
            return item

        return None

    # =========================================================================
    # STRATEGY 2: TEXT-BASED TABLE PARSING
    # =========================================================================

    def _extract_from_text(self, full_text: str) -> List[LineItem]:
        """
        Extract line items from raw text (OCR or plain text).

        Approach:
        1. Find the table region in the text (between header row and totals)
        2. Split into lines
        3. Parse each line that looks like a data row
        """
        lines = full_text.split("\n")

        # Step 1: Find the table start (header row)
        table_start = self._find_table_start(lines)
        if table_start is None:
            logger.debug("Could not find table header in text")
            return []

        # Step 2: Find the table end (totals/summary section)
        table_end = self._find_table_end(lines, table_start)

        # Step 3: Parse data rows between start and end
        items: List[LineItem] = []
        line_number = 1

        for line_idx in range(table_start + 1, table_end):
            line = lines[line_idx].strip()
            if not line:
                continue

            # Skip separator lines (e.g., "---" or "===")
            if re.match(r"^[\-=_\+\|]+$", line):
                continue

            # Try to parse as a line item
            item = self._parse_text_row(line, line_number)
            if item:
                items.append(item)
                line_number += 1

        return items

    def _find_table_start(self, lines: List[str]) -> Optional[int]:
        """
        Find the index of the table header row in text lines.

        Looks for a line containing multiple column keywords.
        """
        # Flatten all keywords for matching
        header_keywords = set()
        for keywords in COLUMN_KEYWORDS.values():
            header_keywords.update(keywords)

        for idx, line in enumerate(lines):
            line_lower = line.lower()
            # Count how many column keywords appear in this line
            match_count = sum(1 for kw in header_keywords if kw in line_lower)
            if match_count >= 3:
                return idx

        # Fallback: look for common patterns (like "S.No" + "Description")
        for idx, line in enumerate(lines):
            line_lower = line.lower()
            if (("description" in line_lower or "particulars" in line_lower) and
                    ("qty" in line_lower or "rate" in line_lower or
                     "amount" in line_lower or "quantity" in line_lower)):
                return idx

        return None

    def _find_table_end(self, lines: List[str], start: int) -> int:
        """
        Find where the table data ends.

        Returns the index of the first line after `start` that contains
        total/summary keywords, or the end of the text.
        """
        end_keywords = [
            "total", "subtotal", "sub total", "grand total",
            "amount in words", "net amount payable", "notes",
            "terms and conditions", "bank details", "payment",
        ]

        # Start looking from 2+ rows after header (skip at least 1 data row)
        for idx in range(start + 2, len(lines)):
            line_lower = lines[idx].strip().lower()

            # Check end keywords, but only if the line starts with the keyword
            # (to avoid matching "Total" in the middle of a description)
            for kw in end_keywords:
                if line_lower.startswith(kw):
                    return idx

            # Also stop if we hit a blank section (2+ consecutive blank lines)
            if not line_lower and idx + 1 < len(lines):
                next_line = lines[idx + 1].strip()
                if not next_line:
                    return idx

        return len(lines)

    def _parse_text_row(self, line: str, line_number: int) -> Optional[LineItem]:
        """
        Parse a single text line as a line item.

        Uses multiple regex patterns to handle different formats:

        Pattern 1: Numbered row with description and amounts
          "1    Widget A    10    500.00    5000.00"
          "1. Widget A  HSN8471  10 Pcs  500.00  5000.00"

        Pattern 2: Description with amounts
          "Widget A    10    500.00    5000.00"
        """
        # Skip if too short
        if len(line) < 10:
            return None

        # Skip total/summary lines
        line_lower = line.lower()
        skip_terms = [
            "total", "subtotal", "sub total", "cgst", "sgst", "igst",
            "round off", "balance", "amount in words", "bank detail",
            "terms", "note", "payment",
        ]
        if any(line_lower.strip().startswith(t) for t in skip_terms):
            return None

        item = LineItem(line_number=line_number)

        # Extract description: the longest non-numeric segment
        # Split the line by multiple spaces or tabs
        parts = re.split(r"\s{2,}|\t", line)
        parts = [p.strip() for p in parts if p.strip()]

        if not parts:
            return None

        # Find numbers in the line (for quantity, price, amount)
        numbers = self._extract_numbers_from_line(line)

        # Identify description vs numeric parts
        text_parts = []
        for part in parts:
            clean = part.replace(",", "").replace(".", "").strip()
            if clean and not clean.replace(".", "").replace(",", "").isdigit():
                # Check if it's not just a serial number
                if not re.match(r"^\d{1,3}\.?$", part):
                    text_parts.append(part)

        # Set description as the longest text part
        if text_parts:
            item.description = " ".join(text_parts)
        elif len(parts) > 1:
            item.description = parts[1] if len(parts) > 1 else parts[0]

        # Assign numbers to fields
        # Heuristic: the LAST number is usually line_total (amount)
        #            if there are 3+ numbers: qty, rate, amount
        if len(numbers) >= 3:
            # Common pattern: quantity, unit_price, ..., line_total
            item.quantity = numbers[0]
            item.unit_price = numbers[1]
            item.line_total = numbers[-1]

            # If there are more numbers, they might be tax-related
            if len(numbers) >= 4:
                item.tax_amount = numbers[-2]

        elif len(numbers) == 2:
            # Could be qty+amount or rate+amount
            if numbers[0] < 1000 and numbers[1] > numbers[0]:
                item.quantity = numbers[0]
                item.line_total = numbers[1]
            else:
                item.unit_price = numbers[0]
                item.line_total = numbers[1]

        elif len(numbers) == 1:
            item.line_total = numbers[0]

        # Check for HSN/SAC code
        hsn_match = re.search(r"\b(\d{4,8})\b", line)
        if hsn_match:
            candidate = hsn_match.group(1)
            # HSN codes are typically 4, 6, or 8 digits
            if len(candidate) in (4, 6, 8):
                item.hsn_sac = candidate

        # Validate: must have description or amount
        if not item.description and not item.line_total:
            return None

        item.confidence = self._item_confidence(item)
        return item

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def _parse_number(self, value: str) -> Optional[float]:
        """
        Parse a string into a float, handling commas and percentage signs.

        Examples:
          "1,234.56" → 1234.56
          "18%"      → 18.0
          "10 Pcs"   → 10.0
          "₹500"     → 500.0
        """
        if not value:
            return None

        # Remove currency symbols, ₹, $, etc.
        clean = re.sub(r"[₹$€£¥Rs\.?\s]", "", value)
        # Remove percentage sign
        clean = clean.replace("%", "")
        # Remove commas
        clean = clean.replace(",", "")
        # Remove non-numeric suffixes (like "Pcs", "Nos", etc.)
        clean = re.sub(r"[A-Za-z]+$", "", clean).strip()

        try:
            return float(clean)
        except (ValueError, TypeError):
            return None

    def _extract_numbers_from_line(self, line: str) -> List[float]:
        """
        Extract all numeric values from a line of text.

        Handles: 1234, 1,234, 1234.56, 1,234.56, etc.
        Ignores: years (2024-2026), serial numbers less than 1000
        """
        # Pattern: optional currency symbol, digits with optional commas and decimals
        number_pattern = r"(?<![A-Za-z])(\d[\d,]*\.?\d*)(?![A-Za-z/\-])"
        matches = re.findall(number_pattern, line)

        numbers = []
        for match in matches:
            clean = match.replace(",", "")
            try:
                num = float(clean)
                # Skip if it looks like a year (2020-2030 range)
                if 2020 <= num <= 2030 and "." not in match:
                    continue
                # Skip very small serial numbers (1, 2, 3...)
                # unless they could be quantities
                if num > 0:
                    numbers.append(num)
            except ValueError:
                pass

        return numbers

    def _item_confidence(self, item: LineItem) -> float:
        """
        Calculate confidence score for a line item.

        Higher confidence when:
        - More fields are populated
        - Quantity × Unit Price ≈ Line Total (math checks out)
        - Description is present and reasonable length
        """
        score = 50.0  # Base score

        # Boost for populated fields
        if item.description:
            score += 10.0
        if item.quantity:
            score += 5.0
        if item.unit_price:
            score += 5.0
        if item.line_total:
            score += 10.0
        if item.hsn_sac:
            score += 5.0

        # Big boost if math checks out: qty × price ≈ total
        if item.quantity and item.unit_price and item.line_total:
            expected = item.quantity * item.unit_price
            actual = item.line_total
            if actual > 0:
                ratio = abs(expected - actual) / actual
                if ratio < 0.01:       # Within 1% → perfect match
                    score += 15.0
                elif ratio < 0.05:     # Within 5% → good match
                    score += 10.0
                elif ratio < 0.15:     # Within 15% → acceptable (tax/discount)
                    score += 5.0

        return min(score, 100.0)
