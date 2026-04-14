"""
Hallucination Monitor — Logging and monitoring for RAG answer quality.

# FIXED: Bug #8 - Layer 5 of the anti-hallucination system.

Logs every /ask call with hallucination metrics for:
- Post-hoc analysis of hallucination patterns
- Daily summary statistics
- Alert triggering on high hallucination rates
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

LOG_PATH = Path("logs/hallucination_log.jsonl")


def log_answer_event(
    query: str,
    result: Dict[str, Any],
    validation: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log an answer event to the hallucination log.
    
    Called after every /ask response with the full result dict.
    
    Parameters
    ----------
    query : str
        The user's query
    result : dict
        The answer() return dict
    validation : dict, optional
        Result from HallucinationGuard.validate_answer()
    """
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    event = {
        "timestamp": datetime.utcnow().isoformat(),
        "query": query[:500],  # Truncate long queries
        "strategy": result.get("strategy"),
        "sources_count": len(result.get("sources", [])),
        "hallucination_score": result.get("hallucination_score", 0),
        "answer_overridden": result.get("answer_overridden", False),
        "confidence": result.get("confidence", 0),
        "is_false_negative": result.get("is_false_negative", False),
    }
    
    # Add validation details if provided
    if validation:
        event["verified"] = validation.get("verified", True)
        event["unverified_count"] = len(validation.get("unverified_claims", []))
    
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    except IOError:
        # Don't fail the request if logging fails
        pass


def daily_summary() -> Dict[str, Any]:
    """
    Generate a daily summary of hallucination metrics.
    
    Returns dict with:
        total_queries: int
        override_count: int
        override_rate_pct: float
        avg_confidence: float
        low_confidence_count: int
        worst_queries: List[dict] (top 5 by hallucination score)
    """
    if not LOG_PATH.exists():
        return {
            "total_queries": 0,
            "override_count": 0,
            "override_rate_pct": 0.0,
            "avg_confidence": 0.0,
            "low_confidence_count": 0,
            "worst_queries": [],
        }
    
    try:
        lines = LOG_PATH.read_text(encoding="utf-8").splitlines()
        events = [json.loads(line) for line in lines if line.strip()]
    except (IOError, json.JSONDecodeError):
        return {
            "total_queries": 0,
            "override_count": 0,
            "override_rate_pct": 0.0,
            "avg_confidence": 0.0,
            "low_confidence_count": 0,
            "worst_queries": [],
        }
    
    if not events:
        return {
            "total_queries": 0,
            "override_count": 0,
            "override_rate_pct": 0.0,
            "avg_confidence": 0.0,
            "low_confidence_count": 0,
            "worst_queries": [],
        }
    
    # Calculate metrics
    overrides = [e for e in events if e.get("answer_overridden")]
    low_confidence = [e for e in events if e.get("confidence", 1.0) < 0.5]
    
    total = len(events)
    confidence_sum = sum(e.get("confidence", 0) for e in events)
    
    # Sort by hallucination score to find worst queries
    worst = sorted(
        events,
        key=lambda e: e.get("hallucination_score", 0),
        reverse=True
    )[:5]
    
    return {
        "total_queries": total,
        "override_count": len(overrides),
        "override_rate_pct": round(100 * len(overrides) / total, 1),
        "avg_confidence": round(confidence_sum / total, 3),
        "low_confidence_count": len(low_confidence),
        "worst_queries": worst,
    }


def clear_log() -> None:
    """Clear the hallucination log (for testing or maintenance)."""
    if LOG_PATH.exists():
        LOG_PATH.unlink()


def get_recent_events(n: int = 100) -> List[Dict[str, Any]]:
    """Get the n most recent events from the log."""
    if not LOG_PATH.exists():
        return []
    
    try:
        lines = LOG_PATH.read_text(encoding="utf-8").splitlines()
        events = [json.loads(line) for line in lines[-n:] if line.strip()]
        return events
    except (IOError, json.JSONDecodeError):
        return []
