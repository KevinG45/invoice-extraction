@echo off
echo Removing unnecessary batch files...

cd /d "C:\Users\kmgs4\Documents\Christ Uni\invoice-extraction\invoice-extraction-current"

del "run_rag_eval.bat" 2>nul && echo DELETED: run_rag_eval.bat
del "run_production_eval.bat" 2>nul && echo DELETED: run_production_eval.bat

cd /d "C:\Users\kmgs4\Documents\Christ Uni\invoice-extraction"

del "cleanup_docs.bat" 2>nul && echo DELETED: cleanup_docs.bat
del "cleanup_obsolete_docs.py" 2>nul && echo DELETED: cleanup_obsolete_docs.py

echo.
echo Done! Remaining batch files:
echo   - invoice-extraction-current\start_eval.bat (RAG testing)
echo   - invoice-extraction-current\cleanup_files.bat (temp file cleanup)
echo.
echo This script will now delete itself...
del "%~f0"
