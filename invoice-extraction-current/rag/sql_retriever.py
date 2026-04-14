"""
SQL retrieval layer for the invoice RAG system.

Converts natural-language questions into SQL via a local Ollama LLM,
then executes the query against the SQLite database.
"""

import re
import sqlite3

import ollama

from core.config import DATABASE_PATH, LLM_BASE_URL, LLM_MODEL, LLM_TEMPERATURE

# ── Schema description fed to the LLM ──────────────────────────────────────

_SCHEMA = """\
The database is SQLite with these tables:

TABLE invoices (
  id              INTEGER PRIMARY KEY,
  source_file     TEXT UNIQUE NOT NULL,
  source_path     TEXT,
  processed_at    DATETIME,
  overall_confidence REAL,
  validated       BOOLEAN,
  invoice_number  TEXT,
  invoice_date    TEXT,
  due_date        TEXT,
  purchase_order_number TEXT,
  vendor_name     TEXT,
  vendor_address  TEXT,
  vendor_email    TEXT,
  vendor_phone    TEXT,
  vendor_tax_id   TEXT,
  vendor_website  TEXT,
  bill_to_name    TEXT,
  bill_to_address TEXT,
  bill_to_email   TEXT,
  ship_to_name    TEXT,
  ship_to_address TEXT,
  subtotal        REAL,
  discount        REAL,
  tax_rate        REAL,
  tax_amount      REAL,
  shipping        REAL,
  total_amount    REAL,
  amount_paid     REAL,
  amount_due      REAL,
  currency        TEXT,
  payment_terms   TEXT,
  payment_method  TEXT,
  bank_details    TEXT,
  notes           TEXT,
  pdf_type        TEXT,
  page_count      INTEGER,
  ocr_engine      TEXT,
  tables_found    INTEGER,
  text_length     INTEGER,
  processing_seconds REAL
);

TABLE line_items (
  id          INTEGER PRIMARY KEY,
  invoice_id  INTEGER NOT NULL REFERENCES invoices(id),
  description TEXT,
  hsn_sac     TEXT,
  quantity    REAL,
  unit_price  REAL,
  discount    REAL,
  tax_rate    REAL,
  tax_amount  REAL,
  total       REAL
);

TABLE validation_reports (
  id          INTEGER PRIMARY KEY,
  invoice_id  INTEGER NOT NULL REFERENCES invoices(id),
  passed      BOOLEAN,
  score       REAL,
  issues      TEXT     -- JSON string
);
"""

