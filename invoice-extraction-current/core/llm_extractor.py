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

# ── Invoice extraction JSON schema prompt ──────────────────────────────────
EXTRACTION_PROMPT = """Extract all invoice fields from the text below. Return ONLY a JSON object — no markdown, no code blocks, no explanations. Start with {{ and end with }}.

RULES:
- Use null for any missing field — never omit fields
- currency: use "INR" if you see ₹, Rs, GSTIN, or any GST%; otherwise match the symbol found
- bill_to.name: the buyer company or person name ONLY — never include the address in this field
- All string values must be on a single line (no newlines inside strings)
- line_items[].total is the line's total amount (qty × unit_price before or after tax)
- For Indian GST invoices: tax_rate is typically 5, 12, 18, or 28 (percent)

OUTPUT this exact structure (replace values, keep all keys, use null for missing):
{{"invoice_number":null,"invoice_date":null,"due_date":null,"purchase_order_number":null,"currency":"INR","subtotal":null,"discount":null,"tax_amount":null,"shipping":null,"total_amount":null,"amount_paid":null,"amount_due":null,"tax_rate":null,"payment_terms":null,"payment_method":null,"bank_details":null,"notes":null,"vendor":{{"name":null,"address":null,"email":null,"phone":null,"tax_id":null,"website":null}},"bill_to":{{"name":null,"address":null,"email":null,"tax_id":null}},"ship_to":{{"name":null,"address":null}},"line_items":[{{"description":null,"hsn_sac":null,"quantity":null,"unit":null,"unit_price":null,"discount":null,"tax_rate":null,"total":null}}]}}

INVOICE TEXT:
{ocr_text}

JSON:"""


# ═══════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════

def extract_invoice_fields(text: str) -> dict:
    """
    Use local Ollama LLM to extract invoice fields from text.
    Retries up to LLM_MAX_RETRIES times on JSON parse failure.

    Args:
        text: Raw OCR / extracted text from an invoice.

    Returns:
        dict matching invoice schema (fields may be null).
    """
    if not text or len(text.strip()) < 10:
        logger.warning("[llm_extractor] Input text is too short, returning empty result")
        return _empty_invoice()

    prompt = EXTRACTION_PROMPT.format(ocr_text=text[:8000])  # Cap at 8k chars
    raw = ""

    for attempt in range(1, LLM_MAX_RETRIES + 1):
        logger.info("[llm_extractor] Extraction attempt %d/%d", attempt, LLM_MAX_RETRIES)
        try:
            raw = _call_ollama(prompt, json_mode=True)
            cleaned = _clean_llm_response(raw)
            data = json.loads(cleaned, strict=False)
            data = _normalize_numeric_fields(data)
            data = _clean_extracted_fields(data)
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


def _clean_extracted_fields(data: dict) -> dict:
    """Post-process LLM output to fix common formatting issues."""
    # Clean tax_id: strip prefixes like "GSTIN/UIN:", "GSTIN:", etc.
    vendor = data.get("vendor") or {}
    if isinstance(vendor, dict) and vendor.get("tax_id"):
        tid = vendor["tax_id"]
        if isinstance(tid, str):
            tid = re.sub(r'^.*?(?:GSTIN|UIN|GST|TIN)\s*[/:]\s*', '', tid, flags=re.IGNORECASE).strip()
            # Validate: GSTIN is exactly 15 alphanumeric chars
            gstin_match = re.search(r'\b(\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z\d]{2})\b', tid)
            if gstin_match:
                vendor["tax_id"] = gstin_match.group(1)

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

    # Also clean bill_to tax_id the same way as vendor tax_id
    bill_to = data.get("bill_to") or {}
    if not isinstance(bill_to, dict):
        bill_to = {}
        data["bill_to"] = bill_to
    if bill_to.get("tax_id"):
        tid = bill_to["tax_id"]
        if isinstance(tid, str):
            tid = re.sub(r'^.*?(?:GSTIN|UIN|GST|TIN)\s*[/:]\s*', '', tid, flags=re.IGNORECASE).strip()
            gstin_match = re.search(r'\b(\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z\d]{2})\b', tid)
            if gstin_match:
                bill_to["tax_id"] = gstin_match.group(1)

    # Backfill missing bill_to.tax_id from raw text if vendor GSTIN is known
    if not bill_to.get("tax_id"):
        vendor = data.get("vendor") or {}
        vendor_gstin = vendor.get("tax_id") if isinstance(vendor, dict) else None
        all_gstins = re.findall(r'\b(\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z\d]{2})\b', text)
        for g in all_gstins:
            if g != vendor_gstin:
                bill_to["tax_id"] = g
                logger.info("[llm_extractor] Backfilled bill_to.tax_id from text: %s", g)
                break

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
    inv_patterns = [
        # Same-line match: "Invoice No. XXX" or "Inv #: XXX" (may have leading paren/bracket)
        r'(?:invoice|inv)\s*(?:no|number|#|num)[\s.:]*\s*[:\s]?\s*[(\[]?\s*([A-Z0-9][\w\-/]+)',
        # Tally-style: "Invoice No." header with value within next few lines (greedy to skip names/addresses)
        r'(?:invoice|inv)\s*(?:no|number|#|num)[\s.:]*(?:.*\n){1,5}\s*[(\[]?\s*([A-Z0-9][\w\-/]+)',
    ]
    for pat in inv_patterns:
        matches = re.finditer(pat, text, re.IGNORECASE)
        for m in matches:
            candidate = m.group(1).strip()
            # Skip false positives
            if re.match(r'^(e[\-]?Way|Bill|No|Date|the|for|of|is|Dated|Buyer|GSTIN)$', candidate, re.IGNORECASE):
                continue
            if len(candidate) < 2:
                continue
            # Invoice numbers must contain at least one digit (skip pure-alpha like "MOHIT")
            if not re.search(r'\d', candidate):
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
    gstin_matches = re.findall(r'\b(\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z\d]{2})\b', text)
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

    # Currency detection — GSTIN is India-only, so any invoice with one must be INR
    gstin_found = bool(re.search(r'\b\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z\d]{2}\b', text))
    if gstin_found or '₹' in text or 'INR' in text or re.search(r'\bRs\.?\b', text):
        result["currency"] = "INR"
    elif '$' in text or 'USD' in text:
        result["currency"] = "USD"
    elif '€' in text or 'EUR' in text:
        result["currency"] = "EUR"

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
