"""
RAG Evaluation Framework — measures retrieval and answer quality.

Metrics:
    - Hit@K: Did the correct source appear in the top-K retrieved results?
    - MRR (Mean Reciprocal Rank): Average of 1/rank for the first correct result.
    - Answer accuracy: Fuzzy match + numerical tolerance scoring.

Usage:
    python -m rag.evaluator          # Run all test cases
    python -m rag.evaluator --verbose # Show detailed per-question results
"""

import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Test Suite ────────────────────────────────────────────────────────────
# Each test case has:
#   - question: the user query
#   - expected_strategy: which retrieval strategy should be chosen
#   - expected_sources: source files that MUST appear in results (at least one)
#   - expected_answer_contains: keywords/phrases the answer should contain
#   - expected_number: if the answer is numeric, the expected value (with tolerance)

TEST_CASES: List[Dict[str, Any]] = [
    # ── SQL strategy tests (aggregation/analytics) ────────────────────
    {
        "question": "How many invoices are in the system?",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": [],
        "expected_number": None,
        "category": "sql_aggregate",
    },
    {
        "question": "What is the total tax amount across all invoices?",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": [],
        "expected_number": None,
        "category": "sql_aggregate",
    },
    {
        "question": "Which vendor has the highest total invoice value?",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": [],
        "expected_number": None,
        "category": "sql_aggregate",
    },
    {
        "question": "What is the average invoice amount?",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": [],
        "expected_number": None,
        "category": "sql_aggregate",
    },
    {
        "question": "How many invoices have validation passed?",
        "expected_strategy": "sql",
        "expected_sources": [],
        "expected_answer_contains": [],
        "expected_number": None,
        "category": "sql_aggregate",
    },

    # ── BM25 strategy tests (keyword/exact lookup) ───────────────────
    {
        "question": "Show me invoice GST001",
        "expected_strategy": "bm25",
        "expected_sources": ["GST001.pdf"],
        "expected_answer_contains": ["GST001", "GST-001"],
        "expected_number": None,
        "category": "bm25_lookup",
    },
    {
        "question": "Find the invoice with GSTIN 36ARKPC6820F1ZZ",
        "expected_strategy": "bm25",
        "expected_sources": ["GST001.pdf"],
        "expected_answer_contains": ["36ARKPC6820F1ZZ"],
        "expected_number": None,
        "category": "bm25_lookup",
    },
    {
        "question": 'What are the details of "NIREL DIGITALS" invoices?',
        "expected_strategy": "bm25",
        "expected_sources": ["GST001.pdf"],
        "expected_answer_contains": ["NIREL"],
        "expected_number": None,
        "category": "bm25_lookup",
    },

    # ── Vector strategy tests (semantic/vague) ────────────────────────
    {
        "question": "Show invoices similar to printing services",
        "expected_strategy": "vector",
        "expected_sources": [],
        "expected_answer_contains": [],
        "expected_number": None,
        "category": "vector_semantic",
    },
    {
        "question": "Describe the types of products sold across all invoices",
        "expected_strategy": "vector",
        "expected_sources": [],
        "expected_answer_contains": [],
        "expected_number": None,
        "category": "vector_semantic",
    },

    # ── Hybrid strategy tests (general/mixed) ─────────────────────────
    {
        "question": "Tell me about the last invoice we processed",
        "expected_strategy": "hybrid",
        "expected_sources": [],
        "expected_answer_contains": [],
        "expected_number": None,
        "category": "hybrid_general",
    },
    {
        "question": "What payment methods are used in our invoices?",
        "expected_strategy": "hybrid",
        "expected_sources": [],
        "expected_answer_contains": [],
        "expected_number": None,
        "category": "hybrid_general",
    },

    # ── Cross-strategy: specific invoice details ──────────────────────
    {
        "question": "What is the total amount for invoice GST001?",
        "expected_strategy": "bm25",
        "expected_sources": ["GST001.pdf"],
        "expected_answer_contains": ["3115"],
        "expected_number": 3115.2,
        "category": "detail_lookup",
    },
    {
        "question": "Who is the vendor for invoice GST001?",
        "expected_strategy": "bm25",
        "expected_sources": ["GST001.pdf"],
        "expected_answer_contains": ["NIREL"],
        "expected_number": None,
        "category": "detail_lookup",
    },

    # ── Edge cases ────────────────────────────────────────────────────
    {
        "question": "What is the meaning of life?",
        "expected_strategy": "hybrid",
        "expected_sources": [],
        "expected_answer_contains": ["don't have enough information", "not", "cannot"],
        "expected_number": None,
        "category": "out_of_scope",
    },
]


