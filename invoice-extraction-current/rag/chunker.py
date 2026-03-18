"""
Invoice Chunker — breaks extracted invoice data into semantically
meaningful natural-language chunks for RAG indexing.

Chunking strategy:
    1. One "header" chunk per invoice — natural-language summary of
       invoice number, vendor, dates, totals, validation status.
    2. One "line_item" chunk per line item — natural-language
       description with HSN, quantity, pricing, and parent invoice ref.

Input:  a single extraction JSON dict
Output: list of dicts, each with "text" and "metadata" keys
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def _fmt(value, suffix: str = "") -> str:
    """Format a value for display, returning empty string if None."""
    if value is None:
        return ""
    return f"{value}{suffix}"


def chunk_invoice(data: Dict[str, Any], filename: str = "unknown") -> List[Dict[str, Any]]:
    """
    Break an extracted invoice into natural-language chunks.

    Args:
        data: Extraction result dict (the full JSON structure).
        filename: Source invoice filename (for provenance tracking).

    Returns:
        List of dicts with 'text' and 'metadata' keys.
    """
    chunks: List[Dict[str, Any]] = []
    meta = data.get("metadata") or {}
    val = data.get("validation") or {}

    source_file = meta.get("source_file", filename)
    inv_num = data.get("invoice_number") or "N/A"
    inv_date = data.get("invoice_date")
    total = data.get("total_amount")
    currency = data.get("currency")
    validated = val.get("passed", False)

    vendor = data.get("vendor") or {}
    bill_to = data.get("bill_to") or {}
    vendor_name = vendor.get("name")
    vendor_gstin = vendor.get("tax_id") or vendor.get("gstin")

    # ── 1. Header chunk ──────────────────────────────────────────────────
    parts = [f"Invoice {inv_num}"]

    if vendor_name:
        gstin_part = f" (GSTIN: {vendor_gstin})" if vendor_gstin else ""
        parts.append(f"from vendor {vendor_name}{gstin_part}")

    if bill_to.get("name"):
        parts.append(f"billed to {bill_to['name']}")

    if inv_date:
        parts.append(f"dated {inv_date}")

    if data.get("due_date"):
        parts.append(f"due {data['due_date']}")

    if total is not None:
        cur = f" {currency}" if currency else ""
        parts.append(f"total amount {total}{cur}")

    if data.get("subtotal") is not None:
        parts.append(f"subtotal {data['subtotal']}")

    if data.get("tax_amount") is not None:
        rate_str = f" at {data['tax_rate']}%" if data.get("tax_rate") is not None else ""
        parts.append(f"tax {data['tax_amount']}{rate_str}")

    if data.get("discount") is not None:
        parts.append(f"discount {data['discount']}")

    if vendor.get("address"):
        parts.append(f"vendor address: {vendor['address']}")

    if vendor.get("phone"):
        parts.append(f"vendor phone: {vendor['phone']}")

    if vendor.get("email"):
        parts.append(f"vendor email: {vendor['email']}")

    if data.get("payment_terms"):
        parts.append(f"payment terms: {data['payment_terms']}")

    if data.get("purchase_order_number"):
        parts.append(f"PO number: {data['purchase_order_number']}")

    n_items = len(data.get("line_items") or [])
    parts.append(f"{n_items} line item(s)")
    parts.append(f"validated: {str(validated).lower()}")

    header_text = ", ".join(parts) + "."

    chunks.append({
        "text": header_text,
        "metadata": {
            "source_file": source_file,
            "invoice_id": inv_num,
            "chunk_type": "header",
            "vendor_name": vendor_name or "",
            "invoice_date": inv_date or "",
            "total_amount": total if total is not None else "",
            "validated": validated,
        },
    })

    # ── 2. Line item chunks ──────────────────────────────────────────────
    for i, item in enumerate(data.get("line_items") or []):
        desc = item.get("description") or "N/A"
        # Handle list-valued descriptions
        if isinstance(desc, list):
            desc = ", ".join(str(d) for d in desc)

        li_parts = [f"Line item from invoice {inv_num}: {desc}"]

        hsn = item.get("hsn_sac")
        if hsn:
            if isinstance(hsn, list):
                hsn = ", ".join(str(h) for h in hsn)
            li_parts.append(f"(HSN {hsn})")

        if item.get("quantity") is not None:
            li_parts.append(f"qty {item['quantity']}")
        if item.get("unit_price") is not None:
            li_parts.append(f"unit price {item['unit_price']}")
        if item.get("discount") is not None:
            li_parts.append(f"discount {item['discount']}")
        if item.get("tax_rate") is not None:
            li_parts.append(f"tax rate {item['tax_rate']}%")
        if item.get("tax_amount") is not None:
            li_parts.append(f"tax amount {item['tax_amount']}")

        line_total = item.get("total") or item.get("line_total")
        if line_total is not None:
            li_parts.append(f"line total {line_total}")

        li_text = ", ".join(li_parts) + "."

        chunks.append({
            "text": li_text,
            "metadata": {
                "source_file": source_file,
                "invoice_id": inv_num,
                "chunk_type": "line_item",
                "line_number": i + 1,
                "hsn_sac": str(hsn) if hsn else "",
                "description": desc[:200] if isinstance(desc, str) else str(desc)[:200],
            },
        })

    logger.info("Chunked '%s' -> %d chunks (1 header + %d line items)",
                source_file, len(chunks), n_items)
    return chunks
