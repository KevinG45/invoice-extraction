"""
Run RAG Evaluation with Production-Ready Test Cases
Execute this script from the invoice-extraction-current directory:
    python run_production_eval.py
"""
import subprocess
import sys
import os

# Set working directory
os.chdir(r"c:\Users\kmgs4\Documents\Christ Uni\invoice-extraction\invoice-extraction-current")
sys.path.insert(0, os.getcwd())

print("=" * 70)
print("RAG Production-Ready Evaluation (75 test cases)")
print("=" * 70)
print()

# Run the evaluation
print("Starting evaluation with verbose output...")
print("This will take approximately 20-25 minutes (~20 seconds per query)")
print()

try:
    # Import and run directly
    from rag import test_suite_extended
    test_suite_extended.main()
except KeyboardInterrupt:
    print("\n\nEvaluation interrupted by user")
except Exception as e:
    print(f"\nError running evaluation: {e}")
    print("\nTry running directly with:")
    print("  python -m rag.test_suite_extended --verbose")
