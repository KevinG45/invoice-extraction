# Bug Fix Checklist - Invoice Extraction System

Quick reference for developers fixing the identified issues.

---

## 🔴 P0 - BLOCKING (Must Fix First)

### [ ] 1. Fix Undefined Limiter Variable
**File:** `api/main.py`  
**Line:** 128  
**Fix:**
```python
# Add after line 29 (after imports):
limiter = Limiter(key_func=get_remote_address)
```
**Test:** `python run_api.py` should start without NameError

---

### [ ] 2. Remove ALL Emojis from UI
**Files:** `frontend/app.py`, `frontend/ui_helpers.py`  
**Count:** 50+ instances to fix

**Search & Replace:**
```python
# Find all: 📄 🚀 💬 📊 ✅ ❌ 📤 📋 💰 📥 🔍 💾 🗑️ 📚 🎯 🧠 🔀 🗄️ 🔑 🏢 👤
# Replace with: clean text alternatives
```

**Examples:**
- `"📄 Invoice Extractor"` → `"Invoice Extraction System"`
- `"🚀 Extract"` → `"Extract Invoice"`
- `"✅ Online"` → `"Online"` (use st.success for color)
- `"❌ Offline"` → `"Offline"` (use st.error for color)

**Locations:**
```bash
# frontend/app.py
Line 37: page_icon="📄"              → page_icon="📋"  # or remove
Line 57: st.title("📄 Invoice...")   → st.title("Invoice Extraction System")
Line 93: tab names                    → Remove emojis from all tab names
Line 110: st.button("🚀 Extract")    → st.button("Extract Invoice")
Line 252: st.button("🗑️ Clear Chat") → st.button("Clear Chat")
Line 262: st.button("💾 Save")       → st.button("Save Conversation")
Line 273: st.button("🔍 Ask")        → st.button("Ask Question")

# frontend/ui_helpers.py  
Line 41: "🔍 Zoom"                   → "Zoom"
Line 73: icon = "✅" / "❌"           → Use st.success/st.error instead
Line 121: "🏢 Vendor Information"    → "Vendor Information"
Line 137: "👤 Customer Information"  → "Customer Information"
Line 153: "📄 Invoice Details"       → "Invoice Details"
Line 403-434: All "📥 Download" btns  → "Download JSON/Excel/CSV"
Line 449: "💡 Example Questions"     → "Example Questions"
Line 516: "📚 Sources"               → "Sources"
```

**Test:** Visual inspection - UI should look clean and professional

---

### [ ] 3. Add Prerequisites Validation
**File:** Create new `utils/prereq_validator.py`

```python
"""Prerequisite validation for invoice extraction system."""
import subprocess
import sys
import requests
from typing import List, Tuple

def check_tesseract() -> Tuple[bool, str]:
    """Check if Tesseract is installed and accessible."""
    try:
        result = subprocess.run(
            ["tesseract", "--version"], 
            capture_output=True, 
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.split('\n')[0]
            return True, f"Tesseract found: {version}"
        return False, "Tesseract not responding correctly"
    except FileNotFoundError:
        return False, "Tesseract not found in PATH"
    except Exception as e:
        return False, f"Tesseract check failed: {e}"

def check_ollama() -> Tuple[bool, str]:
    """Check if Ollama is running and accessible."""
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=5)
        if resp.status_code == 200:
            models = resp.json().get('models', [])
            return True, f"Ollama running with {len(models)} models"
        return False, f"Ollama returned status {resp.status_code}"
    except requests.ConnectionError:
        return False, "Ollama not running on localhost:11434"
    except Exception as e:
        return False, f"Ollama check failed: {e}"

def check_ollama_model(model_name: str = "qwen2.5:3b") -> Tuple[bool, str]:
    """Check if required Ollama model is available."""
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=5)
        if resp.status_code == 200:
            models = resp.json().get('models', [])
            model_names = [m['name'] for m in models]
            if model_name in model_names:
                return True, f"Model {model_name} is available"
            return False, f"Model {model_name} not found. Available: {model_names}"
        return False, "Cannot check models"
    except Exception as e:
        return False, f"Model check failed: {e}"

def validate_all_prerequisites() -> bool:
    """Run all prerequisite checks and display results."""
    print("\n=== Checking Prerequisites ===\n")
    
    all_ok = True
    checks = [
        ("Tesseract OCR", check_tesseract()),
        ("Ollama Service", check_ollama()),
        ("Ollama Model", check_ollama_model()),
    ]
    
    for name, (ok, msg) in checks:
        status = "✓" if ok else "✗"
        print(f"{status} {name}: {msg}")
        if not ok:
            all_ok = False
    
    print("\n" + "="*40 + "\n")
    
    if not all_ok:
        print("❌ Prerequisites check FAILED\n")
        print("Fix the issues above before running the application.\n")
        print("Installation guides:")
        print("  - Tesseract: https://github.com/tesseract-ocr/tesseract")
        print("  - Ollama: https://ollama.com")
        print("  - Model: ollama pull qwen2.5:3b\n")
        return False
    
    print("✓ All prerequisites OK\n")
    return True

if __name__ == "__main__":
    sys.exit(0 if validate_all_prerequisites() else 1)
```

