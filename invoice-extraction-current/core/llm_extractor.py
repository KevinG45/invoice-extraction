"""
LLM-based Invoice Field Extractor — uses Ollama (local, free) for KIE.

Sends OCR text to a local LLM with a structured JSON prompt to extract
all invoice fields. Falls back to regex extraction if the LLM is unavailable
or returns invalid JSON.

RULES:
    - Only Ollama (local). No paid APIs.
    - Temperature = 0 for deterministic extraction.
    - Retry up to LLM_MAX_RETRIES times on JSON parse failure.
    - Always returns a dict (with null values on failure, never empty dict).
    - Runs math post-processing to convert string numbers to actual floats.
"""

import json
import logging
import re
from typing import Any, Dict, Optional

from core.config import LLM_MODEL, LLM_BASE_URL, LLM_TEMPERATURE, LLM_MAX_RETRIES, LLM_TIMEOUT

logger = logging.getLogger(__name__)

# FIXED: Bug #28 — Garbage invoice number validation
GARBAGE_INV_NUMS = {
    "e-Way", "e-way", "E-WAY", "Bill", "No", "Date", "the",
    "Dated", "Buyer", "GSTIN", "Tax", "Invoice", "Page",
    "Seller", "Total", "Amount", "Number", "Details"
}

_GSTIN_RE = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z\d]{2}$")


def _normalize_gstin_candidate(raw: Any) -> Optional[str]:
    """Normalize a noisy GSTIN-like token (OCR-safe) and return valid GSTIN if possible."""
    if raw is None:
        return None
    s = str(raw).upper()
    s = re.sub(r'^(?:GSTIN(?:\s*/\s*UIN)?|UIN|GST|TIN)\s*[/:\-]?\s*', '', s, flags=re.IGNORECASE).strip()
    s = re.sub(r'[^A-Z0-9]', '', s)
    if len(s) < 15:
        return None
    s = s[:15]

    chars = list(s)

    def _as_digit(ch: str) -> str:
        return {
            'O': '0', 'Q': '0', 'D': '0',
            'I': '1', 'L': '1', 'T': '1',
            'S': '5', 'B': '8',
        }.get(ch, ch)

    def _as_letter(ch: str) -> str:
        return {
            '0': 'O', '1': 'I', '2': 'Z', '3': 'B', '4': 'A',
            '5': 'S', '6': 'G', '7': 'T', '8': 'B', '9': 'G',
        }.get(ch, ch)

    # GSTIN format positions: 2 digits + 5 letters + 4 digits + 1 letter + 1 digit + 2 alnum
    for i in (0, 1, 7, 8, 9, 10, 12):
        chars[i] = _as_digit(chars[i])

    for i in (2, 3, 4, 5, 6, 11):
        chars[i] = _as_letter(chars[i])

    # FIXED: Bug P0-5 — Position 13 (14th character) should be digit, position 14 (15th) is alphanumeric check
    # Position 13 (index 13): must be digit
    chars[13] = _as_digit(chars[13])
    
    # Position 14 (index 14): check digit/letter - keep as-is (can be alphanumeric)
    # Don't normalize - let the actual character through for proper validation
    # chars[14] stays as-is

    candidate = ''.join(chars)
    return candidate if _GSTIN_RE.match(candidate) else None


def _extract_gstins_from_text(text: str) -> list[str]:
    """Extract valid GSTIN values from raw text, including OCR-corrupted forms."""
    if not text:
        return []

    hits = []
    seen = set()

    # High-confidence explicit GSTIN labels first.
    for m in re.finditer(r'(?:GSTIN|GSTIN/UIN|UIN|GST)\s*[.:\-]?\s*([A-Z0-9\-/\s]{10,30})', text, re.IGNORECASE):
        norm = _normalize_gstin_candidate(m.group(1))
        if norm and norm not in seen:
            seen.add(norm)
            hits.append(norm)

    # Broader scan for contiguous alnum tokens likely to hold GSTIN values.
    for m in re.finditer(r'\b[A-Z0-9][A-Z0-9\-/\s]{12,22}[A-Z0-9]\b', text.upper()):
        norm = _normalize_gstin_candidate(m.group(0))
        if norm and norm not in seen:
            seen.add(norm)
            hits.append(norm)

    return hits


def _is_valid_invoice_number(inv_num: str | None) -> bool:
    """
    Validate invoice number structure.
    # FIXED: Bug #28
    
    A valid invoice number must:
    - Contain at least one digit
    - Be between 2 and 30 characters
    - Not be purely alphabetic
    - Not match any word in GARBAGE_INV_NUMS
    
    Args:
        inv_num: Candidate invoice number string
    
    Returns:
        True if valid, False otherwise
    """
    if not inv_num or not isinstance(inv_num, str):
        return False
    
    inv_num = inv_num.strip()
    
    # Check length
    if len(inv_num) < 2 or len(inv_num) > 30:
        return False
    
    # Must contain at least one digit
    if not re.search(r'\d', inv_num):
        return False
    
    # Must not be purely numeric (likely page/qty)
    if inv_num.isdigit() and len(inv_num) < 4:
        return False
    
    # Check against garbage list (case-insensitive)
    if inv_num.upper() in {g.upper() for g in GARBAGE_INV_NUMS}:
        return False
    
    # Must not be purely alphabetic
    if inv_num.isalpha():
        return False
    
    return True


# ── Invoice extraction JSON schema prompt ──────────────────────────────────
EXTRACTION_PROMPT = """Extract all invoice fields from the text below. Return ONLY a JSON object — no markdown, no code blocks, no explanations. Start with {{ and end with }}.

RULES:
- Use null for any missing field — never omit fields
- currency: use "INR" if you see ₹, Rs, GSTIN, or any GST%; otherwise match the symbol found
- vendor.name: company name only | vendor.address: full vendor address (street, city, state, PIN) # FIXED: Bug #4
- bill_to.name: buyer company name only | bill_to.address: full buyer address (street, city, state, PIN) # FIXED: Bug #4
- ship_to.name: consignee name only | ship_to.address: full shipping address (street, city, state, PIN) # FIXED: Bug #4
- All string values must be on a single line (no newlines inside strings)
- line_items[].total is the line's total amount (qty × unit_price before or after tax)
- For Indian GST invoices: tax_rate is typically 5, 12, 18, or 28 (percent)
- IMPORTANT: Some invoices have the item name on one line and its description on the NEXT line (before the next item's numbers). Combine them: use the item name + description together as line_items[].description. Do NOT create a separate line item for a description-only line that has no quantity or amount.

OUTPUT this exact structure (replace values, keep all keys, use null for missing):
{{"invoice_number":null,"invoice_date":null,"due_date":null,"purchase_order_number":null,"currency":"INR","subtotal":null,"discount":null,"tax_amount":null,"shipping":null,"total_amount":null,"amount_paid":null,"amount_due":null,"tax_rate":null,"payment_terms":null,"payment_method":null,"bank_details":null,"notes":null,"vendor":{{"name":null,"address":null,"email":null,"phone":null,"tax_id":null,"website":null}},"bill_to":{{"name":null,"address":null,"email":null,"tax_id":null}},"ship_to":{{"name":null,"address":null}},"line_items":[{{"description":null,"hsn_sac":null,"quantity":null,"unit":null,"unit_price":null,"discount":null,"tax_rate":null,"total":null}}]}}

INVOICE TEXT:
{ocr_text}

JSON:"""


