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
You are a SQL expert. Given a user question about invoice data,
write a single SQL SELECT query that answers the question.

{_SCHEMA}

Important notes about the data:
- The invoices table holds invoice-level totals: subtotal, tax_amount,
  total_amount, discount, shipping, amount_paid, amount_due.
  For aggregate questions about totals, taxes, or amounts, query the
  invoices table unless the question is specifically about line items.
- The line_items table holds per-item detail rows.
- The validation_reports table tracks whether each invoice passed validation.

Rules:
- Return ONLY a valid SQL SELECT statement.
- No explanation. No markdown. No code blocks. Only SQL.
- Use only the tables and columns listed above.
- Always alias aggregation columns for readability.
- If the question is about validation, use the validation_reports table.
- NEVER use INSERT, UPDATE, DELETE, DROP, or ALTER.
"""

# Statements that are never allowed
_FORBIDDEN_RE = re.compile(
    r"^\s*(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|ATTACH|DETACH|PRAGMA)",
    re.IGNORECASE,
)

_MAX_ROWS = 50


# ── Helpers ─────────────────────────────────────────────────────────────────

def _generate_sql(question: str) -> str:
    """Ask the LLM to convert a question into SQL."""
    client = ollama.Client(host=LLM_BASE_URL)
    response = client.chat(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        options={"temperature": LLM_TEMPERATURE},
    )
    raw = response["message"]["content"].strip()

    # Strip markdown code fences if the LLM added them anyway
    raw = re.sub(r"^```(?:sql)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```\s*$", "", raw)
    return raw.strip()


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

    # 2. Safety check — reject non-SELECT statements
    if _FORBIDDEN_RE.match(sql):
        return {
            "error": "Rejected: only SELECT statements are allowed.",
            "sql": sql,
        }

    if not sql.strip().upper().startswith("SELECT"):
        return {
            "error": "Rejected: generated output is not a SELECT statement.",
            "sql": sql,
        }

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
