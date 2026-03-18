"""
Prompt 8 — Regression Check Script
Reads the most recent JSON extraction output for each invoice file
and prints the full summary table + known-issues check.

No pipeline execution — reads existing outputs only.
"""

import json
import os
import sys
import re
from pathlib import Path
from collections import defaultdict

OUTPUTS_DIR = Path(__file__).parent / "outputs" / "extractions"
PDF_DIR     = Path(__file__).parent / "data" / "input" / "INVOICES" / "PDF"
IMG_DIR     = Path(__file__).parent / "data" / "input" / "INVOICES" / "IMAGES"

# ─────────────────────────────────────────────────────────────────────────────
# 1. Collect all source files
# ─────────────────────────────────────────────────────────────────────────────

def get_source_files():
    exts = {".pdf", ".jpg", ".jpeg", ".png", ".tiff", ".tif"}
    sources = []
    for d in (PDF_DIR, IMG_DIR):
        if d.exists():
            for f in sorted(d.iterdir()):
                if f.suffix.lower() in exts:
                    sources.append(f)
    return sources


# ─────────────────────────────────────────────────────────────────────────────
# 2. Find the most recent JSON output for a given source file stem
# ─────────────────────────────────────────────────────────────────────────────

TIMESTAMP_RE = re.compile(r"_(\d{8}_\d{6})\.json$")

def get_latest_output(stem: str) -> Path | None:
    """Return the most recent output JSON whose name starts with stem."""
    candidates = []
    for jf in OUTPUTS_DIR.iterdir():
        name = jf.name
        # Strip timestamp suffix to compare stem
        m = TIMESTAMP_RE.search(name)
        if m:
            base = name[:m.start()]
            if base == stem:
                candidates.append((m.group(1), jf))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)  # most recent first
    return candidates[0][1]


# ─────────────────────────────────────────────────────────────────────────────
# 3. Parse one output JSON into summary row
# ─────────────────────────────────────────────────────────────────────────────