# ═══════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════

# ── Sliding Window Config (Bug #17 fix) ──
WINDOW_SIZE = 6000       # Characters per window
WINDOW_OVERLAP = 500     # Overlap between windows
MAX_WINDOWS = 2          # Max windows (12K chars total) — 1 invoice rarely needs more
MAX_INVOICE_CHARS = 12000  # Hard limit — reduces LLM call time significantly


def _extract_window(text: str, window_num: int, is_first: bool) -> dict:
    """Extract fields from a single window of text.
    
    First window: extract all fields (headers + line_items).
    Subsequent windows: extract only line_items.
    """
    if is_first:
        prompt = EXTRACTION_PROMPT.format(ocr_text=text)
    else:
        # For continuation windows, only extract line items
        prompt = f"""Extract ONLY the line items from this invoice text (continuation from previous page).
Return JSON with only the "line_items" array.

Invoice text:
{text}

Return ONLY valid JSON like: {{"line_items": [{{"description": "...", "quantity": ..., "unit_price": ..., "total": ...}}]}}"""
    
    raw = ""
    for attempt in range(1, LLM_MAX_RETRIES + 1):
        try:
            raw = _call_ollama(prompt, json_mode=True)
            cleaned = _clean_llm_response(raw)
            return json.loads(cleaned, strict=False)
        except json.JSONDecodeError:
            if attempt == LLM_MAX_RETRIES:
                return {}
        except Exception:
            if attempt == LLM_MAX_RETRIES:
                return {}
    return {}


def _dedupe_line_items(items: list) -> list:
    """Deduplicate line items by (description, total) tuple."""
    seen = set()
    unique = []
    for item in items:
        if not isinstance(item, dict):
            continue
        desc = str(item.get("description", "")).strip().lower()
        total = item.get("total", 0)
        key = (desc, total)
        if key not in seen and desc:
            seen.add(key)
            unique.append(item)
    return unique


def extract_invoice_fields(text: str) -> dict:
    """
    Use local Ollama LLM to extract invoice fields from text.
    
    FIXED: Bug #17 — Uses sliding window for multi-page invoices.
    - Window 1: Extract all header fields + line_items (6000 chars)
    - Window 2+: Extract only line_items (continuation pages)
    - Dedupe line_items by (description, total) to avoid duplicates
    - Max 5 windows (30K chars total)

    Args:
        text: Raw OCR / extracted text from an invoice.

    Returns:
        dict matching invoice schema (fields may be null).
    """
    if not text or len(text.strip()) < 10:
        logger.warning("[llm_extractor] Input text is too short, returning empty result")
        return _empty_invoice()

    # Truncate to hard limit
    text = text[:MAX_INVOICE_CHARS]
    
    # Short documents: use original single-call approach for efficiency
    if len(text) <= WINDOW_SIZE:
        prompt = EXTRACTION_PROMPT.format(ocr_text=text)
        raw = ""

        for attempt in range(1, LLM_MAX_RETRIES + 1):
            logger.info("[llm_extractor] Extraction attempt %d/%d", attempt, LLM_MAX_RETRIES)
            try:
                raw = _call_ollama(prompt, json_mode=True)
                cleaned = _clean_llm_response(raw)
                data = json.loads(cleaned, strict=False)
                data = _normalize_numeric_fields(data)
                data = _clean_extracted_fields(data, text=text)
                data = _verify_tax_from_text(data, text)
                logger.info("[llm_extractor] Extraction successful")
                return data

            except json.JSONDecodeError as e:
                logger.warning("[llm_extractor] JSON parse failed on attempt %d: %s", attempt, e)
                logger.debug("[llm_extractor] Raw LLM response was:\n%s", raw[:500])
                if attempt == LLM_MAX_RETRIES:
                    logger.error("[llm_extractor] All retries exhausted. Running regex fallback.")
                    return _try_regex_fallback(text)

            except Exception as e:
                logger.error("[llm_extractor] Unexpected error on attempt %d: %s", attempt, e)
                if attempt == LLM_MAX_RETRIES:
                    return _empty_invoice()

        return _empty_invoice()
    
    # Long documents: sliding window approach
    logger.info("[llm_extractor] Using sliding window for %d char document", len(text))
    
    # Calculate window positions
    windows = []
    pos = 0
    while pos < len(text) and len(windows) < MAX_WINDOWS:
        end = min(pos + WINDOW_SIZE, len(text))
        windows.append((pos, end))
        pos = end - WINDOW_OVERLAP
        if end == len(text):
            break
    
    logger.info("[llm_extractor] Processing %d windows", len(windows))
    
    # Process first window (full extraction)
    start, end = windows[0]
    logger.info("[llm_extractor] Window 1: chars %d-%d", start, end)
    result = _extract_window(text[start:end], 1, is_first=True)
    
    if not result:
        logger.warning("[llm_extractor] First window failed, using regex fallback")
        return _try_regex_fallback(text)
    
    # Normalize the first window result
    result = _normalize_numeric_fields(result)
    result = _clean_extracted_fields(result, text=text)
    all_line_items = list(result.get("line_items", []) or [])
    
    # Process subsequent windows (line_items only)
    for i, (start, end) in enumerate(windows[1:], start=2):
        logger.info("[llm_extractor] Window %d: chars %d-%d", i, start, end)
        window_result = _extract_window(text[start:end], i, is_first=False)
        
        if window_result and "line_items" in window_result:
            items = window_result.get("line_items", [])
            if isinstance(items, list):
                all_line_items.extend(items)
    
    # Dedupe and assign final line_items
    result["line_items"] = _dedupe_line_items(all_line_items)
    logger.info("[llm_extractor] Final: %d unique line items from %d windows", 
                len(result["line_items"]), len(windows))
    
    # Verify tax from full text
    result = _verify_tax_from_text(result, text)
    
    return result


# ── Focused customer-name extraction (fallback when main extraction misses it) ──