_SYSTEM_PROMPT = f"""\
You are a SQL expert. Convert user questions about invoices into SQL SELECT queries.

{_SCHEMA}

═══════════════════════════════════════════════════════════════════════════════
MANDATORY PROCEDURE FOR GENERATING SQL
═══════════════════════════════════════════════════════════════════════════════

STEP 1: READ THE QUESTION CAREFULLY
        Identify what data is being requested:
        - Counting? → Use COUNT(*)
        - Summing totals? → Use SUM(total_amount)
        - Listing items? → Use SELECT with appropriate columns
        - Grouping? → Use GROUP BY
        - Sorting? → Use ORDER BY

STEP 2: IDENTIFY THE CORRECT TABLE
        - Invoice-level data (vendor, dates, totals) → invoices table
        - Line item details (product descriptions, quantities) → line_items table
        - Validation status → validation_reports table

STEP 3: CHECK FOR COMMON PATTERNS

        Pattern: "List vendors sorted by total"
        SQL: SELECT vendor_name, SUM(total_amount) as total_value FROM invoices GROUP BY vendor_name ORDER BY total_value DESC

        Pattern: "Count invoices by month"
        SQL: SELECT strftime('%Y-%m', invoice_date) as month, COUNT(*) as invoice_count FROM invoices GROUP BY month ORDER BY month

        Pattern: "Find vendor with highest total"
        SQL: SELECT vendor_name, SUM(total_amount) as total FROM invoices GROUP BY vendor_name ORDER BY total DESC LIMIT 1

        Pattern: "How many invoices above X amount"
        SQL: SELECT COUNT(*) as count FROM invoices WHERE total_amount > X

        Pattern: "Total tax collected"
        SQL: SELECT SUM(tax_amount) as total_tax FROM invoices

STEP 4: GENERATE THE SQL
        - Use ONLY SELECT statements
        - Always alias aggregation columns (COUNT(*) as count, SUM(total_amount) as total)
        - For grouping queries, always use GROUP BY and ORDER BY
        - For date queries, use strftime('%Y-%m', invoice_date) since dates are TEXT

═══════════════════════════════════════════════════════════════════════════════
CRITICAL COLUMN NAMES (MUST USE EXACT NAMES)
═══════════════════════════════════════════════════════════════════════════════

CORRECT column names:
✓ vendor_tax_id (for GSTIN, NOT vendor_gstin)
✓ total_amount (for invoice total, NOT total or amount)
✓ tax_amount (for tax, NOT tax)
✓ vendor_name (for vendor name, NOT vendor)
✓ invoice_date (for date, NOT date)
✓ invoice_number (for invoice number, NOT invoice_num or number)

WRONG column names (DO NOT USE):
✗ vendor_gstin (doesn't exist, use vendor_tax_id)
✗ total (ambiguous, use total_amount)
✗ amount (ambiguous, use total_amount or tax_amount)
✗ invoice_id (for invoices table use 'id', only line_items/validation_reports use 'invoice_id')
✗ selling_charges (use 'shipping')
✗ total_subtotal (use 'subtotal')

═══════════════════════════════════════════════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════════════════════════════════════════════

Return ONLY the SQL query. No explanation. No markdown. No code blocks.

Example user question: "List vendors sorted by total invoice value"
Your output: SELECT vendor_name, SUM(total_amount) as total_value FROM invoices GROUP BY vendor_name ORDER BY total_value DESC

Example user question: "Count invoices by month"
Your output: SELECT strftime('%Y-%m', invoice_date) as month, COUNT(*) as invoice_count FROM invoices GROUP BY month ORDER BY month

═══════════════════════════════════════════════════════════════════════════════
ABSOLUTE RULES (NEVER BREAK)
═══════════════════════════════════════════════════════════════════════════════

1. NEVER use INSERT, UPDATE, DELETE, DROP, ALTER, CREATE
2. ALWAYS start with SELECT
3. ALWAYS use exact column names from schema above
4. ALWAYS alias aggregation results (COUNT(*) as count, SUM(x) as total)
5. ALWAYS use GROUP BY when using SUM, COUNT, AVG, etc. on grouped data
6. ALWAYS use ORDER BY for "sorted" or "highest" or "lowest" questions
7. ALWAYS use strftime for date operations since invoice_date is TEXT
8. NEVER invent column names not in the schema

Additional important notes:
- vendor_tax_id contains the vendor's GSTIN (GST Identification Number)
- For currency-specific queries (rupees, INR, ₹), add: AND currency = 'INR'
- For line item searches, join line_items table: FROM invoices i JOIN line_items l ON l.invoice_id = i.id
- For validation queries, join validation_reports: FROM invoices i JOIN validation_reports v ON v.invoice_id = i.id
- "customer" means the party billed to us → use bill_to_name column
- "highest paying customer" → SELECT bill_to_name, SUM(total_amount) as total_paid FROM invoices WHERE bill_to_name IS NOT NULL GROUP BY bill_to_name ORDER BY total_paid DESC LIMIT 1
- "who do we sell to most" → SELECT bill_to_name, COUNT(*) as invoice_count FROM invoices WHERE bill_to_name IS NOT NULL GROUP BY bill_to_name ORDER BY invoice_count DESC LIMIT 1

"""

