# Invoice RAG System — Fix & Remediation Playbook

**Prepared by:** Senior DS Team  
**Date:** April 2, 2026  
**Status:** 🔴 FAILED PRODUCTION READINESS — 18 P0 bugs, DO NOT DEPLOY  
**System:** Invoice Extraction & RAG (Ollama / ChromaDB / SQLite)  
**Scope:** 36 bugs across extraction, retrieval, SQL, and hallucination layers  

---

## Table of Contents

1. [Team Structure & Ownership](#1-team-structure--ownership)
2. [Bug Assignment Matrix](#2-bug-assignment-matrix)
3. [LEAD A — NLP / LLM Engineer Prompts](#3-lead-a--nlp--llm-engineer-prompts)
4. [LEAD B — RAG / Search Engineer Prompts](#4-lead-b--rag--search-engineer-prompts)
5. [LEAD C — Data / SQL Engineer Prompts](#5-lead-c--data--sql-engineer-prompts)
6. [LEAD D — MLOps / QA Engineer Prompts](#6-lead-d--mlops--qa-engineer-prompts)
7. [LEAD E — Anti-Hallucination Architect Prompts](#7-lead-e--anti-hallucination-architect-prompts)
8. [skills.md Additions — Sections 13 & 14](#8-skillsmd-additions--sections-13--14)
9. [Testing Protocol & Acceptance Criteria](#9-testing-protocol--acceptance-criteria)

---

## 1. Team Structure & Ownership

Five senior specialists own distinct layers of the system. Every bug from the Microsoft assessment is assigned to exactly one owner. Each engineer operates with 10+ years of domain experience and is expected to **research best-in-class solutions before implementing**.

| Lead | Role | Files Owned |
|------|------|-------------|
| **LEAD A** | NLP / LLM Engineer | `core/llm_extractor.py`, `core/ocr_engine.py` |
| **LEAD B** | RAG / Search Engineer | `rag/bm25_retriever.py`, `rag/indexer.py`, `rag/chunker.py` |
| **LEAD C** | Data / SQL Engineer | `rag/sql_retriever.py`, `core/db.py`, `run_db_ingest.py` |
| **LEAD D** | MLOps / QA Engineer | `rag/router.py`, `rag/qa_chain.py`, `api/main.py` |
| **LEAD E** | Anti-Hallucination Architect | Cross-cutting: `rag/hallucination_guard.py` (new), `rag/hallucination_monitor.py` (new) |

---

## 2. Bug Assignment Matrix

| Bug # | Title | Severity | Owner | File(s) |
|-------|-------|----------|-------|---------|
| #1 | vendor.address never extracted | P0 | LEAD A | `llm_extractor.py:404` |
| #2 | bill_to.address partial extraction | P0 | LEAD A | `llm_extractor.py:421` |
| #3 | ship_to.address never extracted | P0 | LEAD A | `llm_extractor.py` |
| #4 | LLM prompt over-constrains bill_to | P0 | LEAD A | `llm_extractor.py:97` |
| #5 | BM25 does not index addresses/city | P0 | LEAD B | `bm25_retriever.py:117` |
| #6 | SQL GROUP BY returns wrong counts | P0 | LEAD C | `sql_retriever.py`, `db.py` |
| #7 | Router ignores follow-up context | P0 | LEAD D | `router.py`, `qa_chain.py` |
| #8 | No LLM answer validation vs context | P0 | LEAD E | `qa_chain.py` |
| #9 | Invoice number tokenisation incomplete | P1 | LEAD B | `bm25_retriever.py:79` |
| #10 | Date queries return wrong month | P1 | LEAD C | `sql_retriever.py` |
| #11 | Numeric SQL comparisons use strings | P1 | LEAD C | `sql_retriever.py` |
| #12 | GSTIN queries not exact-matched | P1 | LEAD B | `bm25_retriever.py` |
| #13 | Vector search >20s per query | P1 | LEAD B | `rag/indexer.py`, `qa_chain.py` |
| #14 | Multi-result output is unreadable prose | P1 | LEAD D | `qa_chain.py` |
| #15 | Conversation memory not persisted | P1 | LEAD D | `qa_chain.py` |
| #16 | No confidence scores in answers | P1 | LEAD E | `qa_chain.py` |
| #17 | Multi-page invoices truncated at 8K | P1 | LEAD A | `llm_extractor.py:130` |
| #18 | Low OCR quality not flagged | P2 | LEAD A | `core/ocr_engine.py` |
| #19 | Line item currency field missing | P2 | LEAD C | `db.py` |
| #20 | No duplicate invoice detection | P2 | LEAD C | `db.py` |
| #21 | No audit trail / access log | P2 | LEAD C | `db.py` |
| #22 | Error messages too technical for users | P2 | LEAD D | `qa_chain.py`, `api/main.py` |
| #23 | No rate limiting on RAG queries | P2 | LEAD D | `api/main.py` |
| #24 | BM25 sources ignored — LLM falls to SQL | P0 | LEAD D | `qa_chain.py` |
| #25 | SQL counts wrong (4 vs 50+ invoices) | P0 | LEAD C | `db.py`, `run_db_ingest.py` |
| #26 | System hangs 18 min on follow-up queries | P0 | LEAD D | `qa_chain.py`, `rag/indexer.py` |
| #27 | Vector results ignored; SQL fallback fires | P0 | LEAD D | `qa_chain.py` |
| #28 | Garbage data in DB (e-Way, Date as inv#) | P0 | LEAD C | `llm_extractor.py`, `db.py` |
| #29 | Currency comparison not normalized | P1 | LEAD C | `sql_retriever.py` |
| #30 | Invoice exact-match fails even for GST001 | P1 | LEAD B | `bm25_retriever.py` |
| #31 | Line items not searchable via BM25/SQL | P1 | LEAD B | `bm25_retriever.py`, `sql_retriever.py` |
| #32 | LLM generates wrong SQL column names | P1 | LEAD C | `sql_retriever.py:_SCHEMA` |
| #33 | SQL date range queries return 0 rows | P1 | LEAD C | `db.py`, `sql_retriever.py` |
| #34 | Location-based queries (city) fail | P1 | LEAD B | `bm25_retriever.py` |
| #35 | Avg query time 68s — 5s SLA breached | P1 | LEAD B | `rag/indexer.py`, `qa_chain.py` |
| #36 | Vague not-found answers with no suggestion | P2 | LEAD D | `qa_chain.py` |

---

## 3. LEAD A — NLP / LLM Engineer Prompts

**Bugs owned:** #1 #2 #3 #4 #17 #18  
**Files:** `core/llm_extractor.py`, `core/ocr_engine.py`

---

### PROMPT A-1 — Fix Address Extraction (Bugs #1 #2 #3 #4)

```
You are a senior NLP engineer with 10+ years extracting structured data from
semi-structured documents. You are fixing critical P0 bugs in llm_extractor.py.

CONTEXT:
  File: core/llm_extractor.py
  Function: _clean_extracted_fields() at line 404
  Function: EXTRACTION_PROMPT at line 92
  Function: extract_fields_with_regex() at line 536

ROOT CAUSES YOU MUST FIX:

  BUG #1 — vendor.address:
    The LLM prompt includes vendor.address in the schema but _clean_extracted_fields()
    NEVER validates or backfills it. The regex fallback extract_fields_with_regex()
    also has zero vendor address extraction logic.

  BUG #2 — bill_to.address:
    The existing logic at line 421-443 ONLY rescues the address when the LLM
    accidentally puts it inside bill_to.name (splits on newline). If LLM returns
    null for bill_to.address there is NO fallback extraction.

  BUG #3 — ship_to.address:
    grep -r 'ship_to' core/ shows ZERO post-processing. The DB column ship_to_address
    exists; the LLM prompt requests it; nothing extracts it.

  BUG #4 — LLM prompt at line 97 says:
    "bill_to.name: the buyer company or person name ONLY — never include the address
    in this field". This negative constraint causes the LLM to omit bill_to.address
    entirely rather than separate the two cleanly.

TASK — implement ALL of the following in one coherent edit:

  1. EXTRACTION_PROMPT (line 92):
     Remove the negative "never include address" instruction.
     Replace with a POSITIVE dual instruction:
       "bill_to.name: buyer company name only | bill_to.address: buyer full address"
     Add equivalent positive instructions for vendor.address and ship_to.address.

  2. _clean_extracted_fields() (line 404):
     After GSTIN cleaning, add three new backfill blocks — one each for
     vendor.address, bill_to.address, ship_to.address. Each block must:
       a. Skip if the field already has a non-empty, non-null value (LLM got it right).
       b. Run a targeted regex search on the raw OCR text parameter.
       c. For vendor.address: look for text blocks after vendor name / before GSTIN.
       d. For bill_to.address: scan after "Bill To", "Sold To", "Customer:" labels,
          capturing lines up to the next GSTIN or "State Name:" marker.
       e. For ship_to.address: scan after "Ship To", "Delivery Address:",
          "Consignee:" labels with the same termination markers.
       f. Normalise extracted addresses: strip leading/trailing whitespace, replace
          multiple spaces with single space, join multi-line with ", ".

  3. extract_fields_with_regex() (line 536):
     Add vendor_address extraction. Use the text block between the vendor name
     line and the first GSTIN occurrence. Strip known label words ("GSTIN", "State",
     "Phone", "Email") from the result.

ANTI-HALLUCINATION CONSTRAINT:
  Every address written to the database must come verbatim from the OCR text.
  Do NOT synthesise, infer, or complete addresses. If no address block is found,
  leave the field as None — do not fill "Unknown" or any placeholder.

TESTING REQUIREMENT:
  Write a pytest test function test_address_extraction() in tests/test_llm_extractor.py:
    - Loads 3 sample OCR text strings (vendor block, bill_to block, ship_to block)
    - Calls extract_invoice_fields() on each
    - Asserts vendor.address is not None
    - Asserts bill_to.address is not None
    - Asserts ship_to.address is not None
    - Asserts no address field equals "Unknown" or contains "null"

OUTPUT FORMAT:
  Provide the complete updated functions only — no full-file rewrites.
  Mark each changed line with: # FIXED: Bug #N
```

---

### PROMPT A-2 — Fix Multi-Page Truncation & OCR Quality (Bugs #17 #18)

```
You are a senior NLP engineer. You must fix two linked problems in the extraction
pipeline that cause data loss on real invoices.

CONTEXT:
  File: core/llm_extractor.py
  Line 130: prompt = EXTRACTION_PROMPT.format(ocr_text=text[:8000])  # Hard cap!
  File: core/ocr_engine.py (or wherever OCR confidence is available)

BUG #17 — 8K CHARACTER TRUNCATION:
  Multi-page invoices commonly exceed 8,000 chars of OCR text. Line items on pages
  2+ are silently dropped. The [:8000] slice must be replaced with a smarter strategy.

  Research and implement a SLIDING WINDOW approach:
    a. Split OCR text into overlapping windows of max 6000 chars with 500-char overlap.
    b. On window 1: extract all header fields (invoice_number, vendor, bill_to, totals).
    c. On windows 2+: extract ONLY line_items — do not re-extract header fields.
    d. Merge line_items lists from all windows, deduplicating by (description, total).
    e. Final header values always come from window 1 (authoritative).
    f. Max windows = 5 (handles 30K chars = ~30 pages).

  Add config option MAX_INVOICE_CHARS in core/config.py (default: 30000).

BUG #18 — OCR CONFIDENCE GATING:
  Low-quality scans produce garbage OCR that the LLM then confidently extracts,
  giving wrong values. No confidence check exists anywhere in the pipeline.

  Implement OCR quality gating:
    a. After OCR extraction, compute mean_confidence = avg of per-word confidences.
    b. If mean_confidence < 0.50: log WARNING, set metadata flag "ocr_quality": "low".
    c. If mean_confidence < 0.30: skip LLM extraction entirely, run only regex
       fallback, set metadata flag "ocr_quality": "very_low".
    d. Surface this flag in the API response and Streamlit UI as a warning banner.
    e. Do NOT reject the invoice — still store partial data but flag it.

TESTING REQUIREMENT:
  test_multipage_extraction():
    Feed 18000-char OCR text, verify line_items > 10, verify header fields present.

  test_ocr_confidence_gate():
    Feed mock OCR result with confidence=0.25, verify "ocr_quality" key equals
    "very_low" in returned metadata.
```

---

## 4. LEAD B — RAG / Search Engineer Prompts

**Bugs owned:** #5 #9 #12 #13 #30 #31 #34 #35  
**Files:** `rag/bm25_retriever.py`, `rag/indexer.py`, `rag/chunker.py`

---

### PROMPT B-1 — BM25 Index Completeness (Bugs #5 #12 #30 #31 #34)

```
You are a senior search engineer specialising in information retrieval for financial
documents. You have deep expertise in BM25, tokenisation, and hybrid search systems.
Fix five interconnected retrieval bugs in bm25_retriever.py.

CONTEXT:
  File: rag/bm25_retriever.py
  Method: _build_document_string() — assembles the indexed text per document
  Method: build_index() at line 117 — reads JSON files, builds BM25Okapi
  Method: search() — scores and ranks results
  Method: _tokenise() — tokenisation with stopwords + stemming

BUG #5 — ADDRESSES / CITY / STATE NOT INDEXED:
  _build_document_string() includes vendor.address and bill_to.address strings.
  BUT: metadata dict does NOT extract city/state/PIN as separate searchable fields.
  Queries like "invoices from Bangalore" fail because "Bangalore" is buried deep
  in an address string and BM25 scores it too low.

  Fix:
    a. In _build_document_string(), add a dedicated city/state block:
       Extract city using regex from vendor.address and bill_to.address.
       Add extracted city tokens TWICE in the document string (BM25 weight boost).
    b. In build_index() metadata dict: add "vendor_city", "bill_to_city",
       "vendor_state", "vendor_pin" fields parsed from address strings.
    c. In search(): if query matches _CITY_NAMES set, boost scores of results
       whose metadata vendor_city or bill_to_city matches, by factor 2.0.
       _CITY_NAMES must include at minimum:
         Bangalore, Bengaluru, Hyderabad, Chennai, Mumbai, Delhi, Pune,
         Kolkata, Ahmedabad, Quthubullapur

BUG #12 — GSTIN EXACT MATCH BROKEN:
  BM25 tokenises "36arkpc6820f1zz" as one token — it only scores well if the EXACT
  token appeared in the corpus. This breaks for any GSTIN not perfectly tokenised.

  Fix (direct metadata scan — bypass BM25 entirely for GSTIN):
    a. Before BM25 scoring, do a DIRECT METADATA SCAN:
         for i, m in enumerate(self.metadata):
           if m.get("vendor_gstin") == gstin or m.get("bill_to_gstin") == gstin:
             scores[i] = 999  # guaranteed top result
    b. Retain BM25 scoring for all non-GSTIN results.

BUG #30 — INVOICE NUMBER EXACT MATCH FAILS:
  Even "GST001" (no separators) fails to retrieve "GST001.pdf". Stemming
  corrupts the token, making the exact match unreliable.

  Fix (same pattern as GSTIN fix):
    a. In search(): extract invoice-number-like pattern from query:
         re.search(r'\b(GST|INV|BILL|PO)[-/]?\d+\b', query, re.I)
    b. If found, scan metadata for invoice_id exact match (after normalisation).
    c. Force score = 999 for that document if metadata invoice_id matches.
    d. Also scan source_file fields for "{invoice_num}.pdf" match.

BUG #31 — LINE ITEMS NOT SEARCHABLE:
  _build_document_string() currently includes only the first 5 line item
  descriptions via line_items_summary. "Search for Sticker line items" finds
  nothing even though the description exists in the JSON.

  Fix:
    a. In _build_document_string(): include ALL line item descriptions, not just first 5.
    b. Add HSN/SAC codes to the indexed string for product-code queries.
    c. In metadata: add "all_descriptions" as a joined string for filter use.

BUG #34 — LOCATION QUERIES (covered by Bug #5 fix above):
  Confirm _CITY_NAMES set is populated as listed in Bug #5 fix.

TESTING:
  test_gstin_exact_match():
    Build index with 3 docs, query by GSTIN, assert correct doc is rank 1, score=999.

  test_invoice_number_exact():
    Query "GST001", assert top result has source_file="GST001.pdf".

  test_city_search():
    Query "invoices from Bangalore", assert docs with vendor_city="Bangalore"
    rank above non-Bangalore docs.

  test_line_item_search():
    Query "Sticker", assert doc containing sticker line item is returned.
```

---

### PROMPT B-2 — Vector Search Performance (Bugs #13 #35)

```
You are a senior MLOps/search engineer. Vector search takes 20-33 seconds per query.
The production SLA is < 5 seconds for 95% of queries. This must be fixed now.

CONTEXT:
  File: rag/indexer.py — ChromaDB query_chunks() function
  File: rag/qa_chain.py — _vector_search() at line 279
  File: rag/query_expander.py — HyDE expansion (adds 1 full LLM call per query)

ROOT CAUSES:
  a. HyDE expansion = 1 extra Ollama call per vector query (~8-15s overhead).
  b. Embedding generation at query time with no caching.
  c. ChromaDB HNSW index not tuned for collection size.
  d. Follow-up queries repeat full vector search even when context is already known.

FIX PLAN:

  1. SELECTIVE HyDE:
     Only use HyDE for pure vector-strategy queries. For hybrid queries, SKIP HyDE.
     In qa_chain.py _vector_search(): the hybrid call at line 458 already passes
     use_hyde=True — change it to use_hyde=False.
     Expected saving: ~8-15s per hybrid query.

  2. QUERY EMBEDDING CACHE:
     In rag/indexer.py, add an LRU cache for embedding generation:
       from functools import lru_cache

       @lru_cache(maxsize=200)
       def _embed_query(query_text: str) -> tuple:
           # Normalise key: lowercase + strip
           # Returns embedding as tuple (hashable for lru_cache)
           embedding = model.encode(query_text.lower().strip())
           return tuple(embedding)
     Expected saving: eliminates re-embedding for repeated/similar queries.

  3. TIMEOUT GUARD:
     Wrap ChromaDB query in a concurrent.futures timeout:
       import concurrent.futures
       with concurrent.futures.ThreadPoolExecutor() as ex:
           future = ex.submit(collection.query, query_texts=[q], n_results=top_k)
           try:
               results = future.result(timeout=15)  # hard 15s limit
           except concurrent.futures.TimeoutError:
               logger.error("ChromaDB query timed out after 15s")
               return []

  4. ChromaDB HNSW TUNING:
     When creating the collection, set metadata:
       hnsw:space = "cosine"
       hnsw:construction_ef = 200
       hnsw:M = 16
     These are ChromaDB 1.0.0+ compatible parameters.

TESTING:
  test_vector_search_timeout():
    Mock ChromaDB to sleep 20s, verify function returns [] within 16s with error log.

  test_embedding_cache():
    Call _embed_query() twice with same text, verify underlying encode() called once.

  Benchmark:
    Run 10 vector queries before and after fix, assert p95 < 8s.
```

---

## 5. LEAD C — Data / SQL Engineer Prompts

**Bugs owned:** #6 #10 #11 #19 #20 #21 #25 #28 #29 #32 #33  
**Files:** `rag/sql_retriever.py`, `core/db.py`, `run_db_ingest.py`

---

### PROMPT C-1 — SQL Schema Accuracy & Wrong Query Results (Bugs #6 #10 #11 #25 #29 #32 #33)

```
You are a senior data engineer with deep expertise in SQLite, ORM design, and
LLM-generated SQL validation. Fix seven interconnected SQL and data integrity bugs.

CONTEXT:
  File: rag/sql_retriever.py — _SCHEMA string at top, _generate_sql(), _SYSTEM_PROMPT
  File: core/db.py — Invoice model, insert_extraction()

BUG #32 — LLM GENERATES WRONG COLUMN NAMES:
  The LLM writes SQL using guessed column names. Observed failures:
    - Uses "bill_to_gstin" for vendor GSTIN (correct column: vendor_tax_id)
    - Uses "description" on invoices table (column only exists in line_items)
    - Uses "has_multiple_line_items" (does not exist anywhere)

  Fix:
    a. Add EXAMPLE QUERIES section to _SYSTEM_PROMPT — at least 8 worked examples:
         -- Find invoices by vendor GSTIN:
         SELECT * FROM invoices WHERE vendor_tax_id = '36ARKPC6820F1ZZ'

         -- Search line items by description:
         SELECT i.invoice_number, i.vendor_name, l.description, l.total
         FROM invoices i JOIN line_items l ON l.invoice_id = i.id
         WHERE l.description LIKE '%sticker%'

         -- Count invoices per vendor:
         SELECT vendor_name, COUNT(*) as invoice_count
         FROM invoices GROUP BY vendor_name ORDER BY invoice_count DESC

         -- Invoices above an amount:
         SELECT invoice_number, vendor_name, total_amount
         FROM invoices WHERE total_amount > 10000 AND currency = 'INR'

         -- Date range query:
         SELECT * FROM invoices
         WHERE strftime('%Y-%m', invoice_date) = '2023-09'

         -- Validation status:
         SELECT i.invoice_number, v.passed, v.score
         FROM invoices i JOIN validation_reports v ON v.invoice_id = i.id
         WHERE v.passed = 0

    b. Add COLUMN ALIAS COMMENTS to _SCHEMA:
         -- NOTE: vendor GSTIN is in column vendor_tax_id (NOT vendor_gstin)
         -- NOTE: buyer GSTIN does not have a dedicated column
         -- NOTE: line item text is in line_items.description (NOT invoices.description)

    c. Add post-generation column validation:
       After _generate_sql(), check generated SQL against a whitelist of known columns.
       VALID_COLUMNS = {all column names from Invoice, LineItem, ValidationReport models}
       If an unknown column name appears, retry with an explicit correction hint in the
       next LLM call.

BUG #33 + #10 — DATE COMPARISONS RETURN WRONG ROWS:
  invoice_date stored as TEXT with mixed formats ("15/09/2023", "2023-09-15").
  String comparison is lexicographic, not temporal — range queries silently fail.

  Fix:
    a. In db.py insert_extraction():
       Normalise invoice_date to ISO format "YYYY-MM-DD" before storing.
       Use dateutil.parser.parse(date_str, dayfirst=True).strftime("%Y-%m-%d").

    b. Add one-time data migration (run at startup if needed):
         UPDATE invoices
         SET invoice_date = strftime('%Y-%m-%d',
             substr(invoice_date,7,4)||'-'||
             substr(invoice_date,4,2)||'-'||
             substr(invoice_date,1,2))
         WHERE invoice_date LIKE '__/__/____';

    c. In _SYSTEM_PROMPT, add date query rule:
       "Dates are stored as YYYY-MM-DD strings. For month queries use:
        WHERE strftime('%Y-%m', invoice_date) = '2023-09'
        For year queries: WHERE strftime('%Y', invoice_date) = '2024'"

BUG #11 — NUMERIC COMPARISONS USE STRING LITERALS:
  LLM generates: WHERE total_amount > "500" (string literal).
  SQLite coerces silently but produces wrong ordering for some values.

  Fix:
    a. Add to _SYSTEM_PROMPT:
       "Always use numeric literals for REAL columns, never string literals.
        Correct: WHERE total_amount > 500
        Wrong:   WHERE total_amount > '500'"
    b. In post-generation validation: regex-check for REAL columns compared to
       quoted values. Strip quotes before executing if found.

BUG #6 + #25 — GROUP BY RETURNS WRONG COUNTS (NIREL = 4 instead of 50+):
  Root cause: data ingestion failure — not all JSONs inserted into database.

  Diagnose and fix:
    a. Add startup validation in run_db_ingest.py:
         json_count = len(list(extractions_dir.glob("*.json")))
         db_count = session.query(func.count(Invoice.id)).scalar()
         if db_count < json_count * 0.95:
             logger.error("DB count %d vs file count %d — re-ingesting", db_count, json_count)

    b. Check source_file UNIQUE constraint: re-running ingest skips existing records
       silently. Add --force flag to overwrite existing rows.

    c. Fix vendor_name normalisation on insert:
       Store vendor_name as vendor.get("name", "").upper().strip()
       This prevents "NIREL DIGITALS" vs "Nirel Digitals" splitting GROUP BY counts.

BUG #29 — CURRENCY COMPARISON NOT NORMALISED:
  "Count invoices above 10000 rupees" should filter currency='INR' but does not.

  Fix:
    a. Add to _SYSTEM_PROMPT:
       "When a query mentions rupees/INR, add AND currency = 'INR' to the WHERE clause.
        When it mentions dollars/USD, add AND currency = 'USD'.
        Always filter by currency when an amount comparison is made."
    b. In router.py _extract_filters(): detect currency keywords and add to filters dict.

TESTING:
  test_sql_column_validation():
    Generate SQL for "show invoices from NIREL", verify SQL uses vendor_name,
    not vendor_company or any invalid column name.

  test_date_normalisation():
    Insert invoice with date="15/09/2023", query with strftime filter for "2023-09",
    verify 1 row returned.

  test_vendor_count():
    Ingest 10 JSONs all with vendor_name="TEST CORP", verify GROUP BY returns count=10.
```

---

### PROMPT C-2 — Data Quality: Garbage Detection & Duplicate Prevention (Bugs #19 #20 #21 #28)

```
You are a senior data engineer. Fix four data quality bugs that corrupt the database
and violate production finance system standards.

BUG #28 — GARBAGE DATA: INVOICE NUMBERS LIKE "e-Way", "Date", "Bill":
  The regex at llm_extractor.py:563 has a false-positive filter that misses "e-Way".
  Real invoice numbers must contain digits and follow a structural pattern.

  Fix in llm_extractor.py extract_fields_with_regex():
    a. Extend the false-positive list:
         GARBAGE_INV_NUMS = {
             "e-Way", "e-way", "Bill", "No", "Date", "the",
             "Dated", "Buyer", "GSTIN", "Tax", "Invoice", "Page"
         }

    b. Add structural validation — a valid invoice number must:
         - Contain at least one digit
         - Be between 2 and 30 characters
         - Not be purely alphabetic
         - Not match any word in GARBAGE_INV_NUMS (case-insensitive)

    c. In db.py insert_extraction():
       Add pre-insert guard:
         if not _is_valid_invoice_number(data.get("invoice_number")):
             logger.warning("Invalid invoice_number rejected: %r", data.get("invoice_number"))
             data["invoice_number"] = None

BUG #20 — NO DUPLICATE INVOICE DETECTION:
  Same invoice uploaded with a different filename bypasses the UNIQUE constraint
  on source_file. Two rows with the same invoice_number + vendor + total get stored.

  Fix in db.py insert_extraction():
    a. Before inserting, check for content-based duplicate:
         existing = session.query(Invoice).filter_by(
             invoice_number=data.get("invoice_number"),
             vendor_name=vendor.get("name"),
             total_amount=data.get("total_amount")
         ).first()

    b. If found: log WARNING "Duplicate invoice detected: {invoice_number}",
       skip insertion, return existing source_file.

    c. Add DB index for O(log n) duplicate detection:
         Index("ix_dedup", Invoice.invoice_number, Invoice.vendor_name, Invoice.total_amount)

BUG #19 — LINE ITEM CURRENCY FIELD MISSING:
  Line items have no currency column. Multi-currency invoices store amounts
  with ambiguous currency.

  Fix in db.py:
    a. Add column to LineItem model: currency = Column(String)
    b. In insert_extraction(): propagate invoice-level currency to each line item.
    c. Write migration: ALTER TABLE line_items ADD COLUMN currency TEXT;
       UPDATE line_items SET currency = (
           SELECT currency FROM invoices WHERE invoices.id = line_items.invoice_id
       );

BUG #21 — NO AUDIT TRAIL:
  Finance systems require audit logging for SOX compliance.

  Fix in db.py:
    a. Add AuditLog model:
         class AuditLog(Base):
             __tablename__ = "audit_log"
             id = Column(Integer, primary_key=True)
             table_name = Column(String, nullable=False)
             record_id = Column(Integer)
             action = Column(String)       # INSERT / UPDATE / DELETE
             user_id = Column(String)
             timestamp = Column(DateTime, default=datetime.utcnow)
             old_value = Column(Text)      # JSON string
             new_value = Column(Text)      # JSON string

    b. In insert_extraction(): after commit, write one AuditLog row:
         action="INSERT", table_name="invoices", new_value=json.dumps(summary)

    c. Expose get_audit_log(invoice_id) query helper in db.py.

TESTING:
  test_garbage_invoice_number():
    Call insert_extraction() with invoice_number="e-Way",
    verify DB stores invoice_number=None, not "e-Way".

  test_duplicate_detection():
    Insert same invoice twice (different source_file names),
    verify only 1 row exists in invoices table.

  test_audit_log_created():
    Insert one invoice, verify AuditLog has exactly 1 row for it.
```

---

## 6. LEAD D — MLOps / QA Engineer Prompts

**Bugs owned:** #7 #14 #15 #22 #23 #24 #26 #27 #36  
**Files:** `rag/router.py`, `rag/qa_chain.py`, `api/main.py`

---

### PROMPT D-1 — The Two-Query Anti-Pattern & Strategy Enforcement (Bugs #24 #27)

```
You are a senior MLOps engineer with expertise in RAG pipeline architecture.
You are fixing the most critical systemic bug: the "two-query anti-pattern" where
the LLM ignores retrieved BM25/vector context and silently falls back to SQL.

CONTEXT:
  File: rag/qa_chain.py — answer() function lines 377-579
  The flow: route → retrieve → build_prompt → LLM call

THE BUG:
  1. BM25 retrieves correct sources (e.g., 10 NIREL invoices)
  2. LLM receives those sources as context
  3. LLM IGNORES the context and generates a SQL query instead
  4. SQL fails (wrong column names or no data)
  5. LLM reports "not found" — FALSE NEGATIVE

  This pattern appears in 20+ test cases. It is the #1 cause of wrong answers.

ROOT CAUSE:
  qwen2.5:3b interprets the absence of a hard prohibition as permission to generate SQL.
  The context format also doesn't clearly signal "this IS the answer — use it".

TASK:

  1. STRATEGY LOCK in qa_chain.py answer():
     After retrieval, before building the prompt, insert:
       if strategy in ("bm25", "vector", "hybrid") and sources:
           lock_instruction = (
               "CRITICAL: You have retrieved invoice data above. "
               "You MUST answer directly from this context. "
               "Do NOT generate SQL. Do NOT say 'not found' if the context "
               "contains matching information."
           )
           user_parts.insert(0, lock_instruction)

  2. REWRITE _format_context() for maximum LLM clarity:
     Current format is ambiguous. New format:
       "=== INVOICE RECORD 1 (source: GST002.pdf) ==="
       "Invoice Number: INV-001"
       "Vendor Name: NIREL DIGITALS"
       "Vendor GSTIN: 36ARKPC6820F1ZZ"
       "Bill To: ACME CORP"
       "Invoice Date: 2024-01-15"
       "Total Amount: INR 15,240.00"
       "Tax Amount: INR 2,440.00"
       "Line Items: Printing Services x 10 @ 1,280.00"
       "=== END RECORD 1 ==="

     This signals clearly that this IS the answer data, not background context.

  3. POST-ANSWER FALSE-NEGATIVE CHECK:
     After getting answer_text from LLM:
       if strategy in ("bm25", "vector", "hybrid") and sources:
           not_found_phrases = ["not found", "no invoice", "does not exist",
                                "no results", "unable to find", "cannot find"]
           if any(p in answer_text.lower() for p in not_found_phrases):
               logger.error(
                   "FALSE NEGATIVE: LLM says not found but %d sources exist. Overriding.",
                   len(sources)
               )
               answer_text = _build_factual_answer_from_sources(bm25_or_vector_results)

  4. Implement _build_factual_answer_from_sources(results: List[dict]) -> str:
     This is a DETERMINISTIC fallback — no LLM call. Builds answer from metadata.

     def _build_factual_answer_from_sources(results: List[dict]) -> str:
         lines = [f"Found {len(results)} invoice(s) matching your query:"]
         for i, r in enumerate(results, 1):
             meta = r.get("metadata", {})
             source = meta.get("source_file") or r.get("source_file", "unknown")
             vendor = r.get("vendor_name") or meta.get("vendor_name", "Unknown Vendor")
             amount = r.get("total_amount") or meta.get("total_amount", "N/A")
             currency = r.get("currency", "INR")
             date = r.get("invoice_date") or meta.get("invoice_date", "N/A")
             inv_id = r.get("invoice_id") or meta.get("invoice_id", "N/A")
             lines.append(
                 f"{i}. {source} — Invoice: {inv_id} — {vendor} — "
                 f"{currency} {amount} — Date: {date}"
             )
         return "\n".join(lines)

TESTING:
  test_strategy_lock():
    Mock LLM to return "not found". Inject 3 real BM25 results with vendor names.
    Call answer(). Verify final answer contains at least one vendor name from sources.

  test_factual_fallback():
    Call _build_factual_answer_from_sources() with 2 result dicts.
    Verify output contains both source files and both amounts.

  test_false_negative_detection():
    Inject sources. Mock LLM to return "No invoice was found".
    Verify answer() returns factual override, not LLM output.
```

---

### PROMPT D-2 — Follow-Up Questions, Timeouts & Formatting (Bugs #7 #14 #15 #22 #23 #26 #36)

```
You are a senior QA/MLOps engineer. Fix seven UX and reliability bugs.

BUG #26 — 18-MINUTE TIMEOUTS ON FOLLOW-UP QUERIES:
  Evidence: Tests #50, #52, #56 all take 1000+ seconds.
  Pattern: all are hybrid strategy + vague + no named entities.
  Root cause: HyDE expansion in _vector_search() triggers an Ollama call that
  queues behind another pending request.

  Fix in qa_chain.py:

    a. Add GLOBAL 30-second retrieval timeout using concurrent.futures:
         import concurrent.futures

         def _retrieve_with_timeout(fn, *args, timeout_sec=30, **kwargs):
             with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                 future = ex.submit(fn, *args, **kwargs)
                 try:
                     return future.result(timeout=timeout_sec)
                 except concurrent.futures.TimeoutError:
                     logger.error("Retrieval timeout after %ds", timeout_sec)
                     return []

       Wrap every strategy retrieval call with _retrieve_with_timeout().

    b. FOLLOW-UP SHORTCUT — detect and handle in router.py:
       Add function is_follow_up(query: str) -> bool:
         words = query.strip().split()
         followup_starters = {"what", "how", "when", "where", "which", "who",
                              "tell", "show", "give", "and", "also"}
         return (len(words) <= 7 and
                 words[0].lower() in followup_starters)

       In qa_chain.py answer(): if is_follow_up(query) and memory.entities:
         # Skip ALL retrieval. Answer from memory entities directly.
         strategy = "memory_only"
         context = _format_memory_context(memory.entities)
         sources = memory.entities.get("last_sources", [])

    c. Add Ollama call timeout:
       In every client.chat() call, add: options={"temperature": LLM_TEMPERATURE, "timeout": 60}

BUG #7 — ROUTER MISSES FOLLOW-UP CONTEXT:
  Router is stateless. "What was the total?" after "Show me invoice GST001"
  routes to sql or hybrid, discarding established invoice context.

  Fix in router.py route_query():
    a. Add optional parameter: memory_entities: dict = None
    b. In qa_chain.py answer(): pass memory.get_current_entities() to route_query().
    c. In route_query(): if memory_entities and is_follow_up(query):
         if "invoice_number" in memory_entities:
             # Enrich the query with the known invoice context
             query = f"{query} [invoice: {memory_entities['invoice_number']}]"
         # Now route the enriched query — it will hit BM25 instead of hybrid

BUG #14 — MULTI-RESULT OUTPUT IS UNREADABLE PROSE:
  When SQL returns 4+ rows, LLM outputs a paragraph. Users need a table.

  Fix in qa_chain.py:
    a. In _format_sql_context(): if row_count > 3, prepend:
         "FORMATTING INSTRUCTION: This query returned {N} results.
          Format your answer as a markdown table with columns:
          Invoice #, Vendor, Date, Amount, Currency.
          End with a summary line: 'Showing N results.'"

    b. In _SYSTEM_PROMPT: add rule:
       "When presenting 4 or more invoice results, always use a markdown table.
        Always include a summary count line."

BUG #15 — CONVERSATION MEMORY NOT PERSISTED:
  _memory is a Python module-level object. It dies on every API restart.

  Fix:
    a. Add session_id: str = "default" parameter to answer() function.
    b. Store ConversationMemory objects in a module-level dict:
         _sessions: Dict[str, ConversationMemory] = {}
    c. Persist sessions to SQLite via a rag_sessions table:
         CREATE TABLE rag_sessions (
             session_id TEXT PRIMARY KEY,
             turns_json TEXT,
             entities_json TEXT,
             updated_at DATETIME
         );
    d. On each turn: upsert session row with updated turns_json.
    e. On startup: load sessions updated within last 24 hours into _sessions.
    f. Add API endpoint: DELETE /api/session/{session_id}

BUG #22 — TECHNICAL ERROR MESSAGES EXPOSED TO USERS:
  Fix in qa_chain.py and api/main.py:
    ERROR_MAP = {
        "SQL execution error":        "Unable to retrieve data. Please try rephrasing your question.",
        "Failed to connect to Ollama": "Processing service temporarily unavailable. Please try again.",
        "no such table":              "Database structure error. Please contact support.",
        "Retrieval timeout":          "Request timed out. Please try a simpler query.",
        "LLM generation failed":      "Could not generate an answer. Please try again.",
    }

    def _user_friendly_error(raw_error: str) -> str:
        for key, msg in ERROR_MAP.items():
            if key.lower() in raw_error.lower():
                return msg
        return "An unexpected error occurred. Please try again."

    Wrap answer() in try/except and apply _user_friendly_error().
    Include original error_code in response JSON for the support team (not shown to user).

BUG #23 — NO RATE LIMITING:
  Fix in api/main.py:
    pip install slowapi

    from slowapi import Limiter
    from slowapi.util import get_remote_address

    limiter = Limiter(key_func=get_remote_address)

    @app.post("/ask")
    @limiter.limit("10/minute")
    async def ask_question(request: Request, body: dict):
        ...

    Return HTTP 429 with Retry-After header when limit exceeded.

BUG #36 — VAGUE NOT-FOUND ANSWERS WITH NO SUGGESTIONS:
  Fix in _build_factual_answer_from_sources() and qa_chain.py:
    a. If answer contains "not found" but BM25 scores > 0 exist:
         top_suggestions = [r.get("source_file") for r in bm25_results[:3]]
         answer += f"\n\nDid you mean: {', '.join(top_suggestions)}?"

    b. For location queries: if city not found, list cities that do exist:
         available_cities = list({m.get("vendor_city") for m in bm25.metadata if m.get("vendor_city")})
         answer += f"\n\nNo vendors in {city}. Found vendors in: {', '.join(available_cities[:5])}."

TESTING:
  test_timeout_fires_30s():
    Mock retrieval to sleep 35s, verify function returns [] within 32s.

  test_followup_uses_memory():
    Ask "show invoice GST001" (stores entities), then ask "what is the total?".
    Verify second answer contains the amount from the first answer's context.

  test_rate_limit():
    Send 12 requests in under 60 seconds, verify 11th returns HTTP 429.

  test_multi_result_table():
    SQL returns 5 rows, verify prompt sent to LLM contains "markdown table" instruction.
```

---

## 7. LEAD E — Anti-Hallucination Architect Prompts

**Bugs owned:** #8 #16  
**Cross-cutting responsibility across ALL files.**

---

### PROMPT E-1 — Full Anti-Hallucination Framework (Bugs #8 #16)

```
You are the anti-hallucination architect for an invoice RAG system used by enterprise
finance teams. Hallucinations in this domain cause real financial loss.
Design and implement a comprehensive 5-layer hallucination prevention system.

EVIDENCE OF HALLUCINATION (from test suite):
  Test #42: Retrieved context showed "Quthubullapur, Hyderabad".
            LLM answered "Bangalore". → Factual hallucination.
  Test #18: 50+ NIREL sources retrieved.
            LLM said "not found". → False negative hallucination.
  The LLM is qwen2.5:3b — a small model that is more prone to confabulation.

IMPLEMENT A 5-LAYER ANTI-HALLUCINATION SYSTEM:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAYER 1 — PROMPT-LEVEL GROUNDING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Rewrite _SYSTEM_PROMPT in qa_chain.py to include:

  "GROUNDING RULE: Every factual claim in your answer — name, number, date,
   address, amount, GSTIN — MUST be taken verbatim from the CONTEXT above.
   If you cannot find a specific fact in the context, say:
   'This information was not present in the retrieved documents.'
   Do NOT guess. Do NOT complete partial information. Do NOT infer missing parts."

  "VERIFICATION STEP: Before writing each sentence, ask yourself:
   'Is this value present in the context above?' If yes: include it.
   If no: do not include it."

  "DO NOT generate SQL. DO NOT use knowledge from outside the provided context.
   Temperature is 0 — there is no excuse for invention."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAYER 2 — ENTITY CROSS-VALIDATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Create new file: rag/hallucination_guard.py

  import re
  from typing import List, Dict, Any

  class HallucinationGuard:

      def validate_answer(self, answer: str, context: str, sources: List[str]) -> Dict[str, Any]:
          """Cross-validate answer entities against retrieved context."""
          unverified = []

          # Extract numeric values from answer
          answer_numbers = re.findall(r'\b[\d,]+\.?\d*\b', answer)
          for num in answer_numbers:
              clean = num.replace(",", "")
              if clean not in context.replace(",", ""):
                  unverified.append(f"number:{num}")

          # Extract named entities (capitalised phrases, GSTINs, etc.)
          answer_entities = re.findall(r'\b[A-Z][A-Z\s&.]{2,}\b', answer)
          for entity in answer_entities:
              if entity.lower() not in context.lower():
                  unverified.append(f"entity:{entity.strip()}")

          # Extract GSTINs from answer
          answer_gstins = re.findall(r'\b\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z\d]\b', answer)
          for gstin in answer_gstins:
              if gstin not in context:
                  unverified.append(f"gstin:{gstin}")

          total_claims = len(answer_numbers) + len(answer_entities) + len(answer_gstins)
          score = len(unverified) / max(total_claims, 1)

          return {
              "verified": score < 0.10,
              "hallucination_score": round(score, 3),
              "unverified_claims": unverified,
              "confidence": "high" if score < 0.1 else "medium" if score < 0.3 else "low"
          }

      def check_false_negative(self, answer: str, sources: List[str]) -> bool:
          """Returns True if LLM says not-found but retrieved sources exist."""
          not_found_phrases = [
              "not found", "no invoice", "does not exist",
              "no results", "unable to find", "cannot find",
              "was not found", "are not found"
          ]
          answer_lower = answer.lower()
          if any(p in answer_lower for p in not_found_phrases) and len(sources) > 0:
              return True
          return False

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAYER 3 — CONFIDENCE SCORING (Bug #16)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Add confidence calculation to qa_chain.py answer() return dict:

  def _calculate_confidence(strategy: str, results: list,
                             hallucination_score: float) -> float:
      if strategy == "sql":
          base = 0.90    # SQL is deterministic
      elif strategy == "bm25":
          top_score = results[0].get("score", 0) if results else 0
          base = min(top_score / 10.0, 0.95)    # normalise BM25 score
      elif strategy == "vector":
          top_dist = results[0].get("distance", 1.0) if results else 1.0
          base = max(0, 1.0 - top_dist)
      elif strategy == "memory_only":
          base = 0.90    # memory answers are from prior verified context
      else:   # hybrid
          base = 0.75
      return round(base * (1.0 - hallucination_score), 3)

Add to answer() return dict:
  "confidence": confidence_value    # float 0.0–1.0

In Streamlit UI, display a colour-coded badge:
  Green (confidence > 0.8), Yellow (0.5–0.8), Red (< 0.5)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAYER 4 — FACTUAL OVERRIDE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Integrate with LEAD D's _build_factual_answer_from_sources(). In qa_chain.py answer():

  guard = HallucinationGuard()
  validation = guard.validate_answer(answer_text, context, sources)
  is_false_neg = guard.check_false_negative(answer_text, sources)

  if is_false_neg:
      answer_text = _build_factual_answer_from_sources(retrieval_results)
      validation["confidence"] = 0.95    # deterministic — high confidence
      result["answer_overridden"] = True
      result["override_reason"] = (
          f"LLM said not-found but {len(sources)} sources were retrieved"
      )
      logger.error("HALLUCINATION OVERRIDE: %s", result["override_reason"])

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAYER 5 — MONITORING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Create new file: rag/hallucination_monitor.py

  import json
  from datetime import datetime
  from pathlib import Path

  LOG_PATH = Path("logs/hallucination_log.jsonl")

  def log_answer_event(query: str, result: dict) -> None:
      LOG_PATH.parent.mkdir(exist_ok=True)
      event = {
          "timestamp": datetime.utcnow().isoformat(),
          "query": query,
          "strategy": result.get("strategy"),
          "sources_count": len(result.get("sources", [])),
          "hallucination_score": result.get("hallucination_score", 0),
          "answer_overridden": result.get("answer_overridden", False),
          "confidence": result.get("confidence", 0),
      }
      with open(LOG_PATH, "a", encoding="utf-8") as f:
          f.write(json.dumps(event) + "\n")

  def daily_summary() -> dict:
      if not LOG_PATH.exists():
          return {}
      events = [json.loads(l) for l in LOG_PATH.read_text().splitlines() if l.strip()]
      overrides = [e for e in events if e.get("answer_overridden")]
      return {
          "total_queries": len(events),
          "override_count": len(overrides),
          "override_rate_pct": round(100 * len(overrides) / max(len(events), 1), 1),
          "avg_confidence": round(sum(e.get("confidence", 0) for e in events) / max(len(events), 1), 3),
          "worst_queries": sorted(events, key=lambda e: e.get("hallucination_score", 0), reverse=True)[:5],
      }

Expose endpoint: GET /api/hallucination_stats → returns daily_summary()

TESTING:
  test_entity_cross_validation():
    context = "Vendor: NIREL DIGITALS, City: Hyderabad"
    answer = "The vendor is NIREL DIGITALS, located in Bangalore"
    result = guard.validate_answer(answer, context, [])
    assert result["verified"] == False
    assert any("Bangalore" in c for c in result["unverified_claims"])

  test_false_negative_detection():
    sources = ["GST001.pdf", "GST002.pdf"]
    answer = "No invoice was found for your query"
    assert guard.check_false_negative(answer, sources) == True

  test_confidence_high_sql():
    result = answer("How many invoices total?")    # routes to SQL
    assert result["confidence"] >= 0.85

  test_hallucination_log_written():
    Run answer() once.
    Verify hallucination_log.jsonl has exactly 1 new line appended.
```

---

## 8. skills.md Additions — Sections 13 & 14

> **Instruction:** Append the following two sections verbatim to the end of `skills.md`. They replace nothing — add after the existing Section 12.

---

### Section 13 — Anti-Hallucination Framework (NEW)

```markdown
## 13. Anti-Hallucination Framework

### Architecture Overview

Five layers prevent confabulation from qwen2.5:3b, the QA LLM:

| Layer | Mechanism | Location |
|-------|-----------|----------|
| 1 | Prompt grounding — every claim must be verbatim from context | `qa_chain.py:_SYSTEM_PROMPT` |
| 2 | Entity cross-validation — post-answer entity verification | `rag/hallucination_guard.py` |
| 3 | Confidence scoring — numeric confidence 0.0–1.0 per answer | `qa_chain.py:answer()` |
| 4 | Factual override — deterministic fallback on false negatives | `qa_chain.py:_build_factual_answer_from_sources()` |
| 5 | Monitoring — JSONL event log + daily summary endpoint | `rag/hallucination_monitor.py` |

### Key Classes and Functions

**rag/hallucination_guard.py**
- `HallucinationGuard.validate_answer(answer, context, sources) -> dict`
  - Returns: `verified`, `hallucination_score`, `unverified_claims`, `confidence`
- `HallucinationGuard.check_false_negative(answer, sources) -> bool`

**rag/qa_chain.py additions**
- `_build_factual_answer_from_sources(results: List[dict]) -> str`
  - Deterministic answer builder from metadata — no LLM call, always factually correct.
- `_calculate_confidence(strategy, results, hallucination_score) -> float`

**rag/hallucination_monitor.py**
- `log_answer_event(query, result_dict) -> None`
- `daily_summary() -> dict`

### Return Dict Contract for qa_chain.answer()

All callers must handle these fields (new in April 2026):

```python
{
    "answer": str,
    "strategy": str,
    "sources": List[str],
    "confidence": float,            # 0.0–1.0
    "hallucination_score": float,   # 0.0 = fully grounded
    "answer_overridden": bool,      # True if factual fallback was used
    "override_reason": str | None,  # Why override fired
    "is_existence_query": bool,
    "total_results": int,
}
```

### Anti-Hallucination Rules for All Engineers

1. `LLM_TEMPERATURE` MUST remain `0` for all QA calls — never increase.
2. Never remove the `CRITICAL RULE` block from `_SYSTEM_PROMPT`.
3. Never use HyDE for SQL-routed queries (SQL is already deterministic).
4. Context format MUST use `=== INVOICE RECORD N ===` delimiters.
5. Strategy lock MUST be applied whenever BM25/vector sources are present.
6. `_build_factual_answer_from_sources()` must never call the LLM.
```

---

### Section 14 — Production Readiness & Bug Fix Registry (NEW)

```markdown
## 14. Production Readiness & Bug Fix Registry

### P0 Bugs Fixed (April 2026)

| Bug | Description | Fix Location |
|-----|-------------|--------------|
| #1 | vendor.address extraction added | `_clean_extracted_fields()`, regex fallback |
| #2 | bill_to.address backfill for null LLM returns | `_clean_extracted_fields()` |
| #3 | ship_to.address extraction implemented | `_clean_extracted_fields()` |
| #4 | Prompt changed: positive dual instruction for address fields | `EXTRACTION_PROMPT` |
| #5 | BM25 indexes city/state; city-boost in search() | `bm25_retriever.py` |
| #6 | DB ingest count validation; vendor_name UPPER() normalised | `run_db_ingest.py`, `db.py` |
| #7 | Router receives memory_entities; follow-up detection added | `router.py`, `qa_chain.py` |
| #8 | HallucinationGuard validates every LLM answer | `hallucination_guard.py` |
| #24 | Strategy lock prevents LLM ignoring BM25/vector context | `qa_chain.py` |
| #25 | Ingest count validation; --force re-ingest flag | `run_db_ingest.py` |
| #26 | 30s timeout guard on all retrieval; follow-up uses memory_only | `qa_chain.py` |
| #27 | Vector strategy subject to strategy lock; factual fallback | `qa_chain.py` |
| #28 | Garbage invoice_number validation in extractor and db.py | `llm_extractor.py`, `db.py` |

### Production Readiness Checklist

- [ ] All P0 bugs fixed and unit tests passing
- [ ] `hallucination_log.jsonl` rotating daily
- [ ] Confidence badge visible in Streamlit UI (green/yellow/red)
- [ ] Rate limiting active on `/ask` endpoint (10 req/min/IP)
- [ ] Session persistence using SQLite `rag_sessions` table
- [ ] Audit log table populated on every invoice insert
- [ ] Date normalisation migration run on existing data
- [ ] Vendor name `UPPER()` normalisation applied to existing rows
- [ ] BM25 index rebuilt after all fixes
- [ ] ChromaDB collection recreated with HNSW tuning
- [ ] p95 query latency < 5s verified under 100 concurrent test queries
- [ ] 83-case test suite (73 existing + 10 new regression) at 95%+ pass rate

### Non-Negotiable Production Parameters

```python
LLM_TEMPERATURE          = 0      # Never increase for QA calls
RETRIEVAL_TIMEOUT_SEC    = 30     # Hard ceiling on all retrieval
OLLAMA_CALL_TIMEOUT_SEC  = 60     # Hard ceiling on LLM generation
MAX_INVOICE_CHARS        = 30000  # Multi-page extraction limit
BM25_EXACT_MATCH_SCORE   = 999    # For GSTIN/invoice number direct hits
RATE_LIMIT_PER_MIN       = 10     # Per IP on /ask endpoint
RAG_TOP_K                = 10     # Default retrieval limit
RAG_TOP_K_LIST           = 20     # For "list all" / "show all" queries
```
```

---

## 9. Testing Protocol & Acceptance Criteria

### Week 1 — P0 Test Gates

All gates must pass before Week 2 work begins.

| Test ID | Description | Owner |
|---------|-------------|-------|
| T-01 | Address extraction: 95%+ of 100 invoices have non-null `vendor_address` | LEAD A |
| T-02 | Invoice exact match: "Show me invoice GST001" returns `GST001.pdf` as rank 1 | LEAD B |
| T-03 | GSTIN exact match: query by GSTIN returns correct vendor in < 5s | LEAD B |
| T-04 | SQL GROUP BY: NIREL DIGITALS count equals actual JSON file count | LEAD C |
| T-05 | Strategy lock: LLM answer contains vendor name when BM25 sources present | LEAD D |
| T-06 | False negative detection: guard catches "not found" when sources exist | LEAD E |
| T-07 | Timeout: no query exceeds 35s (previous worst: 1,094s) | LEAD D |
| T-08 | Garbage invoice number: "e-Way" never stored in `invoice_number` column | LEAD C |

### Week 2 — Quality Test Gates

| Test ID | Description | Owner |
|---------|-------------|-------|
| T-09 | Date query: "invoices from September 2023" returns correct month | LEAD C |
| T-10 | Line item search: "search for Sticker" finds invoices with sticker line items | LEAD B |
| T-11 | Follow-up: "what is the total?" after showing an invoice uses memory | LEAD D |
| T-12 | Multi-result: SQL returning 5 rows produces a markdown table | LEAD D |
| T-13 | Confidence: all `/ask` responses include a `confidence` float | LEAD E |
| T-14 | City search: "vendors in Bangalore" returns Bangalore vendors rank 1 | LEAD B |

### Acceptance Criteria for Production Deployment

- [ ] Extract 95%+ of all address fields (currently ~0%)
- [ ] Return correct SQL aggregations (currently failing for NIREL vendor counts)
- [ ] Zero false negatives on factual queries when retrieved sources exist
- [ ] Follow-up questions answered in < 5s using `memory_only` path
- [ ] Process 10+ page invoices without any truncation of line items
- [ ] Response time p95 < 5 seconds for all strategies (current average: 68s)
- [ ] Full 83-case test suite at 95%+ pass rate
- [ ] Confidence score present in every `/ask` response
- [ ] Hallucination monitoring live, showing < 5% override rate in production

---

> **Reminder to all Leads:** Research best-in-class solutions before implementing.
> Reference ChromaDB 1.0.0+ docs for HNSW tuning, rank_bm25 docs for exact-match
> bypass patterns, and the Ollama API docs for timeout parameters. All code must be
> tested against the actual SQLite database with the real 65-invoice dataset before
> marking any bug as resolved.