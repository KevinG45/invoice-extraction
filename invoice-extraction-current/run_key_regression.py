"""
Prompt 8 — Fresh extraction of 3 key regression test files.
Forces re-extraction regardless of existing outputs.
No code changes — only uses env vars & calls existing pipeline.
"""
import sys
import os
import json

# Force tesseract so image files actually get OCR text
os.environ["OCR_ENGINE"] = "tesseract"
os.environ["LLM_MAX_RETRIES"] = "1"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.pipeline import InvoicePipeline
from core.config import DATA_DIR

def run_and_print(label: str, path: str):
    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"{'='*70}")
    pipeline = InvoicePipeline()
    try:
        result = pipeline.run(path)
    except Exception as e:
        print(f"  PIPELINE ERROR: {e}")
        return

    v  = result.get("vendor", {}) or {}
    bt = result.get("bill_to", {}) or {}
    items = result.get("line_items") or []
    val   = result.get("validation") or {}
    meta  = result.get("metadata") or {}

    sub = result.get("subtotal")
    tax = result.get("tax_amount")
    tot = result.get("total_amount")

    if sub is not None and tax is not None and tot and tot != 0:
        diff_pct = abs((sub + tax) - tot) / abs(tot) * 100
        total_match = f"YES ({diff_pct:.1f}%)" if diff_pct < 2.0 else f"NO ({diff_pct:.1f}%)"
    else:
        total_match = "N/A"

    print(f"  vendor_name   : {v.get('name')}")
    print(f"  customer_name : {bt.get('name')}")
    print(f"  subtotal      : {sub}")
    print(f"  tax_amount    : {tax}")
    print(f"  total_amount  : {tot}")
    print(f"  total_match   : {total_match}")
    print(f"  line_items    : {len(items)}")
    print(f"  ocr_engine    : {meta.get('ocr_engine')}")
    print(f"  text_length   : {meta.get('text_length')}")
    print(f"  validated     : {val.get('passed')}")
    print(f"  warnings      : {val.get('warnings')}")

    if items:
        print(f"  --- Line Items ---")
        for it in items:
            print(f"    [{it.get('line_number')}] {it.get('description','?')!r:30}  "
                  f"qty={it.get('quantity')}  price={it.get('unit_price')}  total={it.get('total')}")

if __name__ == "__main__":
    base = str(DATA_DIR)

    run_and_print(
        "GST003.pdf  (Prompt 5: tax fix — expect tax_amount≈542.70, total=3558)",
        os.path.join(base, "PDF", "GST003.pdf"),
    )
    run_and_print(
        "invis1.jpg  (Prompt 2: vendor_name, Prompt 3: customer, Prompt 4: line item math)",
        os.path.join(base, "IMAGES", "invis1.jpg"),
    )
    run_and_print(
        "invoice.png (Prompt 3: customer_name, Prompt 6: total fix)",
        os.path.join(base, "IMAGES", "invoice.png"),
    )