_CUSTOMER_NAME_PROMPT = """This is an invoice document. What is the customer or buyer company name \
in this invoice? Look for labels such as: Bill To, Sold To, Customer, Ship To, Buyer. \
The name appears directly after one of these labels.
Return ONLY the company name.
Nothing else. No explanation."""


def extract_customer_name(text: str, vendor_name: Optional[str] = None) -> Optional[str]:
    """
    Focused single-field LLM call to extract the customer / bill-to name.

    Called as a fallback when the main extraction returns null for bill_to.name.
    Uses a short, direct prompt to reduce JSON formatting errors.

    Args:
        text: Raw OCR / extracted text from the invoice.
        vendor_name: Known vendor name to exclude from the response.

    Returns:
        The customer name string, or None if unable to extract.
    """
    if not text or len(text.strip()) < 10:
        return None

    exclusion = (
        f"\nIMPORTANT: The vendor/seller in this invoice is '{vendor_name}'. "
        "Do NOT return the vendor name. Return the OTHER party's name only."
        if vendor_name else ""
    )
    prompt = _CUSTOMER_NAME_PROMPT + exclusion + f"\n\nINVOICE TEXT:\n{text[:4000]}\n\nCOMPANY NAME:"
    try:
        raw = _call_ollama(prompt).strip()
        if not raw:
            return None
        # Reject clearly wrong responses (too long = hallucination, too short = garbage)
        if len(raw) > 80 or len(raw) < 2:
            logger.warning("[llm_extractor] extract_customer_name response rejected (len=%d): %r", len(raw), raw[:80])
            return None
        # Strip common prefixes the LLM might add despite instructions
        for prefix in ("Customer:", "Bill To:", "Buyer:", "Company Name:", "Name:"):
            if raw.lower().startswith(prefix.lower()):
                raw = raw[len(prefix):].strip()
        # Reject if the LLM returned the vendor name anyway (normalised comparison)
        if vendor_name:
            norm_raw = re.sub(r'[\s\W]', '', raw).lower()
            norm_vendor = re.sub(r'[\s\W]', '', vendor_name).lower()
            if norm_raw == norm_vendor or (len(norm_vendor) > 3 and norm_vendor in norm_raw):
                logger.warning("[llm_extractor] extract_customer_name returned vendor name, rejecting")
                return None
        logger.info("[llm_extractor] extract_customer_name → %r", raw)
        return raw
    except Exception as e:
        logger.error("[llm_extractor] extract_customer_name failed: %s", e)
        return None


# ── Legacy wrapper for backward compatibility ─────────────────────────────

def extract_fields_with_llm(ocr_text: str, max_retries: int = 2) -> Optional[Dict[str, Any]]:
    """
    Use a local LLM (via Ollama) to extract structured fields from OCR text.

    Legacy interface — delegates to extract_invoice_fields() internally.

    Args:
        ocr_text: Raw text extracted from the invoice.
        max_retries: Number of retry attempts (ignored — uses LLM_MAX_RETRIES).

    Returns:
        Parsed JSON dictionary of invoice fields, or None if LLM unavailable.
    """
    if not ocr_text or len(ocr_text.strip()) < 20:
        logger.warning("OCR text too short (%d chars) for LLM extraction", len(ocr_text))
        return None

    try:
        result = extract_invoice_fields(ocr_text)
        # Return None if all values are null (signals failure to callers)
        if all(v is None for k, v in result.items()
               if k not in ("vendor", "bill_to", "ship_to", "line_items", "validation")):
            return None
        return result
    except Exception as e:
        logger.error("LLM extraction wrapper failed: %s", e)
        return None


# ═══════════════════════════════════════════════════════════════════════════
# PRIVATE — OLLAMA COMMUNICATION
# ═══════════════════════════════════════════════════════════════════════════

def _call_ollama(prompt: str, json_mode: bool = False) -> str:
    """Make a request to the local Ollama API.

    Args:
        prompt: The prompt to send.
        json_mode: If True, add format='json' to force grammar-constrained JSON output.
                   Only use for calls that must return JSON (not plain-text calls).
    """
    import requests as req

    url = f"{LLM_BASE_URL}/api/generate"
    payload = {
        "model": LLM_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": LLM_TEMPERATURE,
            "num_predict": 2048,
        },
    }
    if json_mode:
        payload["format"] = "json"

    try:
        response = req.post(url, json=payload, timeout=LLM_TIMEOUT)
        response.raise_for_status()
        return response.json().get("response", "")
    except req.exceptions.ConnectionError:
        raise ConnectionError(
            f"Cannot connect to Ollama at {LLM_BASE_URL}. "
            "Is it running? Try: ollama serve"
        )
    except req.exceptions.Timeout:
        raise TimeoutError(f"Ollama request timed out after {LLM_TIMEOUT} seconds")


def _check_ollama_available() -> bool:
    """Check if Ollama is running and reachable."""
    try:
        import requests as req
        resp = req.get(f"{LLM_BASE_URL}/api/tags", timeout=5)
        return resp.status_code == 200
    except Exception as e:
        logger.warning("Ollama not available at %s: %s", LLM_BASE_URL, e)
        return False


# ═══════════════════════════════════════════════════════════════════════════
# PRIVATE — RESPONSE CLEANING
# ═══════════════════════════════════════════════════════════════════════════

def _clean_llm_response(raw: str) -> str:
    """Strip markdown fences, control characters, and extract JSON from LLM response."""
    text = raw

    # Step 1: Remove markdown code fences
    text = re.sub(r'```json', '', text)
    text = re.sub(r'```', '', text)
    text = text.strip()

    # Step 2: Find the first { and last } and extract only what is between them.
    # This handles any text before or after JSON.
    start_idx = text.find('{')
    end_idx = text.rfind('}')
    if start_idx != -1 and end_idx != -1:
        text = text[start_idx:end_idx + 1]

    # Step 3: Remove control characters.
    # These are the characters causing the "Invalid control character" parse error.
    # Keeps newlines (\n = \x0a) and tabs (\t = \x09) which are valid in JSON
    # between fields, removes everything else in the control range.
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

    # Step 4: Replace any literal newline that appears inside a quoted string value
    # with a space. Safe approach: replace \n with space only when preceded by a
    # non-whitespace character and followed by a non-whitespace character
    # (i.e. in the middle of content, not between JSON fields).
    text = re.sub(r'(?<=\S)\n(?=\S)', ' ', text)

    return text


def _extract_balanced_json(text: str) -> Optional[str]:
    """Extract the first balanced {...} block from text using brace counting."""
    if not text or text[0] != '{':
        return None
    depth = 0
    in_string = False
    escape = False
    for i, c in enumerate(text):
        if escape:
            escape = False
            continue
        if c == '\\' and in_string:
            escape = True
            continue
        if c == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return text[:i + 1]
    return None