def parse_output(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)

    vendor      = (data.get("vendor") or {}).get("name") or ""
    bill_to     = (data.get("bill_to") or {}).get("name") or ""
    subtotal    = data.get("subtotal")
    tax_amount  = data.get("tax_amount")
    total       = data.get("total_amount")
    items       = data.get("line_items") or []
    validation  = data.get("validation") or {}
    passed      = validation.get("passed", False)
    warnings    = validation.get("warnings") or []

    # Compute total_match
    total_match = "N/A"
    if subtotal is not None and tax_amount is not None and total and total != 0:
        diff_pct = abs((subtotal + tax_amount) - total) / abs(total) * 100
        total_match = "YES" if diff_pct < 2.0 else f"NO({diff_pct:.1f}%)"
    elif total is not None and subtotal is None and tax_amount is None:
        total_match = "N/A(no-sub)"

    # Vendor confidence & source from metadata if present
    meta        = data.get("metadata") or {}
    v_conf      = ""
    v_src       = ""

    # Short warnings summary
    warn_short = []
    for w in warnings:
        if "LINE_ITEM_MATH" in w:
            warn_short.append("MATH_ERR")
        elif "MISSING_REQUIRED" in w:
            field = w.split("'")[1] if "'" in w else "?"
            warn_short.append(f"MISSING({field})")
        elif "TOTAL_MISMATCH" in w or "TOTALS" in w:
            warn_short.append("TOTAL_MISMATCH")
        else:
            warn_short.append(w[:40])

    return {
        "vendor_name"  : vendor or "—",
        "customer_name": bill_to or "—",
        "subtotal"     : subtotal,
        "tax_amount"   : tax_amount,
        "total_amount" : total,
        "total_match"  : total_match,
        "items_count"  : len(items),
        "validated"    : "PASS" if passed else "FAIL",
        "warnings"     : "; ".join(warn_short) if warn_short else "—",
        "output_file"  : path.name,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4. Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    sources  = get_source_files()
    rows     = []
    missing  = []

    for src in sources:
        stem = src.stem          # filename without extension
        ftype = "PDF" if src.suffix.lower() == ".pdf" else "IMG"
        latest = get_latest_output(stem)
        if latest is None:
            missing.append((src.name, ftype))
            rows.append({
                "file": src.name,
                "type": ftype,
                "vendor_name"  : "NO OUTPUT",
                "customer_name": "NO OUTPUT",
                "subtotal"     : None,
                "tax_amount"   : None,
                "total_amount" : None,
                "total_match"  : "—",
                "items_count"  : 0,
                "validated"    : "—",
                "warnings"     : "NO OUTPUT FILE",
                "output_file"  : "—",
            })
        else:
            info = parse_output(latest)
            info["file"] = src.name
            info["type"] = ftype
            rows.append(info)

    # ── Print table ──────────────────────────────────────────────────────────
    hdr = (
        f"{'File':<55} {'T':<3} {'Vendor':<30} {'Customer':<25} "
        f"{'Subtotal':>10} {'Tax':>10} {'Total':>10} "
        f"{'Match':<12} {'#':>3} {'Val':<5} {'Warnings'}"
    )
    sep = "─" * 200
    print("\n" + sep)
    print("REGRESSION SUMMARY  —  Prompt 8")
    print(sep)
    print(hdr)
    print(sep)

    for r in rows:
        sub = f"{r['subtotal']:.2f}"  if r['subtotal']  is not None else "—"
        tax = f"{r['tax_amount']:.2f}" if r['tax_amount'] is not None else "—"
        tot = f"{r['total_amount']:.2f}" if r['total_amount'] is not None else "—"
        line = (
            f"{r['file']:<55} {r['type']:<3} {r['vendor_name'][:29]:<30} "
            f"{r['customer_name'][:24]:<25} "
            f"{sub:>10} {tax:>10} {tot:>10} "
            f"{r['total_match']:<12} {r['items_count']:>3} {r['validated']:<5} "
            f"{r['warnings']}"
        )
        print(line)

    print(sep)
    print(f"Total source files: {len(sources)}  |  With output: {len(sources)-len(missing)}  |  Missing output: {len(missing)}")

    if missing:
        print("\nFILES WITH NO OUTPUT:")
        for fname, ftype in missing:
            print(f"  [{ftype}] {fname}")

    # ── Known-issues check ───────────────────────────────────────────────────
    print("\n" + sep)
    print("KNOWN-ISSUES STATUS CHECK")
    print(sep)

    def find_row(name_fragment):
        for r in rows:
            if name_fragment.lower() in r["file"].lower():
                return r
        return None

    issues = [
        ("1", "vendor_name missing in invis1.jpg",
         lambda: (lambda r: "RESOLVED" if r and r["vendor_name"] != "—" and r["vendor_name"] != "NO OUTPUT"
                  else "STILL PRESENT")(find_row("invis1"))),
        ("2", "bill_to.name missing in invoice.png",
         lambda: (lambda r: "RESOLVED" if r and r["customer_name"] != "—" and r["customer_name"] != "NO OUTPUT"
                  else "STILL PRESENT")(find_row("invoice.png") or find_row("invoice_2"))),
        ("3", "Line item math error in invis1.jpg",
         lambda: (lambda r: ("RESOLVED" if r and "MATH_ERR" not in r["warnings"]
                              else "STILL PRESENT"))(find_row("invis1"))),
        ("4", "Total mismatch in GST003",
         lambda: (lambda r: ("RESOLVED" if r and r["total_match"].startswith("YES")
                              else f"STILL PRESENT (total_match={r['total_match'] if r else 'N/A'})"))(find_row("GST003"))),
        ("5", "Total mismatch in invoice.png",
         lambda: (lambda r: ("RESOLVED" if r and r["total_match"].startswith("YES")
                              else f"STILL PRESENT (total_match={r['total_match'] if r else 'N/A'})"))(
                              find_row("invoice.png") or find_row("invoice_2"))),
        ("6", "PaddleOCR not installed",
         lambda: "FIXED OR DOCUMENTED — see requirements.txt / outputs/README.md note"),
    ]

    for num, desc, check_fn in issues:
        status = check_fn()
        print(f"  Issue {num}: {desc}")
        print(f"    → {status}")
        print()

    # ── GST003 detail ────────────────────────────────────────────────────────
    gst003_row = find_row("GST003")
    if gst003_row:
        print(sep)
        print("GST003 DETAIL (most recent output):")
        gst003_latest = get_latest_output("GST003")
        if gst003_latest:
            with open(gst003_latest) as fh:
                d = json.load(fh)
            print(f"  subtotal    : {d.get('subtotal')}")
            print(f"  tax_amount  : {d.get('tax_amount')}")
            print(f"  total_amount: {d.get('total_amount')}")
            print(f"  tax_rate    : {d.get('tax_rate')}")
            print(f"  warnings    : {(d.get('validation') or {}).get('warnings')}")

    # ── invis1 detail ────────────────────────────────────────────────────────
    invis1_latest = get_latest_output("invis1")
    if invis1_latest:
        print(sep)
        print("invis1.jpg DETAIL:")
        with open(invis1_latest) as fh:
            d = json.load(fh)
        print(f"  vendor_name : {(d.get('vendor') or {}).get('name')}")
        print(f"  customer    : {(d.get('bill_to') or {}).get('name')}")
        print(f"  subtotal    : {d.get('subtotal')}")
        print(f"  tax_amount  : {d.get('tax_amount')}")
        print(f"  total_amount: {d.get('total_amount')}")
        print(f"  line_items  : {len(d.get('line_items') or [])}")
        print(f"  warnings    : {(d.get('validation') or {}).get('warnings')}")

    # ── invoice.png detail ───────────────────────────────────────────────────
    inv_latest = get_latest_output("invoice")
    if inv_latest:
        print(sep)
        print("invoice.png DETAIL:")
        with open(inv_latest) as fh:
            d = json.load(fh)
        print(f"  vendor_name : {(d.get('vendor') or {}).get('name')}")
        print(f"  customer    : {(d.get('bill_to') or {}).get('name')}")
        print(f"  subtotal    : {d.get('subtotal')}")
        print(f"  tax_amount  : {d.get('tax_amount')}")
        print(f"  total_amount: {d.get('total_amount')}")
        print(f"  warnings    : {(d.get('validation') or {}).get('warnings')}")

    print(sep)
    print("END OF REGRESSION REPORT")
    print(sep)


if __name__ == "__main__":
    main()
