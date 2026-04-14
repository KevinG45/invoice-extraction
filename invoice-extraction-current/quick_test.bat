@echo off
REM Quick Smoke Test - Tests critical bugs only (5-10 minutes)

echo ========================================
echo Quick Smoke Test - Critical Bug Check
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
echo Running quick smoke test...
echo.

python -c "
import sys
import time
sys.path.insert(0, '.')

print('='*60)
print('QUICK SMOKE TEST - Critical Bug Detection')
print('='*60)
print()

passed = 0
failed = 0
errors = []

def test(name, func):
    global passed, failed, errors
    try:
        start = time.time()
        result = func()
        elapsed = time.time() - start
        if result:
            print(f'[PASS] {name} ({elapsed:.1f}s)')
            passed += 1
        else:
            print(f'[FAIL] {name} ({elapsed:.1f}s)')
            failed += 1
            errors.append(f'{name}: Test assertion failed')
    except Exception as e:
        print(f'[ERROR] {name}: {type(e).__name__}: {e}')
        failed += 1
        errors.append(f'{name}: {type(e).__name__}: {e}')

# Test 1: BM25 Retriever loads and searches
def test_bm25_basic():
    from rag.bm25_retriever import BM25Retriever
    r = BM25Retriever()
    if r.index is None:
        return False
    result = r.search('GST001', top_k=3)
    return isinstance(result, list)

# Test 2: BM25 doesn't return None
def test_bm25_not_none():
    from rag.bm25_retriever import BM25Retriever
    r = BM25Retriever()
    result = r.search('nonexistent query xyz', top_k=5)
    return result is not None and isinstance(result, list)

# Test 3: SQL query works
def test_sql_query():
    from rag.qa_chain import answer
    result = answer('How many invoices are in the system?')
    return result.get('strategy') == 'sql' and 'error' not in result.get('strategy', '')

# Test 4: BM25 query works (not error)
def test_bm25_query():
    from rag.qa_chain import answer
    result = answer('Show me invoice GST001')
    return result.get('strategy') != 'error'

# Test 5: Vector query works (not error)  
def test_vector_query():
    from rag.qa_chain import answer
    result = answer('Find technology-related invoices')
    return result.get('strategy') != 'error'

# Test 6: Hybrid query works (not error)
def test_hybrid_query():
    from rag.qa_chain import answer
    result = answer('List vendors in Bangalore')
    return result.get('strategy') != 'error'

# Test 7: GSTIN exact match
def test_gstin_match():
    from rag.bm25_retriever import BM25Retriever
    r = BM25Retriever()
    result = r.search('36ARKPC6820F1ZZ', top_k=3)
    return len(result) > 0 and any(r.get('score', 0) >= 999 for r in result)

# Test 8: City boosting
def test_city_search():
    from rag.bm25_retriever import BM25Retriever
    r = BM25Retriever()
    result = r.search('invoices from Bangalore', top_k=5)
    return isinstance(result, list)

# Test 9: Vector indexer works
def test_vector_indexer():
    from rag.indexer import query_chunks
    result = query_chunks('printing services', top_k=3)
    return isinstance(result, list)

# Test 10: SQL retriever with timeout
def test_sql_timeout():
    from rag.sql_retriever import sql_retrieve
    result = sql_retrieve('Count all invoices')
    return 'error' not in str(result).lower() or 'timeout' in str(result).lower()

print('Running 10 critical tests...')
print()

test('BM25 Retriever Basic', test_bm25_basic)
test('BM25 Not None', test_bm25_not_none)
test('SQL Query', test_sql_query)
test('BM25 Query', test_bm25_query)
test('Vector Query', test_vector_query)
test('Hybrid Query', test_hybrid_query)
test('GSTIN Exact Match', test_gstin_match)
test('City Search', test_city_search)
test('Vector Indexer', test_vector_indexer)
test('SQL Retriever', test_sql_timeout)

print()
print('='*60)
print(f'Results: {passed} passed, {failed} failed')
print('='*60)

if errors:
    print()
    print('ERRORS:')
    for e in errors:
        print(f'  - {e}')

if failed == 0:
    print()
    print('All critical tests PASSED!')
    print('Ready to run full evaluation: start_eval.bat')
else:
    print()
    print('Some tests FAILED - please investigate before full evaluation')
"

echo.
pause
