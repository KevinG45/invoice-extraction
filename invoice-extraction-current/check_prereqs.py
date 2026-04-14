#!/usr/bin/env python3
"""
Check prerequisites for RAG evaluation.
"""
import sys
import time
from pathlib import Path

print("=" * 70)
print("CHECKING RAG EVALUATION PREREQUISITES")
print("=" * 70)

# Check 1: Ollama connectivity
print("\n1. Checking Ollama connectivity at http://localhost:11434...")
try:
    import requests
    response = requests.get("http://localhost:11434/api/tags", timeout=5)
    if response.status_code == 200:
        data = response.json()
        print("   ✓ Ollama is running")
        print(f"   Available models: {[m['name'] for m in data.get('models', [])]}")
        
        # Check for qwen2.5:3b
        models = [m['name'] for m in data.get('models', [])]
        if 'qwen2.5:3b' in models or any('qwen' in m for m in models):
            print("   ✓ qwen2.5:3b model found")
        else:
            print("   ⚠ WARNING: qwen2.5:3b model not found")
            print(f"     Available models: {models}")
    else:
        print(f"   ✗ Ollama returned status {response.status_code}")
except Exception as e:
    print(f"   ✗ FAILED: {e}")
    print("   Make sure Ollama is running: ollama serve")
    sys.exit(1)

# Check 2: Required directories
print("\n2. Checking required directories...")
required_dirs = [
    "rag",
    "data",
    "test_results",
    "chroma_db",
]
for dir_name in required_dirs:
    dir_path = Path(dir_name)
    if dir_path.exists():
        print(f"   ✓ {dir_name}/ exists")
    else:
        print(f"   ⚠ {dir_name}/ will be created")

# Check 3: Required modules
print("\n3. Checking Python modules...")
required_modules = [
    "ollama",
    "chromadb",
    "sentence_transformers",
    "rank_bm25",
]
missing = []
for mod in required_modules:
    try:
        __import__(mod)
        print(f"   ✓ {mod}")
    except ImportError:
        print(f"   ✗ {mod} (missing)")
        missing.append(mod)

if missing:
    print(f"\n   Missing modules: {', '.join(missing)}")
    print("   Run: pip install -r requirements.txt")
    sys.exit(1)

# Check 4: Database
print("\n4. Checking database...")
db_path = Path("data/invoices.db")
if db_path.exists():
    print(f"   ✓ Database exists at {db_path}")
else:
    print(f"   ⚠ Database not found at {db_path}")

print("\n" + "=" * 70)
print("PREREQUISITES CHECK COMPLETE")
print("=" * 70)
print("\nReady to run: python -m rag.test_suite_extended --verbose")
print("Estimated duration: ~97 minutes for 65 test cases")
print()
