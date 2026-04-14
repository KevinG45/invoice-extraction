"""
Quick RAG Evaluation Runner
Checks prerequisites and starts the evaluation
"""
import subprocess
import sys
import os
from pathlib import Path

# Set working directory
os.chdir(r"c:\Users\kmgs4\Documents\Christ Uni\invoice-extraction\invoice-extraction-current")

print("=" * 60)
print("RAG Evaluation Suite Runner")
print("=" * 60)
print()

# Check prerequisites
print("Checking prerequisites...")
print()

# Check Ollama
print("1. Checking Ollama service...")
try:
    import requests
    response = requests.get("http://localhost:11434/api/tags", timeout=5)
    if response.status_code == 200:
        print("   ✓ Ollama is running")
    else:
        print(f"   ✗ Ollama returned status {response.status_code}")
        print("   Please start Ollama: 'ollama serve'")
        sys.exit(1)
except Exception as e:
    print(f"   ✗ Ollama not accessible: {e}")
    print("   Please start Ollama: 'ollama serve'")
    sys.exit(1)

print()

# Check if qwen2.5:3b model exists
print("2. Checking qwen2.5:3b model...")
try:
    models = response.json().get('models', [])
    model_names = [m.get('name', '') for m in models]
    if any('qwen2.5:3b' in name for name in model_names):
        print("   ✓ qwen2.5:3b model found")
    else:
        print("   ✗ qwen2.5:3b model not found")
        print("   Please pull model: 'ollama pull qwen2.5:3b'")
        sys.exit(1)
except Exception as e:
    print(f"   ⚠ Could not verify model: {e}")
    print("   Continuing anyway...")

print()
print("=" * 60)
print("Starting RAG Evaluation")
print("Estimated time: ~97 minutes (1 hour 37 minutes)")
print("=" * 60)
print()

# Run the evaluation
try:
    result = subprocess.run(
        [sys.executable, "-m", "rag.test_suite_extended", "--verbose"],
        check=True
    )
    
    print()
    print("=" * 60)
    print("✓ RAG Evaluation Complete!")
    print("=" * 60)
    print()
    print("Results saved to:")
    print("  - test_results/rag_summary.json")
    print("  - test_results/rag_per_query.csv")
    print()
    
except subprocess.CalledProcessError as e:
    print()
    print("=" * 60)
    print(f"✗ Evaluation failed with exit code {e.returncode}")
    print("=" * 60)
    sys.exit(e.returncode)
except KeyboardInterrupt:
    print()
    print("=" * 60)
    print("⚠ Evaluation cancelled by user")
    print("=" * 60)
    sys.exit(130)
