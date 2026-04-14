"""
Hallucination Guard — Entity cross-validation for invoice RAG answers.

# FIXED: Bug #8 - Prevents LLM confabulation by cross-validating
claimed entities against retrieved context.

This is Layer 2 of the 5-layer anti-hallucination system.
"""

import re
from typing import List, Dict, Any


class HallucinationGuard:
    """Cross-validate LLM answers against retrieved context."""
    
    def validate_answer(self, answer: str, context: str, sources: List[str]) -> Dict[str, Any]:
        """
        Cross-validate answer entities against retrieved context.
        
        Parameters
        ----------
        answer : str
            The LLM-generated answer
        context : str
            The retrieved context provided to the LLM
        sources : List[str]
            List of source file names
        
        Returns
        -------
        dict with keys:
            verified: bool - True if answer passes validation
            hallucination_score: float - 0.0 (no hallucination) to 1.0 (all claims unverified)
            unverified_claims: List[str] - Claims in answer not found in context
            confidence: str - "high", "medium", or "low"
        """
        unverified = []
        
        # Handle None/empty inputs gracefully
        if not answer:
            return {
                "verified": True,
                "hallucination_score": 0.0,
                "unverified_claims": [],
                "confidence": "high",
            }
        if not context:
            context = ""
        
        # Extract numeric values from answer
        answer_numbers = re.findall(r'\b[\d,]+\.?\d*\b', answer)
        for num in answer_numbers:
            clean = num.replace(",", "")
            # Skip very small numbers (likely not amounts)
            if len(clean) >= 2 and clean not in context.replace(",", ""):
                # Check for the number without commas in context
                if not self._number_in_context(clean, context):
                    unverified.append(f"number:{num}")
        
        # Extract named entities (capitalised phrases, company names)
        # Match 2+ consecutive capitalized words
        answer_entities = re.findall(r'\b[A-Z][A-Z\s&.]{2,}\b', answer)
        for entity in answer_entities:
            entity_clean = entity.strip()
            # Skip common words
            if entity_clean.upper() in {"THE", "THIS", "THAT", "FOR", "FROM", "WITH"}:
                continue
            if entity_clean.lower() not in context.lower():
                unverified.append(f"entity:{entity_clean}")
        
        # Extract GSTINs from answer (15-char Indian tax IDs)
        answer_gstins = re.findall(r'\b\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z\d]\b', answer.upper())
        for gstin in answer_gstins:
            if gstin not in context.upper():
                unverified.append(f"gstin:{gstin}")
        
        # Extract dates from answer
        answer_dates = re.findall(r'\b\d{4}[-/]\d{2}[-/]\d{2}\b', answer)
        for date in answer_dates:
            normalized_date = date.replace("/", "-")
            if normalized_date not in context.replace("/", "-"):
                unverified.append(f"date:{date}")
        
        # Calculate hallucination score
        total_claims = len(answer_numbers) + len(answer_entities) + len(answer_gstins) + len(answer_dates)
        if total_claims == 0:
            score = 0.0
        else:
            score = len(unverified) / total_claims
        
        # Determine confidence level
        if score < 0.10:
            confidence = "high"
        elif score < 0.30:
            confidence = "medium"
        else:
            confidence = "low"
        
        return {
            "verified": score < 0.10,
            "hallucination_score": round(score, 3),
            "unverified_claims": unverified,
            "confidence": confidence
        }
    
    def _number_in_context(self, num: str, context: str) -> bool:
        """Check if a number appears in context (handles formatting variations)."""
        # Try exact match
        if num in context:
            return True
        
        # Try with different thousand separators
        try:
            num_float = float(num)
            # Check for integer form
            if num_float == int(num_float):
                if str(int(num_float)) in context:
                    return True
            # Check for 2 decimal places
            formatted = f"{num_float:.2f}"
            if formatted in context:
                return True
        except ValueError:
            pass
        
        return False
    
    def check_false_negative(self, answer: str, sources: List[str]) -> bool:
        """
        Check if LLM says not-found but retrieved sources exist.
        
        This is a critical hallucination pattern where the LLM ignores
        valid context and claims no data was found.
        
        Returns True if this is a false negative.
        """
        not_found_phrases = [
            "not found", "no invoice", "does not exist",
            "no results", "unable to find", "cannot find",
            "was not found", "are not found", "weren't found",
            "could not find", "no data", "no matching",
            "did not find", "don't have"
        ]
        
        # Safety check for None answer
        if not answer:
            return False
        
        answer_lower = answer.lower()
        
        # Check if answer claims not found
        claims_not_found = any(p in answer_lower for p in not_found_phrases)
        
        # If claims not found but sources exist, it's a false negative
        if claims_not_found and len(sources) > 0:
            return True
        
        return False


def calculate_confidence(strategy: str, results: list, hallucination_score: float) -> float:
    """
    Calculate overall confidence score for an answer.
    # FIXED: Bug #16 - Adds confidence scores to all answers
    
    Parameters
    ----------
    strategy : str
        The retrieval strategy used (sql, bm25, vector, hybrid, memory_only)
    results : list
        The retrieval results
    hallucination_score : float
        Score from HallucinationGuard.validate_answer()
    
    Returns
    -------
    float between 0.0 and 1.0
    """
    # Base confidence depends on strategy determinism
    if strategy == "sql":
        base = 0.90  # SQL is deterministic
    elif strategy == "bm25":
        # BM25 confidence based on top score
        if results:
            top_score = results[0].get("score", 0)
            base = min(top_score / 10.0, 0.95)  # Normalize BM25 score
        else:
            base = 0.30
    elif strategy == "vector":
        # Vector confidence based on distance (lower is better)
        if results:
            top_dist = results[0].get("distance", 1.0)
            base = max(0, 1.0 - top_dist)
        else:
            base = 0.30
    elif strategy == "memory_only":
        base = 0.90  # Memory answers are from prior verified context
    else:  # hybrid
        base = 0.75
    
    # Reduce confidence based on hallucination score
    confidence = base * (1.0 - hallucination_score)
    
    return round(confidence, 3)
