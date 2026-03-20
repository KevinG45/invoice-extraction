# AGENT REFERENCE DOCUMENT
# ════════════════════════════════════════════
# READ THIS ENTIRE FILE BEFORE EVERY ACTION.
# UPDATE THE RELEVANT SECTION AFTER EVERY PROMPT.
# THIS FILE IS THE ONLY SOURCE OF TRUTH.
# DO NOT TRUST CONTEXT SUMMARIES IN PROMPTS.
# ONLY TRUST WHAT IS WRITTEN HERE.
# ════════════════════════════════════════════

YOU ARE AN EXPERT DATA SCIENTIST.
YOU ARE CRITICAL. YOU THINK BEFORE ACTING.
YOU NEVER MODIFY FILES NOT LISTED IN THE
ACTIVE PROMPT. NO EXCEPTIONS EVER.

═══════════════════════════════════════════════
SECTION 1 — PROJECT IDENTITY
═══════════════════════════════════════════════

Project: Invoice Extraction + RAG System
Location: invoice-extraction-current/
Entry point: main.py
API: api/main.py (FastAPI, port 8000)
Frontend: frontend/app.py (Streamlit, port 8501)
LLM: qwen2.5:3b via Ollama (local, no GPU)
Hardware: Windows or Linux, CPU only, no GPU
Invoice files: 30-100 files in data/input/INVOICES/

═══════════════════════════════════════════════
SECTION 2 — FILES THAT MUST NOT BE TOUCHED
═══════════════════════════════════════════════

These files are confirmed working.
Do not modify them unless the active prompt
explicitly names the file. No exceptions.

- core/pipeline.py
- core/detector.py
- core/pdf_extractor.py
- core/validator.py
- core/db.py
- rag/router.py
- rag/chunker.py
- rag/indexer.py
- rag/bm25_retriever.py
- rag/sql_retriever.py
- rag/agent.py
- api/main.py
- frontend/app.py
- main.py
- All run_*.py scripts

CONFIRMED WORKING BEHAVIOURS:
- Core pipeline initialisation: OK
- RAG agent functionality: OK
- API server startup: OK
- Batch processing: runs without crash
- Database structure: OK
- ChromaDB entries: 160 (stale data)
- Embeddings: OK

═══════════════════════════════════════════════
SECTION 3 — CONFIRMED BUGS AND THEIR STATUS
═══════════════════════════════════════════════

BUG 1 — LLM JSON parsing failures
Status: PARTIALLY FIXED
File to fix: core/llm_extractor.py
Symptom:
  [llm_extractor] JSON parse failed attempt 1:
  Invalid control character at line 20 col 223
  [llm_extractor] All retries exhausted.
  Running regex fallback.
Impact:
  2-3 retries wasted per invoice.
  Each retry approximately 30 seconds.
  Total wasted per invoice: 60-90 seconds.
Root cause:
  qwen2.5:3b outputs control characters and
  markdown wrapping when prompt is not strict.
Exact error observed: _clean_llm_response
Fix approach:
  Strict system prompt + clean user prompt +
  simple robust JSON cleaner
B4 result: JSON errors eliminated but extraction
  quality reduced (vendor_name now null),
  causing fallback stages to trigger (+6.7s).
  Total time increased 32.2s → 42.7s.

BUG 2 — /extract endpoint errors
Status: NOT FIXED
File to check: api/main.py
Likely cause: BUG 1 propagating bad output

BUG 3 — EasyOCR segfault
Status: NOT FIXED
File to fix: core/logo_extractor.py
Symptom: Hard crash on image files
Root cause: easyocr.Reader() called inside
  function, conflicts with Tesseract/OpenCV
Fix approach: subprocess isolation

BUG 4 — PaddleOCR errors
Status: NOT DIAGNOSED
File to check: core/ocr_engine.py
Symptom: Installed but producing errors
Impact: Silent fallback to Tesseract
Exact error: [FILL IN AFTER D1]
Error category: [FILL IN AFTER D1]

