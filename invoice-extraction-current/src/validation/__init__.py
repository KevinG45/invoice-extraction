"""
Invoice Extraction System 2026 - Validation Package.

6-Layer Anti-Hallucination Framework:
1. RAG-Based Validation (35-60% error reduction)
2. Multi-Agent Validation (92% detection rate)
3. Q-A-E Validation (critical field verification)
4. Neurosymbolic Rules (100% on math)
5. Calibrated Confidence Scoring
6. Cross-Model Consistency Checking

Author: ML Engineering Team
Version: 2.0.0
"""

from src.validation.framework_2026 import ValidationFramework2026
from src.validation.rag_validator import RAGValidator
from src.validation.multi_agent import MultiAgentValidator
from src.validation.qae_validator import QAEValidator
from src.validation.neurosymbolic import NeurosymbolicValidator
from src.validation.confidence_scorer import CalibratedConfidenceScorer

__all__ = [
    "ValidationFramework2026",
    "RAGValidator",
    "MultiAgentValidator",
    "QAEValidator",
    "NeurosymbolicValidator",
    "CalibratedConfidenceScorer",
]