# ═══════════════════════════════════════════════════════════════════════════
# PRIVATE — CURRENCY NORMALIZATION
# ═══════════════════════════════════════════════════════════════════════════

def _normalize_currency(currency_str: str) -> str:
    """
    Normalize currency symbols to ISO codes.
    FIXED: Bug P1-2 — Handle INR/Rs/₹, USD/$, EUR/€ variations
    
    Args:
        currency_str: Raw currency string from extraction
        
    Returns:
        Normalized ISO code (INR, USD, EUR, etc.)
    """
    if not currency_str:
        return "INR"  # Default to INR for Indian invoices
    
    currency_str = str(currency_str).strip().upper()
    
    # Direct ISO code matches
    if currency_str in ['INR', 'USD', 'EUR', 'GBP', 'JPY', 'CNY', 'AUD', 'CAD']:
        return currency_str
    
    # INR variations
    if currency_str in ['RS', 'RS.', 'RUPEES', 'RUPEE', 'INDIAN RUPEES', 'INDIAN RUPEE']:
        return 'INR'
    if '₹' in currency_str or 'INR' in currency_str:
        return 'INR'
    
    # USD variations
    if currency_str in ['$', 'DOLLAR', 'DOLLARS', 'US$', 'US DOLLAR']:
        return 'USD'
    if '$' in currency_str and 'USD' not in currency_str:
        return 'USD'
    
    # EUR variations
    if currency_str in ['€', 'EURO', 'EUROS']:
        return 'EUR'
    if '€' in currency_str:
        return 'EUR'
    
    # GBP variations
    if currency_str in ['£', 'GBP', 'POUND', 'POUNDS', 'STERLING']:
        return 'GBP'
    if '£' in currency_str:
        return 'GBP'
    
    # Default to original if no match
    return currency_str


# ═══════════════════════════════════════════════════════════════════════════
# PRIVATE — NUMERIC NORMALIZATION
# ═══════════════════════════════════════════════════════════════════════════

def _normalize_numeric_fields(data: dict) -> dict:
    """
    Convert string numbers to floats/ints throughout the extracted dict.
    Handles formats like "1,500.00", "$1500", "€ 200", "15%".
    """
    MONEY_FIELDS = [
        "subtotal", "discount", "tax_amount", "shipping",
        "total_amount", "amount_paid", "amount_due",
    ]
    RATE_FIELDS = ["tax_rate"]
    LINE_ITEM_MONEY = ["quantity", "unit_price", "discount", "tax_rate", "total"]

    def parse_number(val) -> Optional[float]:
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            cleaned = re.sub(r"[,$€£¥₹%\s]", "", val)
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None

    for field in MONEY_FIELDS + RATE_FIELDS:
        if field in data:
            data[field] = parse_number(data[field])

    for item in data.get("line_items", []):
        for field in LINE_ITEM_MONEY:
            if field in item:
                item[field] = parse_number(item[field])

    return data


def _extract_vendor_address(text: str, vendor_name: str | None, vendor_gstin: str | None) -> str | None:
    """
    Extract vendor address from OCR text using context clues.
    # FIXED: Bug #1
    
    Args:
        text: Raw OCR text
        vendor_name: Vendor company name (if known)
        vendor_gstin: Vendor GSTIN (if known)
    
    Returns:
        Normalized address string or None
    """
    if not text:
        return None
    
    # Strategy: Find text block between vendor name (or start) and first GSTIN
    # Vendor address typically appears at top of invoice before buyer info
    
    lines = text.split('\n')
    address_lines = []
    capture = False
    vendor_found = False
    
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        
        # Start capturing after vendor name is found (or from beginning if no name)
        if vendor_name and vendor_name.upper() in line.upper():
            vendor_found = True
            capture = True
            continue  # Don't include the vendor name line itself
        elif not vendor_name and i < 10:  # Start from beginning if no vendor name
            vendor_found = True
            capture = True
        
        if capture and vendor_found:
            # Stop at GSTIN (marks end of vendor block)
            if vendor_gstin and vendor_gstin in line:
                break
            if re.search(r'\b\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z\d]\b', line):
                break
            # Stop at common section markers
            if re.search(r'\b(Bill\s*To|Sold\s*To|Customer|Consignee|Ship\s*To|Invoice\s*No|Date)\s*:', line, re.IGNORECASE):
                break
            # Skip obvious non-address lines
            if re.search(r'^(Phone|Email|Website|PAN|CIN|GST)', line, re.IGNORECASE):
                continue
            # Capture address-like lines (contains numbers, commas, location keywords)
            if line_stripped and (
                re.search(r'\d', line) or  # Has numbers (street number, PIN)
                ',' in line or  # Has commas (typical address separator)
                re.search(r'\b(Road|Street|Avenue|Lane|Building|Floor|City|State|Bangalore|Hyderabad|Mumbai|Delhi|Chennai|Pune|Kolkata)\b', line, re.IGNORECASE)
            ):
                address_lines.append(line_stripped)
            
            # Stop after collecting reasonable amount
            if len(address_lines) >= 5:
                break
    
    if not address_lines:
        return None
    
    # Normalize: join with commas, clean up spacing
    address = ', '.join(address_lines)
    address = re.sub(r'\s+', ' ', address).strip()
    address = re.sub(r',\s*,', ',', address)  # Remove double commas
    
    # Validation: must have at least one digit (for PIN or street number)
    if not re.search(r'\d', address):
        return None
    
    return address[:500] if len(address) <= 500 else None  # Cap length


