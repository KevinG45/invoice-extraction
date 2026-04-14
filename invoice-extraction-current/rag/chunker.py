"""
Invoice Chunker — breaks extracted invoice data into semantically
meaningful natural-language chunks for RAG indexing.

Enhanced chunking strategy (5 chunk types):
    1. "header"     — invoice summary (number, vendor, dates, totals, status)
    2. "vendor"     — vendor profile (name, GSTIN, address, contact, website)
    3. "financial"  — financial breakdown (subtotal, tax, discount, shipping, payment)
    4. "line_item"  — one per line item (description, HSN, qty, pricing)
    5. "full_text"  — combined narrative for broad semantic search

Input:  a single extraction JSON dict
Output: list of dicts, each with "text" and "metadata" keys
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def _safe(value, default: str = "") -> str:
    """Return str(value) if truthy, else default."""
    if value is None:
        return default
    return str(value)


def _money(value, currency: str = "") -> str:
    """Format a monetary value with optional currency."""
    if value is None:
        return ""
    cur = f" {currency}" if currency else ""
    return f"{value}{cur}"


def chunk_invoice(data: Dict[str, Any], filename: str = "unknown") -> List[Dict[str, Any]]:
    """
    Break an extracted invoice into natural-language chunks.

    Produces 5 chunk types for maximum retrieval coverage:
    - header: quick summary (good for BM25 keyword hits)
    - vendor: vendor profile (good for "who is vendor X" queries)
    - financial: amounts breakdown (good for "what was the tax on X")
    - line_item: one per item (good for product/service searches)
    - full_text: everything combined (good for vague semantic queries)
    """
    chunks: List[Dict[str, Any]] = []
    meta = data.get("metadata") or {}
    val = data.get("validation") or {}

    source_file = meta.get("source_file", filename)
    inv_num = data.get("invoice_number") or "N/A"
    inv_date = data.get("invoice_date")
    due_date = data.get("due_date")
    total = data.get("total_amount")
    currency = data.get("currency") or ""
    validated = val.get("passed", False)

    vendor = data.get("vendor") or {}
    bill_to = data.get("bill_to") or {}
    ship_to = data.get("ship_to") or {}
    vendor_name = vendor.get("name") or ""
    vendor_gstin = vendor.get("tax_id") or vendor.get("gstin") or ""
    bill_to_name = bill_to.get("name") or ""
    bill_to_gstin = bill_to.get("tax_id") or ""

    n_items = len(data.get("line_items") or [])

    # ── Shared metadata for all chunks from this invoice ──────────────
    base_meta = {
        "source_file": source_file,
        "invoice_id": inv_num,
        "vendor_name": vendor_name,
        "invoice_date": inv_date or "",
        "total_amount": total if total is not None else "",
        "validated": validated,
    }

    # ── 1. Header chunk ───────────────────────────────────────────────
    h_parts = [f"Invoice {inv_num}"]
    if vendor_name:
        h_parts.append(f"from {vendor_name}")
    if bill_to_name:
        h_parts.append(f"billed to {bill_to_name}")
    if inv_date:
        h_parts.append(f"dated {inv_date}")
    if due_date:
        h_parts.append(f"due {due_date}")
    if total is not None:
        h_parts.append(f"total {_money(total, currency)}")
    h_parts.append(f"{n_items} line item(s)")
    h_parts.append(f"validation {'passed' if validated else 'failed'}")

    chunks.append({
        "text": ", ".join(h_parts) + ".",
        "metadata": {**base_meta, "chunk_type": "header"},
    })

    # ── 2. Vendor chunk ───────────────────────────────────────────────
    v_parts = []
    if vendor_name:
        v_parts.append(f"Vendor: {vendor_name}")
    if vendor_gstin:
        v_parts.append(f"GSTIN: {vendor_gstin}")
    if vendor.get("address"):
        v_parts.append(f"Address: {vendor['address']}")
    if vendor.get("phone"):
        v_parts.append(f"Phone: {vendor['phone']}")
    if vendor.get("email"):
        v_parts.append(f"Email: {vendor['email']}")
    if vendor.get("website"):
        v_parts.append(f"Website: {vendor['website']}")
    if bill_to_name:
        v_parts.append(f"Customer: {bill_to_name}")
    if bill_to_gstin:
        v_parts.append(f"Customer GSTIN: {bill_to_gstin}")
    if bill_to.get("address"):
        v_parts.append(f"Customer address: {bill_to['address']}")
    if ship_to.get("name"):
        v_parts.append(f"Ship to: {ship_to['name']}")
    if ship_to.get("address"):
        v_parts.append(f"Shipping address: {ship_to['address']}")

    if v_parts:
        v_parts.insert(0, f"Vendor and customer details for invoice {inv_num}.")
        chunks.append({
            "text": " ".join(v_parts),
            "metadata": {**base_meta, "chunk_type": "vendor"},
        })

    # ── 3. Financial chunk ────────────────────────────────────────────
    f_parts = [f"Financial summary for invoice {inv_num}."]
    if data.get("subtotal") is not None:
        f_parts.append(f"Subtotal: {_money(data['subtotal'], currency)}.")
    if data.get("tax_amount") is not None:
        rate_str = f" at {data['tax_rate']}%" if data.get("tax_rate") is not None else ""
        f_parts.append(f"Tax: {_money(data['tax_amount'], currency)}{rate_str}.")
    if data.get("discount") is not None:
        f_parts.append(f"Discount: {_money(data['discount'], currency)}.")
    if data.get("shipping") is not None:
        f_parts.append(f"Shipping: {_money(data['shipping'], currency)}.")
    if total is not None:
        f_parts.append(f"Grand total: {_money(total, currency)}.")
    if data.get("amount_paid") is not None:
        f_parts.append(f"Amount paid: {_money(data['amount_paid'], currency)}.")
    if data.get("amount_due") is not None:
        f_parts.append(f"Amount due: {_money(data['amount_due'], currency)}.")
    if data.get("payment_terms"):
        f_parts.append(f"Payment terms: {data['payment_terms']}.")
    if data.get("payment_method"):
        f_parts.append(f"Payment method: {data['payment_method']}.")
    if data.get("bank_details"):
        f_parts.append(f"Bank details: {data['bank_details']}.")
    if data.get("purchase_order_number"):
        f_parts.append(f"PO number: {data['purchase_order_number']}.")

    if len(f_parts) > 1:
        chunks.append({
            "text": " ".join(f_parts),
            "metadata": {**base_meta, "chunk_type": "financial"},
        })

    # ── 4. Line item chunks ───────────────────────────────────────────
    for i, item in enumerate(data.get("line_items") or []):
        desc = item.get("description") or "N/A"
        if isinstance(desc, list):
            desc = ", ".join(str(d) for d in desc)

        li_parts = [f"Line item {i+1} from invoice {inv_num}"]
        li_parts.append(f"(vendor: {vendor_name})" if vendor_name else "")
        li_parts.append(f": {desc}")

        hsn = item.get("hsn_sac")
        if hsn:
            if isinstance(hsn, list):
                hsn = ", ".join(str(h) for h in hsn)
            li_parts.append(f", HSN/SAC: {hsn}")

        if item.get("quantity") is not None:
            unit = f" {item['unit']}" if item.get("unit") else ""
            li_parts.append(f", quantity: {item['quantity']}{unit}")
        if item.get("unit_price") is not None:
            li_parts.append(f", unit price: {_money(item['unit_price'], currency)}")
        if item.get("discount") is not None:
            li_parts.append(f", discount: {_money(item['discount'], currency)}")
        if item.get("tax_rate") is not None:
            li_parts.append(f", tax rate: {item['tax_rate']}%")
        if item.get("tax_amount") is not None:
            li_parts.append(f", tax amount: {_money(item['tax_amount'], currency)}")

        line_total = item.get("total") or item.get("line_total")
        if line_total is not None:
            li_parts.append(f", line total: {_money(line_total, currency)}")

        li_text = "".join(li_parts).rstrip(", ") + "."

        chunks.append({
            "text": li_text,
            "metadata": {
                **base_meta,
                "chunk_type": "line_item",
                "line_number": i + 1,
                "hsn_sac": str(hsn) if hsn else "",
                "description": desc[:200] if isinstance(desc, str) else str(desc)[:200],
            },
        })

    # ── 5. Full-text chunk (combined narrative for semantic search) ───
    full_parts = []
    full_parts.append(f"Invoice {inv_num} from {vendor_name or 'unknown vendor'}"
                      f" to {bill_to_name or 'unknown customer'}"
                      f" dated {inv_date or 'unknown date'}.")
    if vendor_gstin:
        full_parts.append(f"Vendor GSTIN {vendor_gstin}.")
    if vendor.get("address"):
        full_parts.append(f"Vendor located at {vendor['address']}.")

    for i, item in enumerate(data.get("line_items") or []):
        desc = item.get("description") or "item"
        if isinstance(desc, list):
            desc = ", ".join(str(d) for d in desc)
        qty = item.get("quantity")
        price = item.get("unit_price")
        lt = item.get("total") or item.get("line_total")
        item_str = f"Item {i+1}: {desc}"
        if qty is not None:
            item_str += f" (qty {qty}"
            if price is not None:
                item_str += f" x {price}"
            if lt is not None:
                item_str += f" = {lt}"
            item_str += ")"
        full_parts.append(item_str + ".")

    if data.get("subtotal") is not None:
        full_parts.append(f"Subtotal {_money(data['subtotal'], currency)}.")
    if data.get("tax_amount") is not None:
        full_parts.append(f"Tax {_money(data['tax_amount'], currency)}.")
    if total is not None:
        full_parts.append(f"Total {_money(total, currency)}.")
    if data.get("notes"):
        full_parts.append(f"Notes: {data['notes']}.")

    chunks.append({
        "text": " ".join(full_parts),
        "metadata": {**base_meta, "chunk_type": "full_text"},
    })

    logger.info("Chunked '%s' -> %d chunks (header + vendor + financial + %d items + full_text)",
                source_file, len(chunks), n_items)
    return chunks
