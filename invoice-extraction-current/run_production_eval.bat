@echo off
echo ============================================================
echo RAG Production-Ready Evaluation (75 test cases)
echo ============================================================
echo.
echo This will take approximately 20-25 minutes
echo (~20 seconds per query)
echo.

cd /d "c:\Users\kmgs4\Documents\Christ Uni\invoice-extraction\invoice-extraction-current"

echo Starting evaluation...
python -m rag.test_suite_extended --verbose

echo.
echo Evaluation complete! Check test_results/ for detailed output.
pause