def _extract_bill_to_address(text: str, bill_to_name: str | None) -> str | None:
    """
    Extract bill_to address from OCR text using section markers.
    # FIXED: Bug #2
    
    Args:
        text: Raw OCR text
        bill_to_name: Buyer company name (if known)
    
    Returns:
        Normalized address string or None
    """
    if not text:
        return None
    
    # Strategy: Find "Bill To" / "Sold To" / "Customer" section, capture until next GSTIN or section marker
    lines = text.split('\n')
    address_lines = []
    capture = False
    
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        
        # Start capturing after "Bill To" marker
        if re.search(r'\b(Bill\s*To|Sold\s*To|Customer|Buyer)\s*:', line, re.IGNORECASE):
            capture = True
            # Check if address is on same line
            remainder = re.sub(r'\b(Bill\s*To|Sold\s*To|Customer|Buyer)\s*:', '', line, flags=re.IGNORECASE).strip()
            if remainder and not (bill_to_name and bill_to_name.upper() in remainder.upper()):
                # Has content and it's not just the name
                if re.search(r'\d|,', remainder):  # Looks like address
                    address_lines.append(remainder)
            continue
        
        if capture:
            # Stop at GSTIN (marks boundary)
            if re.search(r'\b\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z\d]\b', line):
                break
            # Stop at next section
            if re.search(r'\b(Ship\s*To|Invoice\s*No|Date|Item|Description|HSN|Qty|Amount|GSTIN|State\s*Name)\s*:', line, re.IGNORECASE):
                break
            # Skip the bill_to name line itself if we know it
            if bill_to_name and bill_to_name.upper() in line.upper():
                continue
            # Capture address-like content
            if line_stripped and (
                re.search(r'\d', line) or
                ',' in line or
                re.search(r'\b(Road|Street|Avenue|Lane|Building|Floor|City|State|PIN|Bangalore|Hyderabad|Mumbai|Delhi)\b', line, re.IGNORECASE)
            ):
                address_lines.append(line_stripped)
            
            if len(address_lines) >= 5:
                break
    
    if not address_lines:
        return None
    
    address = ', '.join(address_lines)
    address = re.sub(r'\s+', ' ', address).strip()
    address = re.sub(r',\s*,', ',', address)
    
    if not re.search(r'\d', address):
        return None
    
    return address[:500] if len(address) <= 500 else None


def _extract_ship_to_address(text: str) -> str | None:
    """
    Extract ship_to address from OCR text using section markers.
    # FIXED: Bug #3
    
    Args:
        text: Raw OCR text
    
    Returns:
        Normalized address string or None
    """
    if not text:
        return None
    
    # Strategy: Find "Ship To" / "Delivery Address" / "Consignee" section
    lines = text.split('\n')
    address_lines = []
    capture = False
    
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        
        # Start capturing after "Ship To" marker
        if re.search(r'\b(Ship\s*To|Delivery\s*Address|Consignee|Shipping\s*Address)\s*:', line, re.IGNORECASE):
            capture = True
            remainder = re.sub(r'\b(Ship\s*To|Delivery\s*Address|Consignee|Shipping\s*Address)\s*:', '', line, flags=re.IGNORECASE).strip()
            if remainder and re.search(r'\d|,', remainder):
                address_lines.append(remainder)
            continue
        
        if capture:
            # Stop at GSTIN or next section
            if re.search(r'\b\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z\d]\b', line):
                break
            if re.search(r'\b(Invoice\s*No|Date|Item|Description|HSN|Qty|Amount|GSTIN|State\s*Name)\s*:', line, re.IGNORECASE):
                break
            # Capture address content
            if line_stripped and (
                re.search(r'\d', line) or
                ',' in line or
                re.search(r'\b(Road|Street|Avenue|Lane|Building|Floor|City|State|PIN|Bangalore|Hyderabad|Mumbai)\b', line, re.IGNORECASE)
            ):
                address_lines.append(line_stripped)
            
            if len(address_lines) >= 5:
                break
    
    if not address_lines:
        return None
    
    address = ', '.join(address_lines)
    address = re.sub(r'\s+', ' ', address).strip()
    address = re.sub(r',\s*,', ',', address)
    
    if not re.search(r'\d', address):
        return None
    
    return address[:500] if len(address) <= 500 else None


def _clean_extracted_fields(data: dict, text: str = "") -> dict:
    """Post-process LLM output to fix common formatting issues."""
    gstins_in_text = _extract_gstins_from_text(text)

    # FIXED: Bug #28 — Validate invoice_number before processing
    if data.get("invoice_number"):
        if not _is_valid_invoice_number(data["invoice_number"]):
            logger.warning("[llm_extractor] Invalid invoice_number rejected: %r", data["invoice_number"])
            data["invoice_number"] = None

    # Clean vendor tax_id and backfill from text if missing/invalid.
    vendor = data.get("vendor") or {}
    if isinstance(vendor, dict):
        vendor_norm = _normalize_gstin_candidate(vendor.get("tax_id"))
        if vendor_norm:
            vendor["tax_id"] = vendor_norm
        elif gstins_in_text:
            vendor["tax_id"] = gstins_in_text[0]
            logger.info("[llm_extractor] Backfilled vendor.tax_id from text: %s", gstins_in_text[0])
        else:
            vendor["tax_id"] = None
        data["vendor"] = vendor

    # Fix bill_to.name: LLM sometimes stuffs the full address block into name.
    # Heuristics: split on first newline, or strip if too long, or contains PIN code / state.
    bill_to = data.get("bill_to") or {}
    if isinstance(bill_to, dict) and bill_to.get("name"):
        name = str(bill_to["name"]).strip()
        # If it contains a newline, the first line is the name, rest is address
        if '\n' in name:
            parts = name.split('\n', 1)
            name = parts[0].strip()
            if not bill_to.get("address"):
                bill_to["address"] = parts[1].strip()
        # Strip trailing 6-digit Indian PIN codes from name
        name = re.sub(r'\s*[-,]?\s*\d{6}\s*$', '', name).strip()
        # If name still looks like it contains an address (comma + digits pattern), truncate
        addr_match = re.match(r'^([A-Za-z][A-Za-z &.\-\']{2,80?}?)(?:,\s*\d|\s+\d{6})', name)
        if addr_match:
            name = addr_match.group(1).strip()
        # Reject if over 80 chars after cleanup — likely still an address blob
        if len(name) > 80:
            logger.warning("[llm_extractor] bill_to.name too long (%d chars), clearing: %r", len(name), name[:80])
            name = None
        bill_to["name"] = name
        data["bill_to"] = bill_to

    # Clean bill_to tax_id and backfill from text (prefer GSTIN different from vendor).
    bill_to = data.get("bill_to") or {}
    if not isinstance(bill_to, dict):
        bill_to = {}
    bill_norm = _normalize_gstin_candidate(bill_to.get("tax_id"))
    if bill_norm:
        bill_to["tax_id"] = bill_norm
    else:
        vendor_gstin = (data.get("vendor") or {}).get("tax_id")
        replacement = None
        for g in gstins_in_text:
            if g != vendor_gstin:
                replacement = g
                break
        bill_to["tax_id"] = replacement
        if replacement:
            logger.info("[llm_extractor] Backfilled bill_to.tax_id from text: %s", replacement)
    data["bill_to"] = bill_to

    # FIXED: Bug #1 — Backfill vendor.address from text if missing
    vendor = data.get("vendor") or {}
    if isinstance(vendor, dict) and not vendor.get("address") and text:
        vendor_addr = _extract_vendor_address(text, vendor.get("name"), vendor.get("tax_id"))
        if vendor_addr:
            vendor["address"] = vendor_addr
            logger.info("[llm_extractor] Backfilled vendor.address from text")
        data["vendor"] = vendor

    # FIXED: Bug #2 — Backfill bill_to.address from text if missing
    bill_to = data.get("bill_to") or {}
    if isinstance(bill_to, dict) and not bill_to.get("address") and text:
        bill_to_addr = _extract_bill_to_address(text, bill_to.get("name"))
        if bill_to_addr:
            bill_to["address"] = bill_to_addr
            logger.info("[llm_extractor] Backfilled bill_to.address from text")
        data["bill_to"] = bill_to

    # FIXED: Bug #3 — Backfill ship_to.address from text if missing
    ship_to = data.get("ship_to") or {}
    if isinstance(ship_to, dict) and not ship_to.get("address") and text:
        ship_to_addr = _extract_ship_to_address(text)
        if ship_to_addr:
            ship_to["address"] = ship_to_addr
            logger.info("[llm_extractor] Backfilled ship_to.address from text")
        data["ship_to"] = ship_to

    return data


