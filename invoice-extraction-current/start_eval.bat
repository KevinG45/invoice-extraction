@echo off
REM Start RAG Evaluation Suite - Comprehensive Testing

echo ========================================
echo Starting RAG Evaluation Suite
echo 99 Test Cases - Full Bug Detection  
echo Estimated time: 2.5 hours (reduced from 106 tests)
echo ========================================
echo.

cd /d "c:\Users\kmgs4\Documents\Christ Uni\invoice-extraction\invoice-extraction-current"

echo Checking prerequisites...
python check_prereqs.py
if errorlevel 1 (
    echo.
    echo Prerequisites check failed!
    pause
    exit /b 1
)

echo.
echo ========================================
echo Starting Full Evaluation (99 test cases)
echo ========================================
echo.
echo Test Categories:
echo   - SQL queries (15)
echo   - BM25 lookup (11)
echo   - Vector semantic (10)
echo   - Hybrid queries (12)
echo   - Conversation memory (5 sequences - duplicates removed)
echo   - Edge cases (5)
echo   - Production ready (8 - duplicates removed)
echo   - Bug detection (33)
echo.

python -m rag.test_suite_extended --verbose

echo.
echo ========================================
echo RAG Evaluation Complete!
echo ========================================
echo.
echo Results saved to:
echo   - test_results/rag_summary.json
echo   - test_results/rag_per_query.csv
echo.
pause