# ENHANCED: Valid column names for improved error messages
_VALID_COLUMNS = {
    'invoices': {
        'id', 'source_file', 'source_path', 'processed_at', 'overall_confidence',
        'validated', 'invoice_number', 'invoice_date', 'due_date', 'purchase_order_number',
        'vendor_name', 'vendor_address', 'vendor_email', 'vendor_phone', 'vendor_tax_id',
        'vendor_website', 'bill_to_name', 'bill_to_address', 'bill_to_email',
        'ship_to_name', 'ship_to_address', 'subtotal', 'discount', 'tax_rate',
        'tax_amount', 'shipping', 'total_amount', 'amount_paid', 'amount_due',
        'currency', 'payment_terms', 'payment_method', 'bank_details', 'notes',
        'pdf_type', 'page_count', 'ocr_engine', 'tables_found', 'text_length',
        'processing_seconds'
    },
    'line_items': {
        'id', 'invoice_id', 'description', 'hsn_sac', 'quantity', 'unit_price',
        'discount', 'tax_rate', 'tax_amount', 'total'
    },
    'validation_reports': {
        'id', 'invoice_id', 'passed', 'score', 'issues'
    }
}

# Common column name corrections
_COLUMN_CORRECTIONS = {
    'invoice_id': 'id',  # For invoices table 
    'vendor_gstin': 'vendor_tax_id',
    'total': 'total_amount',
    'amount': 'total_amount',
    'selling_charges': 'shipping',  # Common misunderstanding
    'total_subtotal': 'subtotal',   # LLM might combine these
}


def _check_column_names(sql: str) -> tuple[bool, str]:
    """
    Check if SQL uses valid column names and suggest corrections.
    Returns (is_valid, error_or_correction_message)
    """
    sql_upper = sql.upper()
    
    # Extract column references from SQL
    # This is a simple check - could be made more sophisticated
    for wrong_col, correct_col in _COLUMN_CORRECTIONS.items():
        if f'{wrong_col.upper()}' in sql_upper:
            return False, f"Column '{wrong_col}' doesn't exist. Did you mean '{correct_col}'?"
    
    # Check for common errors
    if 'INVOICE_ID' in sql_upper and 'FROM INVOICES' in sql_upper:
        return False, "For main invoices table, use 'id' not 'invoice_id'. Only line_items and validation_reports use 'invoice_id' as foreign key."
    
    return True, ""
# Statements that are never allowed
_FORBIDDEN_RE = re.compile(
    r"^\s*(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|ATTACH|DETACH|PRAGMA)",
    re.IGNORECASE,
)

# Additional dangerous patterns to block anywhere in query
_DANGEROUS_PATTERNS = [
    re.compile(r";\s*(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE)", re.IGNORECASE),  # Chained statements
    re.compile(r"--\s*[^\\n]*?(DROP|DELETE|INSERT)", re.IGNORECASE),  # Commands in comments
    re.compile(r"/\*.*?(DROP|DELETE|INSERT).*?\*/", re.IGNORECASE | re.DOTALL),  # Commands in block comments
    re.compile(r"\b(EXEC|EXECUTE|xp_|sp_)\b", re.IGNORECASE),  # Stored procedures
]

_MAX_ROWS = 50


def _validate_sql_safety(sql: str) -> tuple[bool, str]:
    """
    Validate that SQL is safe to execute and uses correct column names.
    ENHANCED: Added column name validation to prevent common errors.
    
    Returns:
        (is_safe, error_message)
    """
    # Check for forbidden statements at start
    if _FORBIDDEN_RE.match(sql):
        return False, "Rejected: Only SELECT queries are allowed"
    
    # Must start with SELECT
    if not sql.strip().upper().startswith("SELECT"):
        return False, "Rejected: Query must start with SELECT"
    
    # Check for dangerous patterns anywhere in query
    for pattern in _DANGEROUS_PATTERNS:
        if pattern.search(sql):
            return False, "Rejected: Query contains potentially dangerous SQL"
    
    # ENHANCED: Check column names
    is_valid, col_error = _check_column_names(sql)
    if not is_valid:
        return False, f"Column error: {col_error}"
    
    # Check for multiple statements (semicolon followed by more SQL)
    statements = [s.strip() for s in sql.split(';') if s.strip()]
    if len(statements) > 1:
        return False, "Rejected: Multiple SQL statements not allowed"
    
    # Limit query length to prevent abuse
    if len(sql) > 2000:
        return False, "Rejected: Query too long (max 2000 characters)"
    
    return True, ""


# ── Helpers ─────────────────────────────────────────────────────────────────

import concurrent.futures
import time

