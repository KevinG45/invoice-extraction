"""
Table Extractor — extracts structured line-item tables from invoices.

Strategy selection by pdf_type:
    - "digital"  → Camelot (lattice → stream) → Tabula fallback
    - "scanned"  → PaddleOCR PPStructure (PDF pages → images → OCR)
    - "image"    → PaddleOCR PPStructure (direct image input)

RULES:
    - Camelot is NEVER used on scanned PDFs or images (vector-only).
    - Returns [] (never crashes) if no tables found or file is missing.
    - All outputs are plain dicts/lists — no raw library objects.
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.config import (
    CAMELOT_FLAVOR_BORDERED,
    CAMELOT_FLAVOR_BORDERLESS,
    TABLE_CONFIDENCE_THRESHOLD,
    USE_GPU,
)

logger = logging.getLogger(__name__)


def clean_ocr_number(raw: str) -> str:
    """
    Cleans OCR-garbled numeric strings.
    Removes spaces within numbers.
    Replaces common OCR character substitutions.
    Returns a clean string suitable for float().
    """
    if raw is None:
        return "0"
    # Remove spaces between digits
    cleaned = re.sub(r'(?<=\d) (?=\d)', '', str(raw))
    # Replace common OCR letter-for-digit errors
    cleaned = cleaned.replace('O', '0')
    cleaned = cleaned.replace('o', '0')
    cleaned = cleaned.replace('l', '1')
    cleaned = cleaned.replace('I', '1')
    cleaned = cleaned.replace('S', '5')
    # Remove any remaining non-numeric characters except decimal point and minus sign
    cleaned = re.sub(r'[^\d.\-]', '', cleaned)
    # Handle empty result
    if cleaned == '' or cleaned == '.':
        return "0"
    return cleaned


# ── Column header keyword mapping ──────────────────────────────────────────
COLUMN_KEYWORDS = {
    "serial": ["s.no", "sl.no", "sr.no", "sno", "sl", "#", "no.", "serial"],
    "item_code": ["item code", "sku", "code", "part no", "product code", "item no"],
    "description": ["description", "particulars", "item", "product", "goods",
                     "service", "details", "name of product"],
    "hsn_sac": ["hsn", "sac", "hsn/sac", "hsn code", "sac code"],
    "quantity": ["qty", "quantity", "pcs", "units", "nos", "no.s"],
    "unit_price": ["rate", "price", "unit price", "mrp", "unit rate", "price/unit"],
    "discount": ["disc", "discount", "disc%", "discount%"],
    "tax_rate": ["tax%", "tax rate", "gst%", "gst rate", "rate%", "cgst%", "sgst%", "igst%"],
    "tax_amount": ["tax amt", "tax amount", "gst", "cgst", "sgst", "igst", "tax"],
    "amount": ["amount", "total", "value", "net amount", "line total", "total amount"],
}


# ═══════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════

def extract_tables(path: str, pdf_type: str) -> List[Dict[str, Any]]:
    """
    Extract tables from a PDF or image based on the file type.

    Args:
        path: file path (PDF or image).
        pdf_type: "digital" | "scanned" | "image".

    Returns:
        list of table dicts, each containing:
        {"rows": [[cell,...], ...], "shape": (rows, cols), "page": int, "method": str}
    """
    path_obj = Path(path)
    logger.info("[table_extractor] Extracting tables from %s (type: %s)", path_obj.name, pdf_type)

    if pdf_type == "digital":
        tables = _extract_with_pdfplumber(str(path_obj))
        if not tables:
            logger.info("[table_extractor] pdfplumber found nothing, trying Camelot")
            tables = _extract_with_camelot(str(path_obj))
        if not tables:
            logger.info("[table_extractor] Camelot found nothing, trying tabula fallback")
            tables = _extract_with_tabula(str(path_obj))
        return tables

    elif pdf_type in ("scanned", "image"):
        return _extract_with_ppstructure(str(path_obj), pdf_type)

    else:
        logger.warning("[table_extractor] Unknown pdf_type '%s', skipping table extraction", pdf_type)
        return []


# ── Legacy wrapper for backward compatibility ─────────────────────────────

def extract_tables_from_pdf(path: str) -> List[List[List[str]]]:
    """
    Extract raw tables from a digital PDF using pdfplumber (legacy helper).

    Returns list of tables, each a list of rows (list of cell strings).
    """
    tables = []
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                page_tables = page.extract_tables() or []
                for table in page_tables:
                    if table and len(table) > 1:
                        cleaned = []
                        for row in table:
                            cleaned.append([str(cell).strip() if cell else "" for cell in row])
                        tables.append(cleaned)
        logger.info("Extracted %d tables from PDF '%s'", len(tables), path)
    except Exception as e:
        logger.warning("pdfplumber table extraction failed: %s", e)
    return tables


# ═══════════════════════════════════════════════════════════════════════════
# PRIVATE — PDFPLUMBER (digital PDFs, primary method)
# ═══════════════════════════════════════════════════════════════════════════

def _extract_with_pdfplumber(pdf_path: str) -> List[Dict[str, Any]]:
    """Use pdfplumber to extract tables from a digital PDF."""
    try:
        import pdfplumber
    except ImportError:
        logger.error("[table_extractor] pdfplumber not installed")
        return []

    tables: List[Dict[str, Any]] = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                page_tables = page.extract_tables() or []
                for raw_table in page_tables:
                    if not raw_table or len(raw_table) < 2:
                        continue
                    rows = []
                    for row in raw_table:
                        cleaned_row = [str(cell).strip() if cell else "" for cell in row]
                        rows.append(cleaned_row)
                    tables.append({
                        "rows": rows,
                        "shape": (len(rows), len(rows[0]) if rows else 0),
                        "page": page_num,
                        "method": "pdfplumber",
                        "accuracy": None,
                    })
        logger.info("[table_extractor] pdfplumber found %d tables", len(tables))
    except Exception as e:
        logger.warning("[table_extractor] pdfplumber table extraction failed: %s", e)

    return tables


# ═══════════════════════════════════════════════════════════════════════════
# PRIVATE — CAMELOT (digital PDFs only)
# ═══════════════════════════════════════════════════════════════════════════

def _extract_with_camelot(pdf_path: str) -> List[Dict[str, Any]]:
    """Use Camelot to extract tables from a digital PDF."""
    try:
        import camelot
    except ImportError:
        logger.error("[table_extractor] camelot not installed")
        return []

    tables: List[Dict[str, Any]] = []

    # Try lattice first (bordered tables)
    try:
        logger.info("[table_extractor] Trying Camelot lattice mode...")
        raw = camelot.read_pdf(pdf_path, flavor=CAMELOT_FLAVOR_BORDERED, pages="all")
        for t in raw:
            if t.accuracy >= TABLE_CONFIDENCE_THRESHOLD * 100:
                rows = t.df.values.tolist()
                tables.append({
                    "rows": rows,
                    "shape": tuple(t.df.shape),
                    "page": t.page,
                    "method": "camelot_lattice",
                    "accuracy": t.accuracy,
                })
        logger.info("[table_extractor] Camelot lattice found %d tables", len(tables))
    except Exception as e:
        logger.warning("[table_extractor] Camelot lattice failed: %s", e)

    # If nothing found, try stream (borderless tables)
    if not tables:
        try:
            logger.info("[table_extractor] Trying Camelot stream mode...")
            raw = camelot.read_pdf(pdf_path, flavor=CAMELOT_FLAVOR_BORDERLESS, pages="all")
            for t in raw:
                if t.accuracy >= TABLE_CONFIDENCE_THRESHOLD * 100:
                    rows = t.df.values.tolist()
                    tables.append({
                        "rows": rows,
                        "shape": tuple(t.df.shape),
                        "page": t.page,
                        "method": "camelot_stream",
                        "accuracy": t.accuracy,
                    })
            logger.info("[table_extractor] Camelot stream found %d tables", len(tables))
        except Exception as e:
            logger.warning("[table_extractor] Camelot stream failed: %s", e)

    return tables


# ═══════════════════════════════════════════════════════════════════════════
# PRIVATE — TABULA FALLBACK
# ═══════════════════════════════════════════════════════════════════════════

def _extract_with_tabula(pdf_path: str) -> List[Dict[str, Any]]:
    """Fallback: use tabula-py for table extraction from digital PDFs."""
    try:
        import tabula
    except ImportError:
        logger.error("[table_extractor] tabula not installed")
        return []

    tables: List[Dict[str, Any]] = []
    try:
        dfs = tabula.read_pdf(pdf_path, pages="all", multiple_tables=True, silent=True)
        for i, df in enumerate(dfs):
            if df.empty:
                continue
            rows = df.fillna("").values.tolist()
            headers = [str(c) for c in df.columns]
            tables.append({
                "rows": [headers] + rows,
                "shape": (df.shape[0] + 1, df.shape[1]),  # include header row
                "page": i + 1,
                "method": "tabula",
                "accuracy": None,
            })
        logger.info("[table_extractor] Tabula found %d tables", len(tables))
    except Exception as e:
        logger.warning("[table_extractor] Tabula failed: %s", e)

    return tables


# ═══════════════════════════════════════════════════════════════════════════
# PRIVATE — PPSTRUCTURE (scanned / image)
# ═══════════════════════════════════════════════════════════════════════════

def _extract_with_ppstructure(path: str, input_type: str) -> List[Dict[str, Any]]:
    """
    Use PaddleOCR's PPStructure to extract tables from scanned PDFs or images.
    For scanned PDFs, converts each page to an image first.
    """
    # PPStructure (paddleocr) is NOT installed.
    # Image table extraction uses regex fallback.
    # To enable: pip install paddleocr>=2.7.0
    # Note: large install approximately 2GB.
    # Regex fallback is functional but less accurate
    # for complex table layouts.
    # IMPORTANT: paddlepaddle backend requires Python <=3.12.
    # paddleocr 3.x renamed PPStructure to PPStructureV3.
    try:
        try:
            from paddleocr import PPStructureV3 as PPStructure  # paddleocr 3.x
        except ImportError:
            from paddleocr import PPStructure  # paddleocr 2.x
        import numpy as np
        from PIL import Image
    except ImportError as e:
        logger.error("[table_extractor] PPStructure import failed: %s", e)
        return []

    tables: List[Dict[str, Any]] = []

    try:
        table_engine = PPStructure(
            show_log=False,
            image_orientation=True,
            return_ocr_result_in_table=True,
        )

        if input_type == "image":
            images = [Image.open(path).convert("RGB")]
        else:
            # Scanned PDF → convert pages to images
            from pdf2image import convert_from_path
            images = convert_from_path(path, dpi=200)

        for page_num, img in enumerate(images, start=1):
            img_array = np.array(img)
            try:
                result = table_engine(img_array)
                for region in result:
                    if region.get("type", "").lower() == "table":
                        table_html = region.get("res", {}).get("html", "")
                        table_cells = _html_table_to_rows(table_html)
                        if table_cells:
                            tables.append({
                                "rows": table_cells,
                                "shape": (len(table_cells),
                                          len(table_cells[0]) if table_cells else 0),
                                "page": page_num,
                                "method": "ppstructure",
                                "accuracy": None,
                            })
            except Exception as e:
                logger.warning("[table_extractor] PPStructure failed on page %d: %s", page_num, e)

        logger.info("[table_extractor] PPStructure found %d tables", len(tables))

    except Exception as e:
        logger.error("[table_extractor] PPStructure extraction failed: %s", e)

    return tables


# ═══════════════════════════════════════════════════════════════════════════
# PRIVATE — HTML TABLE PARSER (for PPStructure output)
# ═══════════════════════════════════════════════════════════════════════════

def _html_table_to_rows(html: str) -> List[List[str]]:
    """Convert an HTML table string to a list of row lists."""
    try:
        from html.parser import HTMLParser

        class TableParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.rows: List[List[str]] = []
                self.current_row: List[str] = []
                self.current_cell: str = ""
                self.in_cell: bool = False

            def handle_starttag(self, tag, attrs):
                if tag in ("td", "th"):
                    self.in_cell = True
                    self.current_cell = ""
                elif tag == "tr":
                    self.current_row = []

            def handle_endtag(self, tag):
                if tag in ("td", "th"):
                    self.current_row.append(self.current_cell.strip())
                    self.in_cell = False
                elif tag == "tr":
                    if self.current_row:
                        self.rows.append(self.current_row)

            def handle_data(self, data):
                if self.in_cell:
                    self.current_cell += data

        parser = TableParser()
        parser.feed(html)
        return parser.rows

    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════════════════
# UTILITIES — column mapping & line-item parsing (kept for pipeline use)
# ═══════════════════════════════════════════════════════════════════════════

def _guess_column_type(header_text: str) -> Optional[str]:
    """Match a column header string to a semantic field name."""
    if not header_text:
        return None
    header_lower = str(header_text).lower().strip()
    for col_type, keywords in COLUMN_KEYWORDS.items():
        for kw in keywords:
            if kw in header_lower:
                return col_type
    return None


def _normalize_subscript_digits(text: str) -> str:
    """Replace Unicode subscript/superscript digits and strip non-digit superscripts."""
    result = []
    for c in text:
        cp = ord(c)
        if 0x2080 <= cp <= 0x2089:
            result.append(str(cp - 0x2080))
        elif 0x2070 <= cp <= 0x2079:
            # Superscript digits
            result.append(str(cp - 0x2070))
        elif 0x207A <= cp <= 0x207F:
            # Superscript non-digit chars (⁺⁻⁼⁽⁾ⁿ) — OCR artifacts, drop them
            pass
        else:
            result.append(c)
    return ''.join(result)


def _has_subscript_digits(text: str) -> bool:
    """Check if text contains Unicode subscript or superscript digits."""
    for c in text:
        cp = ord(c)
        if 0x2080 <= cp <= 0x2089 or 0x2070 <= cp <= 0x2079:
            return True
    return False


def _parse_number(value: str) -> Optional[float]:
    """
    Parse a string to a float, handling Indian lakh notation, commas,
    and Unicode subscript/superscript digits.

    Examples: '1,23,456.78' → 123456.78, '₹5,000' → 5000.0
    """
    if not value:
        return None
    cleaned = _normalize_subscript_digits(str(value))
    cleaned = re.sub(r'[₹$€£\s]', '', cleaned)
    cleaned = cleaned.replace(',', '')
    cleaned = cleaned.strip('-').strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_table_to_line_items(table: List[List[str]]) -> List[Dict[str, Any]]:
    """
    Parse a raw table (list of rows) into structured line items.

    The first row is assumed to be column headers. Each subsequent row
    is parsed based on the detected column mapping.

    Args:
        table: List of rows, where each row is a list of cell strings.

    Returns:
        List of line item dictionaries.
    """
    if not table or len(table) < 2:
        return []

    header_row = table[0]
    col_map = {}
    for i, header in enumerate(header_row):
        col_type = _guess_column_type(header)
        if col_type:
            col_map[i] = col_type

    if not col_map:
        logger.warning("Could not identify any columns in table header: %s", header_row)
        return []

    line_items = []
    for row_idx, row in enumerate(table[1:], start=1):
        item: Dict[str, Any] = {
            "line_number": row_idx,
            "item_code": None,
            "description": None,
            "hsn_sac": None,
            "quantity": None,
            "unit_price": None,
            "discount": None,
            "tax_rate": None,
            "tax_amount": None,
            "line_total": None,
        }

        for col_idx, col_type in col_map.items():
            if col_idx < len(row):
                cell_value = str(row[col_idx]).strip() if row[col_idx] is not None else ""
                if not cell_value or cell_value.lower() in ("", "none", "null", "-", "nil"):
                    continue

                if col_type == "serial":
                    pass
                elif col_type == "item_code":
                    item["item_code"] = cell_value
                elif col_type == "description":
                    item["description"] = cell_value
                elif col_type == "hsn_sac":
                    item["hsn_sac"] = cell_value
                elif col_type == "quantity":
                    item["quantity"] = _parse_number(clean_ocr_number(cell_value))
                elif col_type == "unit_price":
                    item["unit_price"] = _parse_number(clean_ocr_number(cell_value))
                elif col_type == "discount":
                    item["discount"] = _parse_number(cell_value)
                elif col_type == "tax_rate":
                    item["tax_rate"] = _parse_number(cell_value)
                elif col_type == "tax_amount":
                    item["tax_amount"] = _parse_number(cell_value)
                elif col_type == "amount":
                    item["line_total"] = _parse_number(clean_ocr_number(cell_value))

        has_desc = bool(item["description"])
        has_money = any(item[k] is not None for k in ["quantity", "unit_price", "line_total"])
        if has_desc or has_money:
            line_items.append(item)

    logger.info("Parsed %d line items from table", len(line_items))
    return line_items


def extract_line_items_from_text(text: str) -> List[Dict[str, Any]]:
    """
    Fallback: extract line items from raw text using regex heuristics.

    Handles Indian GST invoice formats with patterns like:
        1 Sticker With Lamination 500 NOS ₹ 5.90 18% ₹ 2,950.00
        1 SS 304 SHEET 2B  72199013  805 KGS  232.00 KGS  1,86,760.00

    Args:
        text: Full extracted text from the invoice.

    Returns:
        List of line item dictionaries (best effort).
    """
    text = _normalize_subscript_digits(text)
    line_items = []

    # Pattern for GST invoices: serial description [HSN] qty [unit] [₹] price [gst%] [₹] amount
    gst_pattern = re.compile(
        r'^\s*(\d+)\s+'                           # serial number
        r'(.+?)\s+'                                # description (non-greedy)
        r'(?:(\d{4,8})\s+)?'                       # optional HSN/SAC code (4-8 digits)
        r'([\d,]+(?:\.\d+)?)\s+'                   # quantity
        r'(?:NOS|KGS|PCS|NOS\.|MTR|LTR|BOX|SET|PKT|BAG|UNIT|PAIR|DOZ|DOZENS?|KG|GM|ML|SQFT|SQF|RFT|CFT|ROLL|LOT|EA|EACH|REAM|SHEETS?|BUNDLE)\s+'  # unit
        r'(?:₹\s*)?'                               # optional ₹ symbol
        r'([\d,]+(?:\.\d+)?)\s+'                   # unit price
        r'(?:(\d+(?:\.\d+)?)\s*%?\s+)?'            # optional tax rate %
        r'(?:₹\s*)?'                               # optional ₹ symbol
        r'([\d,]+(?:\.\d+)?)'                      # amount/total
    , re.IGNORECASE)

    # Pattern for lines WITHOUT a leading serial number:
    # description [HSN] qty [unit] price amount
    no_serial_pattern = re.compile(
        r'^\s*([A-Za-z].+?)\s+'                    # description (starts with letter)
        r'(?:(\d{4,8})\s+)?'                       # optional HSN/SAC code
        r'([\d,]+(?:\.\d+)?)\s+'                    # quantity
        r'(?:NOS|KGS|PCS|NOS\.|MTR|LTR|BOX|SET|PKT|BAG|UNIT|PAIR|DOZ|DOZENS?|KG|GM|ML|SQFT|SQF|RFT|CFT|ROLL|LOT|EA|EACH|REAM|SHEETS?|BUNDLE)\s+'  # unit
        r'(?:₹\s*)?'                               # optional ₹ symbol
        r'([\d,]+(?:\.\d+)?)\s+'                    # unit price
        r'(?:(\d+(?:\.\d+)?)\s*%?\s+)?'            # optional tax rate %
        r'(?:₹\s*)?'                               # optional ₹ symbol
        r'([\d,]+(?:\.\d+)?)\s*$'                   # amount/total
    , re.IGNORECASE)

    # Simpler fallback pattern: serial description numbers...
    simple_pattern = re.compile(
        r'^\s*(\d+)\s+'                            # serial number
        r'(.+?)\s+'                                # description
        r'([\d,]+\.?\d*)\s+'                       # number 1 (qty or price)
        r'([\d,]+\.?\d*)\s*'                       # number 2
        r'([\d,]+\.?\d*)?'                         # number 3 (optional)
    , re.IGNORECASE)

    # OCR-aware pattern for serial + description + HSN + multiple numeric columns
    # Matches: "1 solvent 345 23.00 200.00 524.40 21 8.50 4,894.40"
    # Takes the LAST number as line_total, handles variable number of intermediate columns
    ocr_serial_multi_num = re.compile(
        r'^\s*(\d+)\s+'                            # serial number
        r'([A-Za-z][\w\s!.,\-()]*?)\s+'           # description (starts with letter, non-greedy)
        r'(?:(\d{3,8})\s+)?'                       # optional HSN/SAC code (3-8 digits)
        r'([\d,]+\.?\d*)\s+'                       # number 1 (quantity)
        r'([\d,]+\.?\d*)\s+'                       # number 2 (unit price)
        r'(?:[\d,]+\.?\d*\s+)*'                    # skip intermediate numbers (taxable, tax etc.)
        r'([\d,]+\.?\d*)\s*$'                      # LAST number = line total
    , re.IGNORECASE)

    # ── OCR-aware patterns for image invoices ────────────────────────────
    # Pattern for pipe-separated OCR lines (image invoices with table borders):
    # description [HSN] | [symbol] number [number...] | [symbol] amount
    # Works on cleaned text (after stripping |, €, ©, &, % artifacts)
    ocr_pipe_pattern = re.compile(
        r'^\s*([A-Za-z][\w\s!.,\-()]+?)\s+'           # description (starts with letter)
        r'(?:(\d{4,8})\s+)?'                           # optional HSN/SAC code
        r'([\d,]+(?:\.\d+)?)\s+'                       # number 1 (MRP / unit_price)
        r'([\d,]+(?:\.\d+)?)\s+'                       # number 2 (taxable value)
        r'([\d,]+(?:\.\d+)?)\s+'                       # number 3 (tax amount)
        r'([\d,]+(?:\.\d+)?)\s*$'                      # number 4 (line total / amount)
    , re.IGNORECASE)

    # Simpler OCR pattern: description followed by fewer numbers (no tax breakdown)
    ocr_short_pattern = re.compile(
        r'^\s*([A-Za-z][\w\s!.,\-()]+?)\s+'           # description
        r'(?:(\d{4,8})\s+)?'                           # optional HSN/SAC
        r'([\d,]+(?:\.\d+)?)\s+'                       # number 1
        r'([\d,]+(?:\.\d+)?)\s*$'                      # number 2 (line total)
    , re.IGNORECASE)

    # Minimal OCR pattern: description followed by a single amount
    # For lines like "Bosch All-in-One Metal Hand Tool Kit 2,535.00"
    ocr_desc_amount_pattern = re.compile(
        r'^\s*([A-Za-z][\w\s!.,\-()]+?)\s+'           # description (non-greedy)
        r'([\d,]+\.\d{2})\s*$'                         # amount with exactly 2 decimal places
    , re.IGNORECASE)

    lines = text.split('\n')
    row_num = 0
    prev_item_idx = -1

    # Detect table header region to identify where line items start
    table_header_idx = -1
    for li, raw_line in enumerate(lines):
        low = raw_line.lower()
        if any(kw in low for kw in ['description', 'descri', 'particulars', 'product',
                                      'name of product', 'name of service']):
            if any(kw in low for kw in ['amount', 'total', 'value', 'mrp', 'rate',
                                         'price', 'hsn', 'sac', 'qty', 'quantity']):
                table_header_idx = li
                break

    for line_idx, line in enumerate(lines):
        line = line.strip()
        if not line or len(line) < 5:
            continue

        # Skip header-like lines
        if re.match(r'^S\.?\s*No\b|^PARTICULARS|^Description|^HSN|^---', line, re.IGNORECASE):
            continue
        # Also skip lines that look like OCR-garbled table headers
        if re.match(
            r'.*(?:Product\s+Descri|Name\s+of\s+Product|Name\s+of\s+Service).*(?:HSN|SAC|Amount|MRP|Value)',
            line, re.IGNORECASE
        ):
            continue
        if re.match(r'^\[?s\.?n\.?o?\]?\s', line, re.IGNORECASE):
            continue
        # Skip footer-like lines
        if re.match(
            r'^(?:Delivery|Total\s*Qty|Sub\s*Total|Add\s|CGST|SGST|IGST|Round|'
            r'Invoice\s*Amount|Rupees|TOTAL|Terms|Bank|Goods\s*ones|Subject|'
            r'E\.\s*&|Powered|For[,\s]|Branch[:\s]|Declaration|Contact|'
            r'TAX\s*INVOICE|Bill\s*To|Ship\s*To|GSTIN|State|Place\s*of|'
            r'Amount\s*in\s*Words|Net\s*Amount|Taxable\s*Value|Less\s*Discount|'
            r'Total\s*in\s*words|Certified|Thank\s*you|Remarks|Summary|'
            r'Cheque\s*in|Pay\s*using|Customer\s*Signature|Authorised|'
            r'©\s*[\d,]+\.?\d*\s*\|?\s*Total|'
            r'igs\b|cest\b|sGsT\b|'
            r'Shipping\s*&|Pay\s*Now|AUTHORIZED|ROUNDED|AMOUNT\s*DUE|NOTE:|'
            r'^@\d|^-Discount|^Discount\s)',
            line, re.IGNORECASE
        ):
            prev_item_idx = -1  # Stop appending sub-descriptions after footer
            continue

        match = gst_pattern.match(line)
        if match:
            row_num += 1
            serial, desc, hsn, qty_s, price_s, tax_s, amount_s = match.groups()
            item: Dict[str, Any] = {
                "line_number": row_num,
                "description": desc.strip(),
                "hsn_sac": hsn if hsn else None,
                "quantity": _parse_number(clean_ocr_number(qty_s)),
                "unit_price": _parse_number(clean_ocr_number(price_s)),
                "tax_rate": _parse_number(tax_s) if tax_s else None,
                "line_total": _parse_number(clean_ocr_number(amount_s)),
                "item_code": None,
                "discount": None,
                "tax_amount": None,
            }
            # Back-calculate unit_price if math doesn't work
            # (handles corrupted subscript digits in source)
            if item["quantity"] and item["line_total"] and item["quantity"] > 0:
                expected = item["quantity"] * (item["unit_price"] or 0)
                if item["unit_price"] is None or abs(expected - item["line_total"]) > 0.50:
                    item["unit_price"] = round(item["line_total"] / item["quantity"], 2)
            line_items.append(item)
            prev_item_idx = len(line_items) - 1
            continue

        # Try no-serial-number pattern (description HSN qty unit price amount)
        match = no_serial_pattern.match(line)
        if match:
            row_num += 1
            desc, hsn, qty_s, price_s, tax_s, amount_s = match.groups()
            item = {
                "line_number": row_num,
                "description": desc.strip(),
                "hsn_sac": hsn if hsn else None,
                "quantity": _parse_number(clean_ocr_number(qty_s)),
                "unit_price": _parse_number(clean_ocr_number(price_s)),
                "tax_rate": _parse_number(tax_s) if tax_s else None,
                "line_total": _parse_number(clean_ocr_number(amount_s)),
                "item_code": None,
                "discount": None,
                "tax_amount": None,
            }
            if item["quantity"] and item["line_total"] and item["quantity"] > 0:
                expected = item["quantity"] * (item["unit_price"] or 0)
                if item["unit_price"] is None or abs(expected - item["line_total"]) > 0.50:
                    item["unit_price"] = round(item["line_total"] / item["quantity"], 2)
            line_items.append(item)
            prev_item_idx = len(line_items) - 1
            continue

        # Try OCR multi-number serial pattern (serial desc [HSN] qty price ... total)
        # Must come before simple_pattern to catch lines with 4+ numbers correctly
        match = ocr_serial_multi_num.match(line)
        if match:
            serial, desc, hsn, qty_s, price_s, total_s = match.groups()
            row_num += 1
            item = {
                "line_number": row_num,
                "description": desc.strip(),
                "hsn_sac": hsn if hsn else None,
                "quantity": _parse_number(clean_ocr_number(qty_s)),
                "unit_price": _parse_number(clean_ocr_number(price_s)),
                "line_total": _parse_number(clean_ocr_number(total_s)),
                "item_code": None,
                "discount": None,
                "tax_rate": None,
                "tax_amount": None,
            }
            if item["quantity"] and item["line_total"] and item["quantity"] > 0:
                expected = item["quantity"] * (item["unit_price"] or 0)
                if item["unit_price"] is None or abs(expected - item["line_total"]) > 0.50:
                    item["unit_price"] = round(item["line_total"] / item["quantity"], 2)
            line_items.append(item)
            prev_item_idx = len(line_items) - 1
            continue

        # Try simple pattern
        match = simple_pattern.match(line)
        if match:
            row_num += 1
            groups = match.groups()
            item = {
                "line_number": row_num,
                "description": groups[1].strip() if groups[1] else None,
                "quantity": _parse_number(clean_ocr_number(groups[2])) if groups[2] else None,
                "unit_price": _parse_number(clean_ocr_number(groups[3])) if groups[3] else None,
                "line_total": _parse_number(clean_ocr_number(groups[4])) if groups[4] else None,
                "item_code": None,
                "hsn_sac": None,
                "discount": None,
                "tax_rate": None,
                "tax_amount": None,
            }
            if item["description"] or item["line_total"] is not None:
                line_items.append(item)
                prev_item_idx = len(line_items) - 1
            continue

        # ── OCR-aware patterns for image invoices ──────────────────────
        # Clean OCR artifacts: pipe separators, misread currency symbols
        cleaned = re.sub(r'[|€©&%£$₹]', ' ', line)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        # Skip if this line is before the table header (likely header/address area)
        if table_header_idx >= 0 and line_idx <= table_header_idx:
            pass  # Fall through to sub-description check
        else:
            # Try pipe-separated OCR pattern (4 numbers: mrp, taxable, tax, amount)
            match = ocr_pipe_pattern.match(cleaned)
            if match:
                row_num += 1
                desc, hsn, n1, n2, n3, n4 = match.groups()
                item = {
                    "line_number": row_num,
                    "description": desc.strip(),
                    "hsn_sac": hsn if hsn else None,
                    "quantity": None,
                    "unit_price": _parse_number(clean_ocr_number(n1)),
                    "discount": None,
                    "tax_rate": None,
                    "tax_amount": _parse_number(n3),
                    "line_total": _parse_number(clean_ocr_number(n4)),
                    "item_code": None,
                }
                line_items.append(item)
                prev_item_idx = len(line_items) - 1
                continue

            # Try shorter OCR pattern (2 numbers: price + amount)
            match = ocr_short_pattern.match(cleaned)
            if match:
                row_num += 1
                desc, hsn, n1, n2 = match.groups()
                item = {
                    "line_number": row_num,
                    "description": desc.strip(),
                    "hsn_sac": hsn if hsn else None,
                    "quantity": None,
                    "unit_price": _parse_number(clean_ocr_number(n1)),
                    "discount": None,
                    "tax_rate": None,
                    "tax_amount": None,
                    "line_total": _parse_number(clean_ocr_number(n2)),
                    "item_code": None,
                }
                line_items.append(item)
                prev_item_idx = len(line_items) - 1
                continue

            # Try description + single amount pattern
            match = ocr_desc_amount_pattern.match(cleaned)
            if match:
                desc, amount = match.groups()
                # Avoid matching footer lines that have amounts
                if not re.search(
                    r'(?:total|tax|cgst|sgst|igst|subtotal|discount|shipping|'
                    r'bank|amount\s*in|rupees|cheque|summary|taxable)',
                    desc, re.IGNORECASE
                ):
                    row_num += 1
                    item = {
                        "line_number": row_num,
                        "description": desc.strip(),
                        "hsn_sac": None,
                        "quantity": None,
                        "unit_price": None,
                        "discount": None,
                        "tax_rate": None,
                        "tax_amount": None,
                        "line_total": _parse_number(clean_ocr_number(amount)),
                        "item_code": None,
                    }
                    line_items.append(item)
                    prev_item_idx = len(line_items) - 1
                    continue

        # Check if this line is a sub-description for the previous item
        if prev_item_idx >= 0 and not re.match(r'^\d', line):
            # Append to previous item's description if it looks like a continuation
            # Must be short, no currency/percentage symbols, no company/address keywords
            if (len(line) < 60
                    and not re.search(r'[₹$€£%]', line)
                    and not re.match(r'^(?:[A-Z][A-Z\s&.]+(?:PVT|LTD|LLC|DIGITALS|SOLUTIONS|ENTERPRISES))', line)
                    and not re.search(r'(?:Bank|IFSC|A/C|Branch|GSTIN|Contact|Email|Phone|Jurisdiction)', line, re.IGNORECASE)):
                existing = line_items[prev_item_idx]["description"] or ""
                line_items[prev_item_idx]["description"] = (existing + " - " + line).strip(" -")

    logger.info("Extracted %d line items from text (regex fallback)", len(line_items))
    return line_items
