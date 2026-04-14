"""
Delete obsolete documentation files that were created during the bug review process.
All bugs documented in these files have been fixed.
"""

import os

# Files to delete from the root directory
OBSOLETE_FILES = [
    r"C:\Users\kmgs4\Documents\Christ Uni\invoice-extraction\BUG_FIX_CHECKLIST.md",
    r"C:\Users\kmgs4\Documents\Christ Uni\invoice-extraction\CHECKPOINT_P0_FIXES.md",
    r"C:\Users\kmgs4\Documents\Christ Uni\invoice-extraction\CRITICAL_FINDINGS_SUMMARY.md",
    r"C:\Users\kmgs4\Documents\Christ Uni\invoice-extraction\EXECUTIVE_SUMMARY_FOR_USER.md",
    r"C:\Users\kmgs4\Documents\Christ Uni\invoice-extraction\CRITICAL_BUGS_ANALYSIS.md",
    r"C:\Users\kmgs4\Documents\Christ Uni\invoice-extraction\COMPREHENSIVE_CODE_REVIEW_REPORT.md",
]

if __name__ == "__main__":
    print("Cleaning up obsolete documentation files...")
    print("-" * 50)
    
    deleted = 0
    for filepath in OBSOLETE_FILES:
        if os.path.exists(filepath):
            os.remove(filepath)
            print(f"DELETED: {os.path.basename(filepath)}")
            deleted += 1
        else:
            print(f"NOT FOUND: {os.path.basename(filepath)}")
    
    print("-" * 50)
    print(f"Deleted {deleted} obsolete files.")
    print("\nRemaining valid documentation:")
    print("  - BUG_TRACKER.md (updated status)")
    print("  - INVOICE_RAG_FIX_PLAYBOOK.md (original playbook)")
    print("  - skills.md")
