@echo off
REM RAG Evaluation Runner
REM Estimated time: 97 minutes

echo ========================================
echo Starting RAG Evaluation Suite
echo Estimated time: 97 minutes (~1.5 hours)
echo ========================================
echo.

cd /d "c:\Users\kmgs4\Documents\Christ Uni\invoice-extraction\invoice-extraction-current"

REM Check if virtual environment exists
if exist ".venv\Scripts\python.exe" (
    echo Using virtual environment Python
    .venv\Scripts\python.exe -m rag.test_suite_extended --verbose
) else (
    echo Using system Python
    python -m rag.test_suite_extended --verbose
)

echo.
echo ========================================
echo RAG Evaluation Complete!
echo Check test_results/rag_summary.json for results
echo ========================================
pause