**Update:** `run_frontend.py` line 15:
```python
if __name__ == "__main__":
    # Add prerequisite check
    from utils.prereq_validator import validate_all_prerequisites
    if not validate_all_prerequisites():
        sys.exit(1)
    
    # Existing code...
```

**Test:** Run with Ollama stopped - should show clear error message

---

### [ ] 4. Fix SQL Injection Risk
**File:** `rag/sql_retriever.py`  
**Add validation before line 200 (execution):**

```python
def _validate_sql_query(sql: str) -> Tuple[bool, str]:
    """Validate generated SQL query for safety.
    
    Returns:
        (is_valid, error_message)
    """
    sql_upper = sql.upper().strip()
    
    # Check for dangerous operations
    dangerous_keywords = [
        'DROP', 'DELETE', 'INSERT', 'UPDATE', 'ALTER', 
        'CREATE', 'TRUNCATE', 'REPLACE', 'GRANT', 'REVOKE'
    ]
    for keyword in dangerous_keywords:
        if keyword in sql_upper:
            return False, f"Dangerous SQL keyword: {keyword}"
    
    # Must start with SELECT
    if not sql_upper.startswith('SELECT'):
        return False, "Query must be a SELECT statement"
    
    # Check for multiple statements (semicolon)
    if sql.count(';') > 1:
        return False, "Multiple SQL statements not allowed"
    
    # Check for common injection patterns
    injection_patterns = [
        '--',           # SQL comment
        '/*',           # Multi-line comment
        'EXEC',         # Execute
        'xp_',          # Extended procedures
        'sp_',          # System procedures
    ]
    for pattern in injection_patterns:
        if pattern in sql_upper:
            return False, f"Potential SQL injection pattern: {pattern}"
    
    return True, ""

# In sql_retrieve() function, before line 200:
def sql_retrieve(question: str, top_k: int = 20) -> list[dict]:
    """..."""
    # ... existing code ...
    
    # BEFORE executing:
    is_valid, error = _validate_sql_query(sql_query)
    if not is_valid:
        logger.error(f"SQL validation failed: {error}. Query: {sql_query}")
        raise ValueError(f"Generated SQL query failed validation: {error}")
    
    # ... rest of execution code ...
```

**Test:** Try malicious queries and verify they're blocked

---

### [ ] 5. Fix Session Save Error Handling
**File:** `rag/qa_chain.py`  
**Lines:** 237-253

**Change from:**
```python
except Exception as e:
    logger.warning("Could not save session %s: %s", memory.session_id, e)
```

**To:**
```python
except Exception as e:
    logger.error("Could not save session %s: %s", memory.session_id, e)
    # Re-raise to surface to API layer
    raise RuntimeError(f"Session save failed: {e}") from e
```

**In API (`api/main.py`), catch and handle:**
```python
# In /ask endpoint, after qa_chain.answer():
try:
    save_memory(session_id)
except RuntimeError as e:
    logger.error(f"Session save failed: {e}")
    # Add warning to response
    result["warning"] = "Your conversation may not be saved"
```

