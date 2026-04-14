@echo off
echo ============================================
echo Cleaning Up Obsolete Documentation Files
echo ============================================
echo.

cd /d "C:\Users\kmgs4\Documents\Christ Uni\invoice-extraction"

echo Deleting obsolete bug documentation files...
echo.

if exist "BUG_FIX_CHECKLIST.md" (
    del "BUG_FIX_CHECKLIST.md"
    echo DELETED: BUG_FIX_CHECKLIST.md
) else (
    echo NOT FOUND: BUG_FIX_CHECKLIST.md
)

if exist "CHECKPOINT_P0_FIXES.md" (
    del "CHECKPOINT_P0_FIXES.md"
    echo DELETED: CHECKPOINT_P0_FIXES.md
) else (
    echo NOT FOUND: CHECKPOINT_P0_FIXES.md
)

if exist "CRITICAL_FINDINGS_SUMMARY.md" (
    del "CRITICAL_FINDINGS_SUMMARY.md"
    echo DELETED: CRITICAL_FINDINGS_SUMMARY.md
) else (
    echo NOT FOUND: CRITICAL_FINDINGS_SUMMARY.md
)

if exist "EXECUTIVE_SUMMARY_FOR_USER.md" (
    del "EXECUTIVE_SUMMARY_FOR_USER.md"
    echo DELETED: EXECUTIVE_SUMMARY_FOR_USER.md
) else (
    echo NOT FOUND: EXECUTIVE_SUMMARY_FOR_USER.md
)

if exist "CRITICAL_BUGS_ANALYSIS.md" (
    del "CRITICAL_BUGS_ANALYSIS.md"
    echo DELETED: CRITICAL_BUGS_ANALYSIS.md
) else (
    echo NOT FOUND: CRITICAL_BUGS_ANALYSIS.md
)

if exist "COMPREHENSIVE_CODE_REVIEW_REPORT.md" (
    del "COMPREHENSIVE_CODE_REVIEW_REPORT.md"
    echo DELETED: COMPREHENSIVE_CODE_REVIEW_REPORT.md
) else (
    echo NOT FOUND: COMPREHENSIVE_CODE_REVIEW_REPORT.md
)

REM Also delete the Python cleanup script since we're using this bat file
if exist "cleanup_obsolete_docs.py" (
    del "cleanup_obsolete_docs.py"
    echo DELETED: cleanup_obsolete_docs.py
)

echo.
echo ============================================
echo Cleanup Complete!
echo ============================================
echo.
echo Remaining valid files:
echo   - BUG_TRACKER.md (updated status)
echo   - INVOICE_RAG_FIX_PLAYBOOK.md (original playbook)
echo   - skills.md (technical documentation)
echo.
pause