def _verify_tax_from_text(data: dict, text: str) -> dict:
    """Verify and correct tax_amount by summing explicit CGST/SGST/IGST values from raw text."""
    # Find all explicit CGST/SGST/IGST amounts — skip percentage values, grab the last number
    # Pattern: CGST <optional percentage(s)> <amount>
    # e.g. "ADD CGST 12% 12% 13632" → captures 13632
    # e.g. "CGST (9%) ₹1,234.56"    → captures 1234.56
    # Also handle parenthesised rate notation like "CGST (9%) ₹ 271.35"
    tax_amounts = re.findall(
        r'(?:CGST|SGST|IGST)\s*(?:\([^)]*\)\s*|[\d.]+\s*%?\s*)*[₹$€£]?\s*([\d,]+\.?\d*)',
        text, re.IGNORECASE
    )
    # Filter out matches that are clearly percentages (≤ 50) when amounts should be larger
    if tax_amounts:
        parsed = []
        for a in tax_amounts:
            try:
                v = float(a.replace(',', ''))
                parsed.append(v)
            except ValueError:
                pass
        # If all captured values ≤ 50, they are likely rates, not amounts — try a different pattern
        if parsed and all(v <= 50 for v in parsed):
            # Fallback: find the last number on lines containing CGST/SGST/IGST
            tax_amounts_alt = []
            for line in text.split('\n'):
                if re.search(r'(?:CGST|SGST|IGST)', line, re.IGNORECASE):
                    nums = re.findall(r'([\d,]+\.?\d*)', line)
                    if nums:
                        tax_amounts_alt.append(nums[-1])  # last number is likely the amount
            if tax_amounts_alt:
                tax_amounts = tax_amounts_alt
    if tax_amounts:
        total_tax = 0.0
        for a in tax_amounts:
            try:
                total_tax += float(a.replace(',', ''))
            except ValueError:
                pass
        if total_tax > 0:
            llm_tax = data.get("tax_amount")
            if llm_tax is None or abs(total_tax - llm_tax) > 0.5:
                logger.info(
                    "[llm_extractor] Correcting tax_amount: LLM=%s → text-derived=%.2f",
                    llm_tax, total_tax,
                )
                data["tax_amount"] = total_tax

    # Re-validate tax IDs after all corrections.
    vendor = data.get("vendor") or {}
    if isinstance(vendor, dict):
        vendor["tax_id"] = _normalize_gstin_candidate(vendor.get("tax_id"))
        data["vendor"] = vendor

    bill_to = data.get("bill_to") or {}
    if isinstance(bill_to, dict):
        bill_to["tax_id"] = _normalize_gstin_candidate(bill_to.get("tax_id"))
        data["bill_to"] = bill_to

    return data

def _try_regex_fallback(text: str) -> dict:
    """
    Last resort: use regex to extract key fields when LLM JSON fails.
    Delegates to the comprehensive extract_fields_with_regex().
    """
    logger.info("[llm_extractor] Running regex fallback extraction")
    return extract_fields_with_regex(text)