# ── Scoring Functions ─────────────────────────────────────────────────────

def score_strategy(predicted: str, expected: str) -> float:
    """1.0 if strategy matches, 0.0 otherwise."""
    return 1.0 if predicted == expected else 0.0


def score_hit_at_k(sources: List[str], expected_sources: List[str], k: int = 5) -> float:
    """1.0 if any expected source appears in the top-K sources."""
    if not expected_sources:
        return 1.0  # No expectation = automatic pass
    top_sources = set(sources[:k])
    return 1.0 if any(s in top_sources for s in expected_sources) else 0.0


def score_mrr(sources: List[str], expected_sources: List[str]) -> float:
    """Mean Reciprocal Rank: 1/rank of the first expected source found."""
    if not expected_sources:
        return 1.0
    for rank, source in enumerate(sources, 1):
        if source in expected_sources:
            return 1.0 / rank
    return 0.0


def score_answer_contains(answer: str, expected_phrases: List[str]) -> float:
    """Fraction of expected phrases found in the answer (case-insensitive)."""
    if not expected_phrases:
        return 1.0  # No expectation = automatic pass
    if answer is None:
        return 0.0  # No answer = fail
    answer_lower = answer.lower()
    hits = sum(1 for phrase in expected_phrases if phrase.lower() in answer_lower)
    return hits / len(expected_phrases)


def score_numerical(answer: str, expected: Optional[float], tolerance: float = 0.05) -> float:
    """Check if the expected number appears in the answer (within tolerance)."""
    if expected is None:
        return 1.0  # No expectation = automatic pass
    if answer is None:
        return 0.0  # No answer = fail

    # Extract all numbers from the answer
    numbers = re.findall(r"[\d,]+\.?\d*", answer)
    for num_str in numbers:
        try:
            num = float(num_str.replace(",", ""))
            if abs(num - expected) / max(abs(expected), 1e-9) <= tolerance:
                return 1.0
        except ValueError:
            continue
    return 0.0


# ── Evaluation Runner ─────────────────────────────────────────────────────

def evaluate_single(test_case: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, float]:
    """Score a single test case against the RAG result."""
    return {
        "strategy_match": score_strategy(
            result.get("strategy", ""),
            test_case.get("expected_strategy", ""),
        ),
        "hit_at_3": score_hit_at_k(
            result.get("sources", []),
            test_case.get("expected_sources", []),
            k=3,
        ),
        "hit_at_5": score_hit_at_k(
            result.get("sources", []),
            test_case.get("expected_sources", []),
            k=5,
        ),
        "mrr": score_mrr(
            result.get("sources", []),
            test_case.get("expected_sources", []),
        ),
        "answer_contains": score_answer_contains(
            result.get("answer", ""),
            test_case.get("expected_answer_contains", []),
        ),
        "numerical_accuracy": score_numerical(
            result.get("answer", ""),
            test_case.get("expected_number"),
        ),
    }