def _generate_sql(question: str, max_retries: int = 3) -> str:
    """Ask the LLM to convert a question into SQL with retry logic."""
    client = ollama.Client(host=LLM_BASE_URL)
    
    # FIXED: Bug SQL-3 — Validate query is not empty
    if not question or not question.strip():
        raise ValueError("Query cannot be empty")
    
    last_error = None
    for attempt in range(max_retries):
        try:
            # FIXED: Bug SQL-1 — Add timeout to prevent indefinite hangs
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    client.chat,
                    model=LLM_MODEL,
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": question},
                    ],
                    options={"temperature": LLM_TEMPERATURE},
                )
                response = future.result(timeout=60)  # 60 second timeout
            
            # FIXED: Bug SQL-2 — Safer response access
            raw = response.get("message", {}).get("content", "").strip()
            if not raw:
                raise ValueError("Empty response from LLM")

            # Strip markdown code fences if the LLM added them anyway
            raw = re.sub(r"^```(?:sql)?\s*", "", raw, flags=re.IGNORECASE)
            raw = re.sub(r"\s*```\s*$", "", raw)
            return raw.strip()
        except concurrent.futures.TimeoutError:
            last_error = TimeoutError("SQL generation timed out after 60 seconds")
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
    
    # FIXED: Bug SQL-2 — Handle case where last_error is None
    if last_error:
        raise last_error
    else:
        raise RuntimeError("Failed to generate SQL after all retries")


def _add_limit(sql: str) -> str:
    """Append a LIMIT clause if none is present."""
    if not re.search(r"\bLIMIT\b", sql, re.IGNORECASE):
        sql = sql.rstrip().rstrip(";")
        sql += f" LIMIT {_MAX_ROWS}"
    return sql


# ── Public API ──────────────────────────────────────────────────────────────

def sql_retrieve(query: str) -> dict:
    """Convert a natural-language query to SQL, execute it, return results.

    Returns
    -------
    dict with keys:
      - On success: results (list[dict]), sql (str), row_count (int)
      - On failure: error (str), sql (str)
    """
    # 1. Generate SQL from the question
    try:
        sql = _generate_sql(query)
    except Exception as e:
        return {"error": f"LLM call failed: {e}", "sql": ""}

    # 2. ENHANCED: Safety validation with column checking
    is_safe, error_msg = _validate_sql_safety(sql)
    if not is_safe:
        # Check if it's a correctable column error
        if "Column error:" in error_msg:
            # Try to auto-correct common column mistakes
            corrected_sql = sql
            for wrong_col, correct_col in _COLUMN_CORRECTIONS.items():
                corrected_sql = re.sub(
                    rf'\b{re.escape(wrong_col)}\b', 
                    correct_col, 
                    corrected_sql, 
                    flags=re.IGNORECASE
                )
            
            # Validate corrected SQL
            is_corrected, correction_error = _validate_sql_safety(corrected_sql)
            if is_corrected:
                sql = corrected_sql
                print(f"[SQL AUTO-CORRECT] Fixed column names in query")
            else:
                return {"error": error_msg, "sql": sql}
        else:
            return {"error": error_msg, "sql": sql}

    # 3. Enforce row limit
    sql = _add_limit(sql)

    # 4. Execute against SQLite
    try:
        conn = sqlite3.connect(str(DATABASE_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(sql)
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
    except Exception as e:
        return {"error": f"SQL execution error: {e}", "sql": sql}

    return {
        "results": rows,
        "sql": sql,
        "row_count": len(rows),
    }


# ── Self-test ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        "What is the total tax amount across all invoices?",
        "Which vendor has the highest total invoice value?",
        "How many invoices were validated successfully?",
    ]

    for i, q in enumerate(tests, 1):
        print(f"\n{'='*60}")
        print(f"TEST {i}: {q}")
        print("=" * 60)
        result = sql_retrieve(q)
        print(f"SQL: {result.get('sql', 'N/A')}")
        if "error" in result:
            print(f"ERROR: {result['error']}")
        else:
            print(f"Rows: {result['row_count']}")
            for row in result["results"][:5]:
                print(f"  {row}")