def extract_fields_with_regex(text: str) -> Dict[str, Any]:
    """
    Fallback: extract invoice fields using regex patterns.

    Used when the LLM is unavailable or returns invalid output.
    Covers the most common invoice field patterns.

    Args:
        text: Raw text from the invoice.

    Returns:
        Dictionary with extracted fields (partial — regex can't get everything).
    """
    result = _empty_invoice()

    # Invoice number patterns — skip common false matches like "e-Way", "Bill"
    # FIXED: Bug #28 — Extended garbage filter
    GARBAGE_INV_NUMS = {
        "e-Way", "e-way", "E-WAY", "Bill", "No", "Date", "the",
        "Dated", "Buyer", "GSTIN", "Tax", "Invoice", "Page",
        "Seller", "Total", "Amount", "Number", "Details"
    }
    
    inv_patterns = [
        # "Invoice No. XXX" / "Inv #: XXX" / "Bill No: XXX" / "Receipt No: XXX"
        r'(?:invoice|inv|bill|receipt|ref|order)\s*(?:no\.?|number|#|num|id)[\s.:]*\s*[:\s]?\s*[(\[]?\s*([\w][\w\-/]{1,29})',
        # "Invoice: XXX" or "Invoice # XXX" without the word "number/no"
        r'(?:invoice|inv)\s*[:#]\s*([\w][\w\-/]{1,29})',
        # Tally-style: "Invoice No." header with value within next few lines
        r'(?:invoice|inv|bill)\s*(?:no\.?|number|#|num)[\s.:]*(?:.*\n){1,5}\s*[(\[]?\s*([\w][\w\-/]{1,29})',
    ]
    for pat in inv_patterns:
        matches = re.finditer(pat, text, re.IGNORECASE)
        for m in matches:
            candidate = m.group(1).strip()
            
            # FIXED: Bug #28 — Structural validation
            # Skip if in garbage list (case-insensitive)
            if candidate.upper() in {g.upper() for g in GARBAGE_INV_NUMS}:
                continue
            # Must be 2-30 characters
            if len(candidate) < 2 or len(candidate) > 30:
                continue
            # Invoice numbers must contain at least one digit (skip pure-alpha like "MOHIT")
            if not re.search(r'\d', candidate):
                continue
            # Must not be purely numeric (likely page number or quantity)
            if candidate.isdigit() and len(candidate) < 4:
                continue
            # Skip if it looks like a street address (digit-digit-digit/digit)
            if re.match(r'^\d+-\d+-\d+', candidate):
                continue
            
            result["invoice_number"] = candidate
            break
        if result["invoice_number"]:
            break

    # Date patterns (numeric and alpha-month) — search across line boundaries
    date_patterns = [
        (r'(?:invoice\s*date|(?<!due\s)date|dated)\s*[:\s]*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})', "invoice_date"),
        (r'(?:invoice\s*date|(?<!due\s)date|dated)\s*[:\s]*\n?\s*(\d{1,2}[\-\s]*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*[\-\s]*\d{2,4})', "invoice_date"),
        (r'(\d{1,2}[\-](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*[\-]\d{2,4})', "invoice_date"),
        (r'(?:due\s*date)\s*[:\s]*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})', "due_date"),
        (r'(?:due\s*date)\s*[:\s]*(\d{1,2}[\-\s]*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*[\-\s]*\d{2,4})', "due_date"),
    ]
    for pat, field_name in date_patterns:
        if result.get(field_name):
            continue  # Already found
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            # Skip partial address matches like "3-1-67"
            remainder = text[m.end():]
            if remainder and remainder[0] == '/':
                continue  # Likely part of an address like 3-1-67/4/C
            result[field_name] = val

    # GSTIN pattern (15 alphanumeric)
    gstin_matches = _extract_gstins_from_text(text)
    if len(gstin_matches) >= 1:
        result["vendor"]["tax_id"] = gstin_matches[0]

    # Vendor name: look for company name near the top, before first GSTIN
    # or extract from "for <NAME>" at bottom, or "M/s <NAME>"
    if gstin_matches:
        first_gstin_pos = text.find(gstin_matches[0])
        header_text = text[:first_gstin_pos] if first_gstin_pos > 0 else text[:500]
        # Find all-caps company names (2+ words, may include PVT, LTD, etc.)
        name_match = re.search(
            r'(?:^|\n)\s*([A-Z][A-Z &.\-]{2,}(?:PVT|LTD|LLC|ENTERPRISES|TRADERS|AGENCIES|INDUSTRIES|SOLUTIONS|METALS|SERVICES|CORPORATION|COMPANY|CO)?\.?)\s*(?:\n|Invoice|Address|GSTIN)',
            header_text
        )
        if name_match:
            candidate = name_match.group(1).strip()
            # Skip headers like "Tax Invoice", "Page 1"
            if not re.match(r'^(Tax\s+Invoice|Page\s+\d|Invoice|INVOICE)$', candidate, re.IGNORECASE):
                result["vendor"]["name"] = candidate

    # "for <NAME>" pattern at bottom of invoice (common in Indian invoices)
    if not result["vendor"]["name"]:
        for_match = re.search(r'(?:for|declaration\s+for)\s+([A-Z][A-Z &.\-]+)', text)
        if for_match:
            result["vendor"]["name"] = for_match.group(1).strip()

    # FIXED: Bug #1 — Extract vendor address using helper function
    vendor_addr = _extract_vendor_address(text, result["vendor"].get("name"), result["vendor"].get("tax_id"))
    if vendor_addr:
        result["vendor"]["address"] = vendor_addr

    # Bill-to / Buyer name — look for name in the Buyer/Bill-to section
    # Strategy 1: Explicit headers (Buyer, Bill To, Sold To, Customer, Consignee, etc.)
    buyer_section = re.search(
        r'(?:buyer|bill\s*to|billed\s*to|sold\s*to|customer|consignee|details\s+of\s+receiver|name\s+of\s+the?\s+party)\s*(?:\(.*?\))?\s*[\n:](.{0,500}?)(?:GSTIN|State\s+Name|Contact|S\.?\s*No)',
        text, re.IGNORECASE | re.DOTALL
    )
    if buyer_section:
        section = buyer_section.group(1)
        for line in section.split('\n'):
            line = line.strip()
            # Match all-caps name at start (at least 4 chars), ignore trailing text
            m = re.match(r'^([A-Z][A-Z &.\-]{3,}?)(?:\s+(?:Date|Invoice|Contact|Address|Phone|Dispatch|Terms|dt\.)|\s*$)', line)
            if m:
                candidate = m.group(1).strip()
                if not re.match(r'^(GSTIN|State|Code|Terms|Plot|House|Door|Flat|Floor|Street|Road|Invoice|Tax)', candidate):
                    result["bill_to"]["name"] = candidate
                    break

    # Strategy 2: "M/s <Name>" pattern (common in Indian invoices for customer)
    if not result["bill_to"]["name"]:
        ms_match = re.search(r'M/s\.?\s+([A-Za-z][A-Za-z &.\-]+)', text)
        if ms_match:
            candidate = ms_match.group(1).strip()
            # Don't pick the vendor name again
            vendor_name = result.get("vendor", {}).get("name") or ""
            if candidate.upper() != vendor_name.upper():
                result["bill_to"]["name"] = candidate

    # Strategy 3: Second GSTIN section — find the name near the second GSTIN
    if not result["bill_to"]["name"]:
        gstin_pattern = r'\b\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z\d]{2}\b'
        gstin_positions = [(m.start(), m.group()) for m in re.finditer(gstin_pattern, text)]
        if len(gstin_positions) >= 2:
            # Look at the 150 characters before the second GSTIN for a name
            second_pos = gstin_positions[1][0]
            look_back = text[max(0, second_pos - 150):second_pos]
            vendor_name = result.get("vendor", {}).get("name") or ""
            # Try to find a capitalized name (mixed or all-caps) on lines before this GSTIN
            for line in reversed(look_back.split('\n')):
                line = line.strip()
                if not line or len(line) < 3:
                    continue
                # Skip address-like lines and labels
                if re.match(r'^(GSTIN|State|Code|Plot|House|Door|Flat|Floor|Street|Road|No\.|Ph|Tel|Email|Address|Pin)', line, re.IGNORECASE):
                    continue
                # Skip lines that are purely numeric or date-like
                if re.match(r'^[\d\s/\-.,]+$', line):
                    continue
                # Candidate: line with at least one letter and not matching the vendor
                candidate = re.match(r'^([A-Za-z][A-Za-z &.\-\']+)', line)
                if candidate:
                    name = candidate.group(1).strip()
                    if len(name) >= 3 and name.upper() != vendor_name.upper():
                        result["bill_to"]["name"] = name
                        break

    # Email
    email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', text)
    if email_match:
        result["vendor"]["email"] = email_match.group(0)

    # Phone
    phone_match = re.search(
        r'(?:phone|tel|mob|contact)\s*[:\s]*([+\d][\d\s\-().]{7,15})', text, re.IGNORECASE
    )
    if phone_match:
        result["vendor"]["phone"] = phone_match.group(1).strip()

    # Currency prefix — handles ₹ / $ / € / £ and also the "Rs." / "Rs" text form
    _CUR = r'(?:[₹$€£]|Rs?\.?)'
    # Amounts — first try specific labeled patterns, then broader ones
    amount_patterns = [
        (r'(?:sub\s*total|subtotal)\s*[:\s]*' + _CUR + r'?\s*([\d,]+\.?\d*)', "subtotal"),
        # "Taxable Value" or "Taxable Amount" — both map to subtotal (post-discount base)
        (r'(?:taxable\s+(?:value|amount))\s*[:\s]*' + _CUR + r'?\s*([\d,]+\.?\d*)', "subtotal"),
        (r'(?:total\s+tax\s+amount|total\s+tax)\s*[:\s]*' + _CUR + r'?\s*([\d,]+\.?\d*)', "tax_amount"),
        # "Grand Total", "Total Amount", "Net Payable", "Due Amount", "Payable Amount" etc.
        (r'(?:grand\s*total|total\s*amount|net\s*payable|total\s*due|'
         r'amount\s*(?:due|payable)|due\s*amount|payable\s*amount)\s*[:\s]*'
         + _CUR + r'?\s*([\d,]+\.?\d*)', "total_amount"),
    ]
    for pat, field_name in amount_patterns:
        if result.get(field_name) is not None:
            continue  # Already found
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = m.group(1).replace(',', '')
            try:
                parsed = float(val)
                if field_name == "tax_amount" and parsed > 1_000_000 and '.' not in m.group(1):
                    continue
                result[field_name] = parsed
            except ValueError:
                pass

    # Multi-line: "Taxable Value" header with number on a subsequent line (table layout)
    if result.get("subtotal") is None:
        m = re.search(r'(?:taxable\s+value).*?\n.*?\n\s*([\d,]+\.?\d+)', text, re.IGNORECASE)
        if m:
            try:
                result["subtotal"] = float(m.group(1).replace(',', ''))
            except ValueError:
                pass

    # Multi-line: look for "% Amount" header line, next line has: taxable_value rate tax_amount
    if result.get("tax_amount") is None or result.get("subtotal") is None:
        m = re.search(r'%\s*Amount\s*\n\s*([\d,]+\.?\d+)\s+([\d.]+)\s+([\d,]+\.?\d+)', text)
        if m:
            try:
                tv = float(m.group(1).replace(',', ''))
                ta = float(m.group(3).replace(',', ''))
                if result.get("subtotal") is None:
                    result["subtotal"] = tv
                if result.get("tax_amount") is None:
                    result["tax_amount"] = ta
            except ValueError:
                pass

    # If total_amount not found, look for the last "Total <amount>" line in the text
    if result.get("total_amount") is None:
        total_matches = re.findall(
            r'(?:^|\n)\s*\[?\s*Total\s*[:\s]*[₹$€£]?\s*([\d,]+\.?\d*)',
            text, re.IGNORECASE
        )
        if total_matches:
            try:
                result["total_amount"] = float(total_matches[-1].replace(',', ''))
            except ValueError:
                pass

    # Compute total from subtotal + tax if still missing
    if result.get("total_amount") is None:
        sub = result.get("subtotal")
        tax = result.get("tax_amount")
        if sub is not None and tax is not None:
            result["total_amount"] = sub + tax

    # Tax amount: sum CGST + SGST if no total tax amount found
    if result.get("tax_amount") is None:
        # Line-based: find lines containing CGST/SGST/IGST, take the last number on each
        tax_line_amounts = []
        for line in text.split('\n'):
            if re.search(r'(?:CGST|SGST|IGST)', line, re.IGNORECASE):
                nums = re.findall(r'([\d,]+\.?\d*)', line)
                # Filter out small numbers that are likely percentages
                candidates = []
                for n in nums:
                    try:
                        v = float(n.replace(',', ''))
                        candidates.append(v)
                    except ValueError:
                        pass
                # Take the largest number on the line (the amount, not the rate)
                # Skip lines where every number is ≤ 50 — those are rate percentages only
                if candidates:
                    max_cand = max(candidates)
                    if max_cand > 50:  # only append if at least one real amount found
                        tax_line_amounts.append(max_cand)
        if tax_line_amounts:
            result["tax_amount"] = sum(tax_line_amounts)

    # Derive tax_amount from grand total - subtotal when explicit tax lines are absent
    # (common in OCR text where CGST/SGST amounts are missing but totals are present)
    if result.get("tax_amount") is None:
        tot = result.get("total_amount")
        sub = result.get("subtotal")
        disc = result.get("discount") or 0.0
        if tot is not None and sub is not None and tot > sub:
            derived = round(tot - sub - disc, 2)
            if derived > 0:
                result["tax_amount"] = derived

    # If total_amount not found by label, find ₹ amounts and take the largest
    if result.get("total_amount") is None:
        rupee_amounts = re.findall(r'[₹]\s*([\d,]+\.?\d*)', text)
        if rupee_amounts:
            amounts = []
            for a in rupee_amounts:
                try:
                    amounts.append(float(a.replace(',', '')))
                except ValueError:
                    pass
            if amounts:
                result["total_amount"] = max(amounts)

    # FIXED: Bug P1-2 — Currency normalization using dedicated function
    # First, normalize any existing currency value from LLM
    if result.get("currency"):
        result["currency"] = _normalize_currency(result["currency"])
    
    # Then, override based on text analysis if needed
    gstin_found = bool(re.search(r'\b\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z\d]{2}\b', text))
    if gstin_found or '₹' in text or re.search(r'\bRs\.?\s*\d', text):
        result["currency"] = "INR"
    elif not result.get("currency"):
        # Only detect from symbols if LLM didn't provide valid currency
        if '$' in text or 'USD' in text:
            result["currency"] = "USD"
        elif '€' in text or 'EUR' in text:
            result["currency"] = "EUR"
        else:
            result["currency"] = "INR"  # Default for Indian invoices

    return result


# ═══════════════════════════════════════════════════════════════════════════
# EMPTY INVOICE TEMPLATE
# ═══════════════════════════════════════════════════════════════════════════

def _empty_invoice() -> dict:
    """Return an invoice dict with all fields set to null."""
    return {
        "invoice_number": None,
        "invoice_date": None,
        "due_date": None,
        "purchase_order_number": None,
        "vendor": {
            "name": None, "address": None, "email": None,
            "phone": None, "tax_id": None, "website": None,
        },
        "bill_to": {"name": None, "address": None, "email": None, "tax_id": None},
        "ship_to": {"name": None, "address": None},
        "line_items": [],
        "subtotal": None,
        "discount": None,
        "tax_rate": None,
        "tax_amount": None,
        "shipping": None,
        "total_amount": None,
        "amount_paid": None,
        "amount_due": None,
        "currency": None,
        "payment_terms": None,
        "payment_method": None,
        "bank_details": None,
        "notes": None,
    }
