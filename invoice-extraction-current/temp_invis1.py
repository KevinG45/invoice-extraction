import os, sys
os.environ["OCR_ENGINE"] = "tesseract"
os.environ["LLM_MAX_RETRIES"] = "1"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.pipeline import InvoicePipeline
from core.config import DATA_DIR

p = InvoicePipeline()
r = p.run(str(DATA_DIR / "IMAGES" / "invis1.jpg"))

v  = (r.get("vendor") or {}).get("name")
bt = (r.get("bill_to") or {}).get("name")
sub = r.get("subtotal")
tax = r.get("tax_amount")
tot = r.get("total_amount")
items = r.get("line_items") or []
val = r.get("validation") or {}
meta = r.get("metadata") or {}

print("=== invis1.jpg ===")
print(f"vendor_name   : {v}")
print(f"customer_name : {bt}")
print(f"subtotal      : {sub}")
print(f"tax_amount    : {tax}")
print(f"total_amount  : {tot}")
print(f"ocr_engine    : {meta.get('ocr_engine')}")
print(f"text_length   : {meta.get('text_length')}")
print(f"validated     : {val.get('passed')}")
print(f"warnings      : {val.get('warnings')}")
for it in items:
    print(f"  item {it.get('line_number')}: {repr(it.get('description',''))[:30]} qty={it.get('quantity')} price={it.get('unit_price')} total={it.get('total')}")
