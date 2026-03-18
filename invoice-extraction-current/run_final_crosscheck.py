"""
STEP 9 — FINAL CROSS CHECK
Run 4 files (2 PDFs, 2 images) through the pipeline and print a summary table.
"""
import sys, os, json, time, logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("LLM_MAX_RETRIES", "1")

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)-8s %(message)s")

from core.pipeline import InvoicePipeline
from core.config import DATA_DIR

# ── 4 test files: 2 PDFs, 2 images ──────────────────────────────────────
TEST_FILES = [
    ("GST001.pdf",       "PDF",   str(DATA_DIR / "PDF"   / "GST001.pdf")),
    ("GST003.pdf",       "PDF",   str(DATA_DIR / "PDF"   / "GST003.pdf")),
    ("invis1.jpg",       "Image", str(DATA_DIR / "IMAGES" / "invis1.jpg")),
    ("invoice.png",      "Image", str(DATA_DIR / "IMAGES" / "invoice.png")),
]

# ── Header fields we check ───────────────────────────────────────────────
HEADER_FIELDS = [
    "invoice_number", "invoice_date", "vendor.name", "vendor.tax_id",
    "bill_to.name", "subtotal", "tax_amount", "total_amount",
]

def get_nested(d, dotted_key):
    """Retrieve a dotted key like 'vendor.name' from a nested dict."""
    keys = dotted_key.split(".")
    val = d
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k)
        else:
            return None
    return val

def check_line_item(item):
    """Return (is_good, issues) for a single line item."""
    issues = []
    desc = item.get("description")
    if not desc:
        issues.append("no description")
    qty   = item.get("quantity")
    price = item.get("unit_price")
    total = item.get("total") or item.get("line_total")
    if qty is not None and price is not None and total is not None:
        expected = round(qty * price, 2)
        if abs(expected - total) > max(1.0, total * 0.05):
            issues.append(f"math: {qty}x{price}={expected} != {total}")
    elif total is None:
        issues.append("no total")
    return (len(issues) == 0, issues)


def run_crosscheck():
    pipeline = InvoicePipeline()
    rows = []

    for fname, ftype, fpath in TEST_FILES:
        print(f"\n{'='*60}")
        print(f"  Processing: {fname} ({ftype})")
        print(f"{'='*60}")

        if not os.path.exists(fpath):
            print(f"  ** FILE NOT FOUND: {fpath}")
            rows.append((fname, ftype, "FILE NOT FOUND", "", 0, 0, 0))
            continue

        start = time.time()
        try:
            result = pipeline.run(fpath)
        except Exception as e:
            print(f"  ** PIPELINE ERROR: {e}")
            rows.append((fname, ftype, "ERROR", str(e), 0, 0, 0))
            continue
        elapsed = time.time() - start

        # ── Assess header fields ─────────────────────────────────────────
        good_headers = []
        missing_headers = []
        for field in HEADER_FIELDS:
            val = get_nested(result, field)
            if val is not None and val != "" and val != 0:
                good_headers.append(field)
            else:
                missing_headers.append(field)

        # ── Assess line items ────────────────────────────────────────────
        items = result.get("line_items", [])
        items_good = 0
        items_wrong = 0
        item_details = []
        for idx, item in enumerate(items, 1):
            ok, issues = check_line_item(item)
            if ok:
                items_good += 1
            else:
                items_wrong += 1
                item_details.append(f"  Item {idx}: {', '.join(issues)}")

        # ── Print detail ─────────────────────────────────────────────────
        print(f"  Time: {elapsed:.1f}s")
        print(f"  Headers GOOD ({len(good_headers)}/{len(HEADER_FIELDS)}): {', '.join(good_headers)}")
        if missing_headers:
            print(f"  Headers MISSING: {', '.join(missing_headers)}")
        print(f"  Line items: {len(items)} found, {items_good} good, {items_wrong} wrong")
        if item_details:
            for d in item_details:
                print(d)

        # Validation warnings
        validation = result.get("validation", {})
        warnings = validation.get("warnings", [])
        if warnings:
            print(f"  Validation warnings ({len(warnings)}):")
            for w in warnings:
                print(f"    - {w}")

        rows.append((fname, ftype,
                      f"{len(good_headers)}/{len(HEADER_FIELDS)}",
                      ", ".join(missing_headers) if missing_headers else "—",
                      len(items), items_good, items_wrong))

    # ── Summary table ────────────────────────────────────────────────────
    print("\n")
    print("=" * 100)
    print("  FINAL CROSS-CHECK SUMMARY")
    print("=" * 100)
    header = f"{'File':<22} {'Type':<7} {'Hdrs GOOD':<12} {'Hdrs MISSING':<35} {'Items':<7} {'Good':<6} {'Wrong':<6}"
    print(header)
    print("-" * 100)
    for row in rows:
        fname, ftype, hdr_good, hdr_miss, n_items, n_good, n_wrong = row
        print(f"{fname:<22} {ftype:<7} {hdr_good:<12} {hdr_miss:<35} {n_items:<7} {n_good:<6} {n_wrong:<6}")
    print("-" * 100)
    print()


if __name__ == "__main__":
    run_crosscheck()
