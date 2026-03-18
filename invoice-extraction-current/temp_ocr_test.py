"""
Test OCR text quality on invis1.jpg and invoice.png using tesseract directly,
then test the regex extractor on the text — stops before logo_extractor.
"""
import os, sys
os.environ["OCR_ENGINE"] = "tesseract"
os.environ["LLM_MAX_RETRIES"] = "1"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import DATA_DIR
from core.ocr_engine import run_ocr_on_image_file
from core.llm_extractor import extract_fields_with_regex

def test_image(name, path):
    print(f"\n{'='*70}")
    print(f"  {name}  (tesseract OCR only)")
    print(f"{'='*70}")
    try:
        ocr_result = run_ocr_on_image_file(str(path), engine="tesseract")
        text = ocr_result.get("full_text", "")
        print(f"  text_length  : {len(text)}")
        print(f"  --- First 600 chars ---")
        print(text[:600])
        print(f"  --- Regex extraction ---")
        fields = extract_fields_with_regex(text)
        print(f"  vendor_name  : {(fields.get('vendor') or {}).get('name')}")
        print(f"  customer_name: {(fields.get('bill_to') or {}).get('name')}")
        print(f"  subtotal     : {fields.get('subtotal')}")
        print(f"  tax_amount   : {fields.get('tax_amount')}")
        print(f"  total_amount : {fields.get('total_amount')}")
        items = fields.get("line_items") or []
        print(f"  line_items   : {len(items)}")
        for it in items:
            print(f"    [{it.get('line_number','')}] qty={it.get('quantity')} "
                  f"price={it.get('unit_price')} total={it.get('total')}")
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback; traceback.print_exc()

test_image("invis1.jpg", DATA_DIR / "IMAGES" / "invis1.jpg")
test_image("invoice.png", DATA_DIR / "IMAGES" / "invoice.png")