**Test:** Simulate DB failure, verify user sees warning

---

## ⚠️ P1 - HIGH PRIORITY

### [ ] 6. Remove Fake Validation Metrics
**File:** `frontend/ui_helpers.py`  
**Lines:** 97-99

**Delete:**
```python
format_checks = 2  # GSTIN format, date format
st.metric("Format Checks", f"{format_checks}/2",
         help="GSTIN format, date formats")
```

**Test:** Validation badge should show only real metrics

---

### [ ] 7. Add Error Boundaries
**File:** `frontend/app.py`

**Wrap each tab in try-except:**
```python
with tab1:
    try:
        # Existing tab1 code
    except Exception as e:
        st.error("An error occurred in the extraction interface.")
        st.exception(e)  # Only in debug mode
        logger.exception("Tab1 error")

# Repeat for tab2, tab3
```

---

### [ ] 8. Fix Memory Leak - Session Cleanup
**File:** `rag/qa_chain.py`

**Add cleanup function after line 313:**
```python
def cleanup_old_sessions(max_age_hours: int = 24) -> None:
    """Remove sessions older than max_age_hours."""
    cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
    to_remove = []
    
    for session_id, memory in _sessions.items():
        # Check last update time
        if hasattr(memory, 'updated_at'):
            if memory.updated_at < cutoff:
                to_remove.append(session_id)
    
    for session_id in to_remove:
        del _sessions[session_id]
        logger.info(f"Cleaned up old session: {session_id}")
    
    logger.info(f"Session cleanup: removed {len(to_remove)}, kept {len(_sessions)}")

# Call periodically (e.g., in API startup or background task)
```

---

### [ ] 9. Implement Missing Playbook Features

#### 9a. Add Line Item Currency Column
**File:** `core/db.py`

**Add to LineItem model (around line 160):**
```python
class LineItem(Base):
    # ... existing columns ...
    currency = Column(String)  # NEW: Add this
```

**Migration SQL:**
```sql
ALTER TABLE line_items ADD COLUMN currency TEXT;
UPDATE line_items SET currency = (
    SELECT currency FROM invoices WHERE invoices.id = line_items.invoice_id
);
```

**Update insert logic to propagate currency.**

---

#### 9b. Add Duplicate Detection
**File:** `core/db.py`

**Add index (in models section):**
```python
Index("ix_invoice_dedup", 
      Invoice.invoice_number, 
      Invoice.vendor_name, 
      Invoice.total_amount)
```

**In insert_extraction() function, before insert:**
```python
# Check for duplicate
existing = session.query(Invoice).filter_by(
    invoice_number=data.get("invoice_number"),
    vendor_name=vendor.get("name"),
    total_amount=data.get("total_amount")
).first()

if existing:
    logger.warning(
        f"Duplicate invoice detected: {data.get('invoice_number')} "
        f"from {vendor.get('name')}. Skipping insert."
    )
    return existing.source_file  # Return existing file instead of inserting
```

---

#### 9c. Add Audit Log
**File:** `core/db.py`

**Add model:**
```python
class AuditLog(Base):
    __tablename__ = "audit_log"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    table_name = Column(String, nullable=False)
    record_id = Column(Integer)
    action = Column(String, nullable=False)  # INSERT, UPDATE, DELETE
    user_id = Column(String, default="system")
    timestamp = Column(DateTime, default=datetime.utcnow)
    old_value = Column(Text)  # JSON
    new_value = Column(Text)  # JSON
```

**After each insert:**
```python
audit = AuditLog(
    table_name="invoices",
    record_id=invoice_obj.id,
    action="INSERT",
    new_value=json.dumps({
        "invoice_number": invoice_obj.invoice_number,
        "vendor": invoice_obj.vendor_name,
        "total": invoice_obj.total_amount
    })
)
session.add(audit)
```

---

#### 9d. Add OCR Quality Flagging
**File:** `core/ocr_engine.py`

