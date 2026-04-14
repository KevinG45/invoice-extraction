@echo off
echo ==================== REPOSITORY CLEANUP ====================
echo Deleting obsolete files...
echo.

set "root=c:\Users\kmgs4\Documents\Christ Uni\invoice-extraction"
set "current=%root%\invoice-extraction-current"
set count=0

REM ===== Category 1 - Root level docs =====
echo [Category 1] Root level documentation...
del /Q "%root%\CHECKPOINT_P0_FIXES.md" 2>nul && set /A count+=1 && echo   - Deleted CHECKPOINT_P0_FIXES.md
del /Q "%root%\CRITICAL_BUGS_ANALYSIS.md" 2>nul && set /A count+=1 && echo   - Deleted CRITICAL_BUGS_ANALYSIS.md

REM ===== Current folder docs =====
echo [Category 1] Current folder documentation...
del /Q "%current%\HANDOFF_TASKS_A_D.md" 2>nul && set /A count+=1 && echo   - Deleted HANDOFF_TASKS_A_D.md
del /Q "%current%\TASKS_A_D_STATUS.md" 2>nul && set /A count+=1 && echo   - Deleted TASKS_A_D_STATUS.md
del /Q "%current%\TASKS_A_D_COMPLETION_SUMMARY.md" 2>nul && set /A count+=1 && echo   - Deleted TASKS_A_D_COMPLETION_SUMMARY.md
del /Q "%current%\SESSION_NOTES.md" 2>nul && set /A count+=1 && echo   - Deleted SESSION_NOTES.md
del /Q "%current%\RAG_ENHANCEMENT_PLAN.md" 2>nul && set /A count+=1 && echo   - Deleted RAG_ENHANCEMENT_PLAN.md
del /Q "%current%\HOW_TO_RUN_TASK_D.md" 2>nul && set /A count+=1 && echo   - Deleted HOW_TO_RUN_TASK_D.md
del /Q "%current%\PRODUCTION_READINESS_ANALYSIS.md" 2>nul && set /A count+=1 && echo   - Deleted PRODUCTION_READINESS_ANALYSIS.md
del /Q "%current%\PRODUCTION_FIXES_SUMMARY.md" 2>nul && set /A count+=1 && echo   - Deleted PRODUCTION_FIXES_SUMMARY.md
del /Q "%current%\REPORT_CHANGES_REQUIRED.md" 2>nul && set /A count+=1 && echo   - Deleted REPORT_CHANGES_REQUIRED.md
del /Q "%current%\AGENT_REFERENCE.md" 2>nul && set /A count+=1 && echo   - Deleted AGENT_REFERENCE.md

REM ===== Category 2 - Project/Presentation files =====
echo [Category 2] Project and presentation files...
del /Q "%current%\example document .docx" 2>nul && set /A count+=1 && echo   - Deleted example document .docx
del /Q "%current%\Project Report Guidelines.docx" 2>nul && set /A count+=1 && echo   - Deleted Project Report Guidelines.docx
del /Q "%current%\project_documentation (2).pdf" 2>nul && set /A count+=1 && echo   - Deleted project_documentation (2).pdf
del /Q "%current%\project_documentation (2).txt" 2>nul && set /A count+=1 && echo   - Deleted project_documentation (2).txt
del /Q "%current%\project_draft.pdf" 2>nul && set /A count+=1 && echo   - Deleted project_draft.pdf
del /Q "%current%\PROJECT PRESENTATION.pptx (1).pdf" 2>nul && set /A count+=1 && echo   - Deleted PROJECT PRESENTATION.pptx (1).pdf
del /Q "%current%\presentation_updated.pdf" 2>nul && set /A count+=1 && echo   - Deleted presentation_updated.pdf
del /Q "%current%\qa_prep.pdf" 2>nul && set /A count+=1 && echo   - Deleted qa_prep.pdf

REM ===== Category 3 - Temporary test files =====
echo [Category 3] Temporary and test files...
del /Q "%current%\temp_gst003.py" 2>nul && set /A count+=1 && echo   - Deleted temp_gst003.py
del /Q "%current%\temp_invis1.py" 2>nul && set /A count+=1 && echo   - Deleted temp_invis1.py
del /Q "%current%\temp_ocr_test.py" 2>nul && set /A count+=1 && echo   - Deleted temp_ocr_test.py
del /Q "%current%\test_routing.py" 2>nul && set /A count+=1 && echo   - Deleted test_routing.py
del /Q "%current%\test_extraction.py" 2>nul && set /A count+=1 && echo   - Deleted test_extraction.py
del /Q "%current%\test_address_extraction.py" 2>nul && set /A count+=1 && echo   - Deleted test_address_extraction.py

REM ===== Category 4 - Log files =====
echo [Category 4] Log files...
del /Q "%current%\extraction_stderr.log" 2>nul && set /A count+=1 && echo   - Deleted extraction_stderr.log
del /Q "%current%\extraction_stderr2.log" 2>nul && set /A count+=1 && echo   - Deleted extraction_stderr2.log
del /Q "%current%\extraction_stderr3.log" 2>nul && set /A count+=1 && echo   - Deleted extraction_stderr3.log
del /Q "%current%\api_server.log" 2>nul && set /A count+=1 && echo   - Deleted api_server.log
del /Q "%current%\rag_eval_output.log" 2>nul && set /A count+=1 && echo   - Deleted rag_eval_output.log

echo   - Deleting old extraction logs...
for %%f in ("%current%\logs\extraction_20260302_*.log") do (
    del /Q "%%f" 2>nul && set /A count+=1 && echo     * Deleted %%~nxf
)

REM ===== Category 6 - Version artifacts =====
echo [Category 6] Version artifacts...
del /Q "%current%\2.7.0" 2>nul && set /A count+=1 && echo   - Deleted 2.7.0
del /Q "%current%\=0.2.2" 2>nul && set /A count+=1 && echo   - Deleted =0.2.2

echo.
echo ==================== CLEANUP COMPLETE ====================
echo Total files deleted: %count%
echo.
echo Files KEPT (as requested):
echo   - skills.md (Category 1)
echo   - All test_results/* files (Category 5 - for comparison)
echo   - All data/input/INVOICES/* files
echo   - All outputs/* files
echo ===========================================================
pause