def run_evaluation(
    answer_fn=None,
    test_cases: Optional[List[Dict]] = None,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Run the full evaluation suite.

    Args:
        answer_fn: Callable that takes a question string and returns a result dict.
                   Defaults to rag.qa_chain.answer.
        test_cases: List of test case dicts. Defaults to TEST_CASES.
        verbose: Print per-question details.

    Returns:
        Summary dict with aggregate metrics and per-question scores.
    """
    if answer_fn is None:
        from rag.qa_chain import answer as _answer
        answer_fn = _answer

    if test_cases is None:
        test_cases = TEST_CASES

    results = []
    total_time = 0.0

    for i, tc in enumerate(test_cases, 1):
        question = tc["question"]
        category = tc.get("category", "unknown")

        if verbose:
            print(f"\n{'='*70}")
            print(f"[{i}/{len(test_cases)}] ({category}) {question}")
            print("=" * 70)

        start = time.time()
        try:
            result = answer_fn(question)
        except Exception as e:
            result = {"answer": f"ERROR: {e}", "strategy": "error", "sources": []}
        elapsed = time.time() - start
        total_time += elapsed

        scores = evaluate_single(tc, result)
        scores["time_seconds"] = round(elapsed, 2)

        if verbose:
            print(f"  Strategy: {result.get('strategy', '?')} (expected: {tc['expected_strategy']})"
                  f" -> {'PASS' if scores['strategy_match'] == 1.0 else 'FAIL'}")
            print(f"  Sources: {result.get('sources', [])}")
            print(f"  Hit@3: {scores['hit_at_3']:.0f} | Hit@5: {scores['hit_at_5']:.0f}"
                  f" | MRR: {scores['mrr']:.2f}")
            print(f"  Answer contains: {scores['answer_contains']:.0%}"
                  f" | Numerical: {scores['numerical_accuracy']:.0%}")
            print(f"  Time: {elapsed:.1f}s")
            answer_preview = result.get("answer", "")[:200]
            print(f"  Answer: {answer_preview}...")

        results.append({
            "question": question,
            "category": category,
            "scores": scores,
            "strategy_used": result.get("strategy", ""),
            "reranked": result.get("reranked", False),
        })

    # ── Aggregate metrics ─────────────────────────────────────────────
    n = len(results)
    if n == 0:
        return {"error": "No test cases run"}

    agg = {
        "total_questions": n,
        "total_time_seconds": round(total_time, 2),
        "avg_time_seconds": round(total_time / n, 2),
        "strategy_accuracy": round(sum(r["scores"]["strategy_match"] for r in results) / n, 3),
        "hit_at_3": round(sum(r["scores"]["hit_at_3"] for r in results) / n, 3),
        "hit_at_5": round(sum(r["scores"]["hit_at_5"] for r in results) / n, 3),
        "mean_mrr": round(sum(r["scores"]["mrr"] for r in results) / n, 3),
        "answer_quality": round(sum(r["scores"]["answer_contains"] for r in results) / n, 3),
        "numerical_accuracy": round(sum(r["scores"]["numerical_accuracy"] for r in results) / n, 3),
    }

    # Per-category breakdown
    categories = set(r["category"] for r in results)
    category_breakdown = {}
    for cat in sorted(categories):
        cat_results = [r for r in results if r["category"] == cat]
        cn = len(cat_results)
        category_breakdown[cat] = {
            "count": cn,
            "strategy_accuracy": round(sum(r["scores"]["strategy_match"] for r in cat_results) / cn, 3),
            "answer_quality": round(sum(r["scores"]["answer_contains"] for r in cat_results) / cn, 3),
        }

    return {
        "summary": agg,
        "category_breakdown": category_breakdown,
        "details": results,
    }


# ── CLI entry point ───────────────────────────────────────────────────────

if __name__ == "__main__":
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    # Router-only mode (no LLM needed) — just test routing accuracy
    if "--router-only" in sys.argv:
        from rag.router import route_query

        print("\n" + "=" * 60)
        print("ROUTER-ONLY EVALUATION (no LLM calls)")
        print("=" * 60)

        correct = 0
        total = len(TEST_CASES)

        for i, tc in enumerate(TEST_CASES, 1):
            result = route_query(tc["question"])
            got = result["strategy"]
            expected = tc["expected_strategy"]
            ok = got == expected
            if ok:
                correct += 1
            tag = "PASS" if ok else "FAIL"
            print(f"  [{tag}] {tc['question'][:60]:<60} expected={expected:<7} got={got}")

        print(f"\nRouter accuracy: {correct}/{total} ({correct/total:.0%})")
        sys.exit(0)

    # Full evaluation
    print("\n" + "=" * 60)
    print("FULL RAG EVALUATION")
    print("=" * 60)

    report = run_evaluation(verbose=verbose)
    summary = report["summary"]

    print(f"\n{'='*60}")
    print("SUMMARY")
    print("=" * 60)
    print(f"  Questions:          {summary['total_questions']}")
    print(f"  Total time:         {summary['total_time_seconds']:.1f}s")
    print(f"  Avg time/question:  {summary['avg_time_seconds']:.1f}s")
    print(f"  Strategy accuracy:  {summary['strategy_accuracy']:.0%}")
    print(f"  Hit@3:              {summary['hit_at_3']:.0%}")
    print(f"  Hit@5:              {summary['hit_at_5']:.0%}")
    print(f"  Mean MRR:           {summary['mean_mrr']:.3f}")
    print(f"  Answer quality:     {summary['answer_quality']:.0%}")
    print(f"  Numerical accuracy: {summary['numerical_accuracy']:.0%}")

    print(f"\n{'='*60}")
    print("PER-CATEGORY BREAKDOWN")
    print("=" * 60)
    for cat, stats in report["category_breakdown"].items():
        print(f"  {cat:<20} n={stats['count']:<3}"
              f" strategy={stats['strategy_accuracy']:.0%}"
              f" quality={stats['answer_quality']:.0%}")