═══════════════════════════════════════════════
SECTION 4 — MEASUREMENTS AND DISCOVERIES
═══════════════════════════════════════════════

[All values below are filled in as prompts run]

PIPELINE STRUCTURE (filled in after A1):
Stage 1: detect_file_type()
Stage 2: _extract_text()
Stage 3: _extract_tables()
Stage 4: _extract_with_llm()
Stage 4b: _backfill_from_regex()
Stage 4c: extract_vendor_from_logo() [conditional]
Stage 4d: extract_customer_name() [conditional]
Stage 5: _merge_tables_into_line_items()
Stage 5b: _enhance_line_items_from_text()
Stage 6: validate_invoice()
"import time" existed originally: yes

TEST FILES (filled in after A3):
PDF test file full path: C:\Users\kmgs4\Documents\Christ Uni\invoice-extraction\invoice-extraction-current\data\input\INVOICES\PDF\32 DIVYA ENT INV EWAY.pdf
Image test file full path: C:\Users\kmgs4\Documents\Christ Uni\invoice-extraction\invoice-extraction-current\data\input\INVOICES\IMAGES\863_gst_bill_format_by_refrens_4e033c932d.jpg

BASELINE TIMING (filled in after A3):
PDF total time: 32.2s
Image total time: 71.6s
Slowest stage PDF: _extract_with_llm 29.9s
Slowest stage image: _extract_tables 39.6s
JSON parse failures observed in A3: no
Number of JSON failures: 0

TIMING AFTER JSON FIX (filled in after B4):
PDF total time after B4: 42.7s
Improvement: 32.2s → 42.7s (REGRESSION: +10.5s slower)

TIMING AFTER REGEX-FIRST (filled in after C3):
PDF total time after C3: [FILL IN]
Image total time after C3: [FILL IN]
Improvement B4 to C3: [FILL IN]

LLM EXTRACTOR STRUCTURE (filled in after C1):
Structure type: functions
Regex function name: extract_fields_with_regex
Regex currently called: after LLM
Main extraction function name and signature: extract_invoice_fields(text: str) -> dict
LLM result variable name inside function: data

═══════════════════════════════════════════════
SECTION 5 — RAG STATE
═══════════════════════════════════════════════

ChromaDB before reindex: 160 entries (stale)
ChromaDB after reindex: [FILL IN AFTER F2]
SQLite before reindex: stale incomplete data
SQLite after reindex: [FILL IN AFTER F2]
BM25 after rebuild: [FILL IN AFTER F2]

Batch run results (filled in after F1):
  Total attempted: [FILL IN]
  Succeeded: [FILL IN]
  Failed: [FILL IN]
  JSON failures appeared: [yes/no]

RAG test results (filled in after G2):
  Q1 sensible: [yes/no]
  Q2 sensible: [yes/no]
  Q3 sensible: [yes/no]
  Q4 sensible: [yes/no]
  Q5 sensible: [yes/no]

═══════════════════════════════════════════════
SECTION 6 — PROMPT COMPLETION LOG
═══════════════════════════════════════════════

Format for each entry after completion:
  PROMPT_ID — Status: PASSED or FAILED
  What was done: [one line]
  Files changed: [list]
  Key finding: [one line]

