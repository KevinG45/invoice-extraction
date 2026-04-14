#!/usr/bin/env python3
"""
RAG Evaluation Manager - Run full evaluation suite and report results
"""
import subprocess
import sys
import json
import time
from pathlib import Path

def check_prerequisites():
    """Check if all prerequisites are met."""
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
            models = [m['name'] for m in data.get('models', [])]
            print(f"   ✓ Ollama is running with {len(models)} models")
            
            if 'qwen2.5:3b' in models or any('qwen' in m.lower() for m in models):
                print("   ✓ qwen2.5:3b model is available")
            else:
                print(f"   Available models: {', '.join(models[:5])}")
                if len(models) > 5:
                    print(f"   ... and {len(models) - 5} more")
                # Don't fail - user might have different model
        else:
            print(f"   ✗ Ollama returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"   ✗ FAILED: {e}")
        print("   → Make sure Ollama is running: ollama serve")
        return False
    
    # Check 2: Required Python modules
    print("\n2. Checking Python modules...")
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
        print("   → Run: pip install -r requirements.txt")
        return False
    
    # Check 3: Database exists
    print("\n3. Checking database...")
    db_path = Path("data/invoices.db")
    if db_path.exists():
        print(f"   ✓ Database exists")
    else:
        print(f"   ⚠ Database not found - evaluation may fail if no data is indexed")
    
    print("\n" + "=" * 70)
    print("PREREQUISITES CHECK PASSED")
    print("=" * 70)
    return True


def run_evaluation():
    """Run the RAG evaluation suite."""
    print("\n" + "=" * 70)
    print("STARTING RAG EVALUATION SUITE")
    print("=" * 70)
    print("\nRunning 65 test cases...")
    print("Estimated duration: 90-100 minutes")
    print("Each test case takes ~90 seconds")
    print()
    
    start_time = time.time()
    
    try:
        # Run the evaluation
        result = subprocess.run(
            [sys.executable, "-m", "rag.test_suite_extended", "--verbose"],
            capture_output=False,
            text=True,
            timeout=6300  # 105 minutes timeout
        )
        
        elapsed = time.time() - start_time
        
        if result.returncode == 0:
            print("\n" + "=" * 70)
            print("EVALUATION COMPLETED SUCCESSFULLY")
            print("=" * 70)
            print(f"Total time: {elapsed/60:.1f} minutes ({elapsed/3600:.2f} hours)")
            return True
        else:
            print(f"\n✗ Evaluation failed with return code {result.returncode}")
            return False
            
    except subprocess.TimeoutExpired:
        print("\n✗ Evaluation timed out after 105 minutes")
        return False
    except Exception as e:
        print(f"\n✗ Error running evaluation: {e}")
        return False


def report_results():
    """Load and report the evaluation results."""
    print("\n" + "=" * 70)
    print("LOADING RESULTS")
    print("=" * 70)
    
    summary_path = Path("test_results/rag_summary.json")
    csv_path = Path("test_results/rag_per_query.csv")
    
    if not summary_path.exists():
        print(f"✗ Results file not found: {summary_path}")
        return False
    
    try:
        with open(summary_path, 'r') as f:
            summary = json.load(f)
        
        print("\n✓ Summary results loaded")
        
        # Display key metrics
        print("\n" + "=" * 70)
        print("KEY METRICS")
        print("=" * 70)
        
        metrics = {
            "Total Questions": summary.get("total_questions", 0),
            "Total Time": f"{summary.get('total_time_seconds', 0) / 60:.1f} minutes",
            "Avg Time/Question": f"{summary.get('avg_time_seconds', 0):.1f}s",
            "Strategy Accuracy": f"{summary.get('strategy_accuracy', 0):.1%}",
            "Hit@3": f"{summary.get('hit_at_3', 0):.1%}",
            "Hit@5": f"{summary.get('hit_at_5', 0):.1%}",
            "Mean MRR": f"{summary.get('mean_mrr', 0):.3f}",
            "Answer Quality": f"{summary.get('answer_quality', 0):.1%}",
            "Numerical Accuracy": f"{summary.get('numerical_accuracy', 0):.1%}",
        }
        
        for key, value in metrics.items():
            print(f"  {key:<25} {value}")
        
        # Check targets
        print("\n" + "=" * 70)
        print("TARGET ASSESSMENT")
        print("=" * 70)
        
        targets = {
            "strategy_accuracy": ("Strategy Accuracy", 0.85, "≥ 0.85"),
            "hit_at_5": ("Hit@5", 0.70, "≥ 0.70"),
            "mean_mrr": ("Mean MRR", 0.55, "≥ 0.55"),
            "answer_quality": ("Answer Quality", 0.60, "≥ 0.60"),
        }
        
        all_passed = True
        for key, (name, target, target_str) in targets.items():
            value = summary.get(key, 0)
            status = "✓ PASS" if value >= target else "✗ FAIL"
            print(f"  {status}  {name:<20} {value:.3f} (target: {target_str})")
            if value < target:
                all_passed = False
        
        print("\n" + "=" * 70)
        if all_passed:
            print("✓ ALL TARGETS MET")
        else:
            print("✗ SOME TARGETS NOT MET")
        print("=" * 70)
        
        # Show per-query file info
        if csv_path.exists():
            print(f"\n✓ Per-query details saved to: {csv_path}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error loading results: {e}")
        return False


def main():
    """Main entry point."""
    # Change to project directory
    project_dir = Path(__file__).parent
    import os
    os.chdir(project_dir)
    
    # Check prerequisites
    if not check_prerequisites():
        print("\n✗ Prerequisites check failed!")
        sys.exit(1)
    
    # Run evaluation
    if not run_evaluation():
        print("\n✗ Evaluation failed!")
        sys.exit(1)
    
    # Report results
    if not report_results():
        print("\n✗ Could not load results!")
        sys.exit(1)
    
    print("\n✓ RAG Evaluation Complete")
    sys.exit(0)


if __name__ == "__main__":
    main()
