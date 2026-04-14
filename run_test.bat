@echo off
cd /d "C:\Users\kmgs4\Documents\Christ Uni\invoice-extraction"
call .venv\Scripts\activate.bat
python test_router_line_items.py