A1 — Status: PASSED
What was done: read pipeline.py, listed stages
Files changed: AGENT_REFERENCE.md only
Key finding: 10 stages found (6 main + 4 sub-stages), import time: yes
A2 — Status: PASSED
What was done: timing added to 10 stages
Files changed: core/pipeline.py, AGENT_REFERENCE.md
Key finding: import time added no
A3 — Status: PASSED
What was done: timed PDF and image extraction
Files changed: AGENT_REFERENCE.md only
Key finding: PDF 32.2s, image 71.6s, slowest: _extract_with_llm (PDF) / _extract_tables (image)
B1 — Status: PASSED
What was done: audited llm_extractor.py
Files changed: AGENT_REFERENCE.md only
Key finding: functions, LLM_MAX_RETRIES retries, re imported: yes
B2 — Status: PASSED
What was done: replaced system prompt, confirmed user prompt end
Files changed: core/llm_extractor.py, AGENT_REFERENCE.md
Key finding: prompts updated
B3 — Status: PASSED
What was done: replaced JSON cleaner body
Files changed: core/llm_extractor.py, AGENT_REFERENCE.md
Key finding: simpler cleaner installed
B4 — Status: FAILED
What was done: tested JSON fix on PDF
Files changed: AGENT_REFERENCE.md only
Key finding: JSON failures gone yes, time 32.2s → 42.7s (SLOWER, condition 2 failed)
C1 — Status: PASSED
What was done: audited llm_extractor structure
Files changed: AGENT_REFERENCE.md only
Key finding: functions, regex exists: yes (extract_fields_with_regex, called after LLM)
C2 — Status: NOT STARTED
C3 — Status: NOT STARTED
D1 — Status: NOT STARTED
D2 — Status: NOT STARTED
E1 — Status: NOT STARTED
E2 — Status: NOT STARTED
F1 — Status: NOT STARTED
F2 — Status: NOT STARTED
G1 — Status: NOT STARTED
G2 — Status: NOT STARTED
G3 — Status: NOT STARTED

═══════════════════════════════════════════════
SECTION 7 — HARD RULES
═══════════════════════════════════════════════

RULE 1:
Read this entire file before every action.
Do not skip any section.

RULE 2:
Only modify files explicitly named in the
active prompt. No exceptions ever.

RULE 3:
After every code change run:
  python run_regression_check.py
If new failures appear: STOP. Report exactly
what failed. Do not attempt to fix it here.

RULE 4:
Every prompt has a PASS CONDITION.
Do not proceed to the next step until
the current pass condition is met.

RULE 5:
If an unexpected error occurs:
STOP. Print the exact error in full.
Do not guess at a fix. Do not proceed.
Wait for instruction.

RULE 6:
Never delete or overwrite files in:
  outputs/extractions/
  chroma_db/

RULE 7:
After completing your prompt, update
Section 6 with status, findings, and
files changed. Also fill in any FILL IN
fields in Section 4 and Section 5.

RULE 8:
Speed improvements only via:
  - Fewer tokens sent to LLM
  - Fewer LLM calls
  - Eliminating retry waste
  - Skipping LLM when regex is confident
NOT via new models, new libraries,
async rewrites, or parallel processing.

RULE 9:
The context summaries written inside
prompts may be incomplete.
Always read this file for the true state.

═══════════════════════════════════════════════
SECTION 8 — STANDARD TEST COMMANDS
═══════════════════════════════════════════════

After any code change:
  python run_regression_check.py

Single file extraction (replace PATH):
  python -c "
  from core.pipeline import InvoicePipeline
  import time
  p = InvoicePipeline()
  start = time.time()
  r = p.run('PATH')
  print(f'Time: {time.time()-start:.1f}s')
  print('vendor_name:', r.get('vendor_name'))
  print('total_amount:', r.get('total_amount'))
  print('validated:',
    r.get('validation',{}).get('passed'))
  "

RAG query test:
  python -c "
  from rag.qa_chain import answer
  r = answer('how many invoices exist?')
  print(r['answer'], r['strategy'])
  "

PaddleOCR isolation test:
  python -c "
  from paddleocr import PaddleOCR
  ocr = PaddleOCR(use_angle_cls=True,
      lang='en', use_gpu=False, show_log=False)
  print('OK')
  "

EasyOCR isolation test (replace PATH):
  python -c "
  from core.logo_extractor import (
      extract_vendor_from_logo)
  print(extract_vendor_from_logo('PATH'))
  "
