"""
Metrics Calculator Module.

This module provides comprehensive metrics calculation for
evaluating invoice extraction accuracy.

Metrics Include:
    - Field-level accuracy (exact match)
    - Partial match scores
    - Missing field rates
    - Overall extraction rate
    - Confidence analysis

Author: ML Engineering Team
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
import re
from datetime import datetime

from src.utils.logger import get_logger

# Initialize module logger
logger = get_logger(__name__)


@dataclass
class FieldMetrics:
    """
    Metrics for a single field across all samples.
    
    Attributes:
        field_name: Name of the field
        total_samples: Total number of samples evaluated
        extracted_count: Number of samples where field was extracted
        correct_count: Number of exact matches
        partial_match_count: Number of partial matches
        missing_count: Number of missing values
        accuracy: Exact match accuracy (0-1)
        extraction_rate: Rate of successful extraction (0-1)
        partial_accuracy: Accuracy including partial matches (0-1)
    """
    field_name: str
    total_samples: int = 0
    extracted_count: int = 0
    correct_count: int = 0
    partial_match_count: int = 0
    missing_count: int = 0
    accuracy: float = 0.0
    extraction_rate: float = 0.0
    partial_accuracy: float = 0.0
    avg_confidence: float = 0.0


@dataclass
class EvaluationResult:
    """
    Complete evaluation results.
    
    Attributes:
        field_metrics: Dictionary of field name to FieldMetrics
        overall_accuracy: Overall exact match accuracy
        overall_extraction_rate: Overall extraction rate
        avg_confidence: Average confidence across all fields
        total_samples: Total number of samples evaluated
        timestamp: Evaluation timestamp
    """
    field_metrics: Dict[str, FieldMetrics] = field(default_factory=dict)
    overall_accuracy: float = 0.0
    overall_extraction_rate: float = 0.0
    avg_confidence: float = 0.0
    total_samples: int = 0
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'overall_accuracy': self.overall_accuracy,
            'overall_extraction_rate': self.overall_extraction_rate,
            'avg_confidence': self.avg_confidence,
            'total_samples': self.total_samples,
            'timestamp': self.timestamp,
            'field_metrics': {
                name: {
                    'accuracy': m.accuracy,
                    'extraction_rate': m.extraction_rate,
                    'partial_accuracy': m.partial_accuracy,
                    'extracted_count': m.extracted_count,
                    'correct_count': m.correct_count,
                    'missing_count': m.missing_count,
                    'avg_confidence': m.avg_confidence
                }
                for name, m in self.field_metrics.items()
            }
        }
    
    def print_report(self) -> str:
        """Generate a formatted report string."""
        lines = [
            "=" * 60,
            "EXTRACTION EVALUATION REPORT",
            "=" * 60,
            f"Timestamp: {self.timestamp}",
            f"Total Samples: {self.total_samples}",
            "-" * 60,
            "",
            "OVERALL METRICS:",
            f"  Accuracy:        {self.overall_accuracy * 100:.1f}%",
            f"  Extraction Rate: {self.overall_extraction_rate * 100:.1f}%",
            f"  Avg Confidence:  {self.avg_confidence:.2f}",
            "",
            "-" * 60,
            "FIELD-LEVEL METRICS:",
            "",
        ]
        
        for name, m in self.field_metrics.items():
            lines.extend([
                f"  {name}:",
                f"    Accuracy:        {m.accuracy * 100:.1f}%",
                f"    Extraction Rate: {m.extraction_rate * 100:.1f}%",
                f"    Partial Match:   {m.partial_accuracy * 100:.1f}%",
                f"    Extracted/Total: {m.extracted_count}/{m.total_samples}",
                f"    Avg Confidence:  {m.avg_confidence:.2f}",
                ""
            ])
        
        lines.append("=" * 60)
        return "\n".join(lines)


class MetricsCalculator:
    """
    Calculates evaluation metrics for invoice extraction.
    
    Compares extracted results against ground truth and computes
    various accuracy and quality metrics.
    
    Attributes:
        fields: List of fields to evaluate
        case_sensitive: Whether comparisons are case-sensitive
        normalize_whitespace: Whether to normalize whitespace
        
    Example:
        >>> calculator = MetricsCalculator()
        >>> result = calculator.evaluate(predictions, ground_truth)
        >>> print(result.print_report())
    """
    
    # Default fields to evaluate
    DEFAULT_FIELDS = [
        'invoice_number',
        'invoice_date',
        'vendor_name',
        'customer_name',
        'total_amount',
        'payment_due_date'
    ]
    
    def __init__(
        self,
        fields: Optional[List[str]] = None,
        case_sensitive: bool = False,
        normalize_whitespace: bool = True,
        partial_match_threshold: float = 0.8
    ) -> None:
        """
        Initialize the metrics calculator.
        
        Args:
            fields: List of field names to evaluate.
            case_sensitive: Whether string comparisons are case-sensitive.
            normalize_whitespace: Whether to normalize whitespace.
            partial_match_threshold: Threshold for partial match scoring.
        """
        self.fields = fields or self.DEFAULT_FIELDS
        self.case_sensitive = case_sensitive
        self.normalize_whitespace = normalize_whitespace
        self.partial_match_threshold = partial_match_threshold
        
        logger.debug(f"MetricsCalculator initialized (fields: {len(self.fields)})")
    
    def evaluate(
        self,
        predictions: List[Dict[str, Any]],
        ground_truth: List[Dict[str, Any]],
        confidence_scores: Optional[List[Dict[str, float]]] = None
    ) -> EvaluationResult:
        """
        Evaluate predictions against ground truth.
        
        Args:
            predictions: List of prediction dictionaries.
            ground_truth: List of ground truth dictionaries.
            confidence_scores: Optional list of confidence score dictionaries.
            
        Returns:
            EvaluationResult with computed metrics.
            
        Raises:
            ValueError: If predictions and ground truth lengths don't match.
        """
        if len(predictions) != len(ground_truth):
            raise ValueError(
                f"Predictions ({len(predictions)}) and ground truth "
                f"({len(ground_truth)}) must have same length"
            )
        
        total_samples = len(predictions)
        
        if total_samples == 0:
            return EvaluationResult()
        
        # Initialize field metrics
        field_metrics = {
            name: FieldMetrics(field_name=name, total_samples=total_samples)
            for name in self.fields
        }
        
        # Compute per-field metrics
        for idx, (pred, gt) in enumerate(zip(predictions, ground_truth)):
            conf = confidence_scores[idx] if confidence_scores else {}
            
            for field_name in self.fields:
                pred_value = pred.get(field_name, '') or ''
                gt_value = gt.get(field_name, '') or ''
                field_conf = conf.get(field_name, 0.0)
                
                metrics = field_metrics[field_name]
                
                # Track confidence
                if field_conf > 0:
                    metrics.avg_confidence = (
                        (metrics.avg_confidence * idx + field_conf) / (idx + 1)
                    )
                
                # Check if field was extracted
                if pred_value:
                    metrics.extracted_count += 1
                else:
                    metrics.missing_count += 1
                    continue
                
                # Compare values
                is_exact, is_partial = self._compare_values(
                    pred_value, gt_value, field_name
                )
                
                if is_exact:
                    metrics.correct_count += 1
                    metrics.partial_match_count += 1
                elif is_partial:
                    metrics.partial_match_count += 1
        
        # Calculate final metrics for each field
        total_accuracy = 0.0
        total_extraction_rate = 0.0
        total_confidence = 0.0
        
        for name, metrics in field_metrics.items():
            if metrics.total_samples > 0:
                metrics.extraction_rate = metrics.extracted_count / metrics.total_samples
                
                # Accuracy is based on extracted samples only
                if metrics.extracted_count > 0:
                    metrics.accuracy = metrics.correct_count / metrics.total_samples
                    metrics.partial_accuracy = metrics.partial_match_count / metrics.total_samples
                
                total_accuracy += metrics.accuracy
                total_extraction_rate += metrics.extraction_rate
                total_confidence += metrics.avg_confidence
        
        # Calculate overall metrics
        num_fields = len(self.fields)
        overall_accuracy = total_accuracy / num_fields if num_fields > 0 else 0
        overall_extraction_rate = total_extraction_rate / num_fields if num_fields > 0 else 0
        avg_confidence = total_confidence / num_fields if num_fields > 0 else 0
        
        return EvaluationResult(
            field_metrics=field_metrics,
            overall_accuracy=overall_accuracy,
            overall_extraction_rate=overall_extraction_rate,
            avg_confidence=avg_confidence,
            total_samples=total_samples
        )
    
    def _compare_values(
        self,
        predicted: str,
        ground_truth: str,
        field_name: str
    ) -> Tuple[bool, bool]:
        """
        Compare predicted and ground truth values.
        
        Args:
            predicted: Predicted value.
            ground_truth: Ground truth value.
            field_name: Name of the field (for type-specific comparison).
            
        Returns:
            Tuple of (is_exact_match, is_partial_match).
        """
        # Handle empty ground truth
        if not ground_truth:
            return (False, False)
        
        # Normalize values
        pred_norm = self._normalize_value(predicted, field_name)
        gt_norm = self._normalize_value(ground_truth, field_name)
        
        # Exact match
        if pred_norm == gt_norm:
            return (True, True)
        
        # Partial match using similarity
        similarity = self._string_similarity(pred_norm, gt_norm)
        
        if similarity >= self.partial_match_threshold:
            return (False, True)
        
        return (False, False)
    
    def _normalize_value(self, value: str, field_name: str) -> str:
        """
        Normalize a value for comparison.
        
        Args:
            value: Value to normalize.
            field_name: Field name for type-specific normalization.
            
        Returns:
            Normalized value string.
        """
        if not value:
            return ''
        
        # Convert to string
        value = str(value).strip()
        
        # Case normalization
        if not self.case_sensitive:
            value = value.lower()
        
        # Whitespace normalization
        if self.normalize_whitespace:
            value = ' '.join(value.split())
        
        # Field-specific normalization
        if 'amount' in field_name.lower():
            # Remove currency symbols and normalize decimals
            value = re.sub(r'[^\d.,]', '', value)
            value = value.replace(',', '.')
            # Remove trailing zeros
            try:
                value = str(float(value))
            except ValueError:
                pass
        
        elif 'date' in field_name.lower():
            # Try to normalize dates
            value = re.sub(r'[^\d]', '', value)
        
        return value
    
    def _string_similarity(self, s1: str, s2: str) -> float:
        """
        Calculate similarity between two strings using Levenshtein ratio.
        
        Args:
            s1: First string.
            s2: Second string.
            
        Returns:
            Similarity score between 0 and 1.
        """
        if not s1 or not s2:
            return 0.0
        
        if s1 == s2:
            return 1.0
        
        # Simple Levenshtein-based similarity
        len1, len2 = len(s1), len(s2)
        
        if len1 == 0 or len2 == 0:
            return 0.0
        
        # Create distance matrix
        distances = [[0] * (len2 + 1) for _ in range(len1 + 1)]
        
        for i in range(len1 + 1):
            distances[i][0] = i
        for j in range(len2 + 1):
            distances[0][j] = j
        
        for i in range(1, len1 + 1):
            for j in range(1, len2 + 1):
                cost = 0 if s1[i-1] == s2[j-1] else 1
                distances[i][j] = min(
                    distances[i-1][j] + 1,
                    distances[i][j-1] + 1,
                    distances[i-1][j-1] + cost
                )
        
        distance = distances[len1][len2]
        max_len = max(len1, len2)
        
        return 1.0 - (distance / max_len)
    
    def evaluate_single(
        self,
        prediction: Dict[str, Any],
        ground_truth: Dict[str, Any],
        confidence_scores: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Evaluate a single prediction against ground truth.
        
        Args:
            prediction: Prediction dictionary.
            ground_truth: Ground truth dictionary.
            confidence_scores: Optional confidence scores.
            
        Returns:
            Dictionary with per-field comparison results.
        """
        results = {}
        
        for field_name in self.fields:
            pred_value = prediction.get(field_name, '') or ''
            gt_value = ground_truth.get(field_name, '') or ''
            confidence = confidence_scores.get(field_name, 0.0) if confidence_scores else 0.0
            
            is_exact, is_partial = self._compare_values(pred_value, gt_value, field_name)
            
            results[field_name] = {
                'predicted': pred_value,
                'ground_truth': gt_value,
                'exact_match': is_exact,
                'partial_match': is_partial,
                'confidence': confidence,
                'extracted': bool(pred_value)
            }
        
        return results
