import os

files = [
    r"C:\Users\kmgs4\Documents\Christ Uni\invoice-extraction\BUG_FIX_CHECKLIST.md",
    r"C:\Users\kmgs4\Documents\Christ Uni\invoice-extraction\CHECKPOINT_P0_FIXES.md", 
    r"C:\Users\kmgs4\Documents\Christ Uni\invoice-extraction\CRITICAL_FINDINGS_SUMMARY.md",
    r"C:\Users\kmgs4\Documents\Christ Uni\invoice-extraction\EXECUTIVE_SUMMARY_FOR_USER.md",
    r"C:\Users\kmgs4\Documents\Christ Uni\invoice-extraction\CRITICAL_BUGS_ANALYSIS.md",
    r"C:\Users\kmgs4\Documents\Christ Uni\invoice-extraction\COMPREHENSIVE_CODE_REVIEW_REPORT.md"
]

for f in files:
    if os.path.exists(f):
        os.remove(f)
        print(f"Deleted: {f}")
    else:
        print(f"Not found: {f}")