**Add to OCR result:**
```python
def extract_text(image) -> dict:
    # ... existing code ...
    
    # Calculate confidence
    mean_confidence = calculate_mean_confidence(ocr_result)
    
    quality = "high"
    if mean_confidence < 0.50:
        quality = "low"
        logger.warning(f"Low OCR quality: {mean_confidence:.2f}")
    if mean_confidence < 0.30:
        quality = "very_low"
        logger.error(f"Very low OCR quality: {mean_confidence:.2f}")
    
    return {
        "text": extracted_text,
        "confidence": mean_confidence,
        "ocr_quality": quality  # NEW
    }
```

**Surface in API response and show warning in UI.**

---

## 📱 UI Improvements

### [ ] 10. Improve Visual Hierarchy
**File:** `frontend/app.py`

Add custom CSS:
```python
st.markdown("""
<style>
    /* Primary actions */
    .stButton > button[kind="primary"] {
        font-size: 1.1rem;
        font-weight: 600;
    }
    
    /* Card style for sections */
    .card {
        background: #f9fafb;
        padding: 1.5rem;
        border-radius: 0.5rem;
        border-left: 4px solid #3b82f6;
        margin: 1rem 0;
    }
    
    /* Status indicators */
    .status-online { color: #059669; font-weight: 600; }
    .status-offline { color: #dc2626; font-weight: 600; }
</style>
""", unsafe_allow_html=True)
```

---

### [ ] 11. Better Error Messages
**File:** `frontend/app.py`

Replace technical errors with user-friendly messages:
```python
ERROR_MESSAGES = {
    404: "Document not found. Please try uploading again.",
    500: "Processing failed. Our team has been notified.",
    "ConnectionError": "Service temporarily unavailable. Please try again in a moment.",
}

def get_user_friendly_error(error):
    """Convert technical error to user-friendly message."""
    for key, msg in ERROR_MESSAGES.items():
        if str(key) in str(error) or key in type(error).__name__:
            return msg
    return "An unexpected error occurred. Please contact support."
```

---

### [ ] 12. Add Empty States
**File:** `frontend/app.py`

```python
if not result:
    st.info("""
    ### Welcome to Invoice Extraction System
    
    Upload an invoice to get started:
    - Supported formats: PDF, PNG, JPG, TIFF
    - Maximum file size: 50MB
    - Processing time: 30-60 seconds
    
    Example questions you can ask:
    - "Show me invoice GST001"
    - "What is the total of all invoices?"
    - "List invoices from last month"
    """)
```

---

## 🔧 Code Quality

### [ ] 13. Add Type Hints
Pick 5 most-used functions and add type hints:

```python
# Before
def render_document_viewer(file_bytes, filename, file_type):

# After  
def render_document_viewer(
    file_bytes: bytes,
    filename: str,
    file_type: str
) -> None:
```

---

### [ ] 14. Extract Magic Numbers
**File:** `frontend/ui_helpers.py`

```python
# Add at top of file:
ZOOM_MIN = 50
ZOOM_MAX = 200
ZOOM_DEFAULT = 100

# Use in code:
zoom = st.slider("Zoom", ZOOM_MIN, ZOOM_MAX, ZOOM_DEFAULT)
```

---

## ✅ Testing Checklist

### Manual Tests:
- [ ] API starts without errors
- [ ] Frontend loads without emojis
- [ ] Upload invoice successfully
- [ ] Ask question, get answer
- [ ] Check session persists
- [ ] Verify no SQL injection
- [ ] Test with Ollama stopped (should show clear error)
- [ ] Test with Tesseract not installed (should show clear error)

### Automated Tests (Nice to Have):
- [ ] Unit tests for validation functions
- [ ] Integration test for end-to-end extraction
- [ ] Performance test for query response time

---

## 📝 Sign-off

- [ ] All P0 bugs fixed
- [ ] UI emojis removed
- [ ] Prerequisites validated
- [ ] Security issues addressed
- [ ] Code reviewed by peer
- [ ] Tested locally
- [ ] Ready for deployment

---

**Estimated Time:**
- P0 fixes: 4-6 hours
- P1 fixes: 8-12 hours  
- UI improvements: 6-8 hours
- Testing: 4-6 hours

**Total: 2-3 days**
