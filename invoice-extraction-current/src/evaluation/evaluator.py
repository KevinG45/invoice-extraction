"""
Main Evaluator Module.

This module provides the unified Evaluator class that orchestrates
all evaluation operations including metrics calculation, ground truth
comparison, and report generation.

Author: ML Engineering Team
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import json

from config import get_config
from src.utils.logger import get_logger
from src.utils.helpers import ensure_directory, generate_timestamp
from src.model_inference.extraction_result import ExtractionResult
from .metrics import MetricsCalculator, EvaluationResult
from .ground_truth import GroundTruthLoader

# Initialize module logger
logger = get_logger(__name__)


class Evaluator:
    """
    Main evaluator for invoice extraction system.
    
    Orchestrates ground truth loading, metrics calculation,
    and report generation.
    
    Attributes:
        metrics_calculator: MetricsCalculator instance
        ground_truth: GroundTruthLoader instance
        
    Example:
        >>> evaluator = Evaluator("ground_truth.json")
        >>> result = evaluator.evaluate(extraction_results)
        >>> print(result.print_report())
    """
    
    def __init__(
        self,
        ground_truth_path: Optional[str] = None,
        case_sensitive: bool = False,
        partial_match_threshold: float = 0.8
    ) -> None:
        """
        Initialize the evaluator.
        
        Args:
            ground_truth_path: Path to ground truth file.
            case_sensitive: Whether comparisons are case-sensitive.
            partial_match_threshold: Threshold for partial match scoring.
        """
        self.metrics_calculator = MetricsCalculator(
            case_sensitive=case_sensitive,
            partial_match_threshold=partial_match_threshold
        )
        
        self.ground_truth = None
        if ground_truth_path:
            self.load_ground_truth(ground_truth_path)
        
        logger.debug("Evaluator initialized")
    
    def load_ground_truth(self, path: str) -> None:
        """
        Load ground truth data from file.
        
        Args:
            path: Path to ground truth file.
        """
        self.ground_truth = GroundTruthLoader(path)
        validation = self.ground_truth.validate()
        
        if validation['invalid_records'] > 0:
            logger.warning(
                f"Ground truth has {validation['invalid_records']} incomplete records"
            )
    
    def evaluate(
        self,
        results: Union[List[ExtractionResult], List[Dict[str, Any]]],
        ground_truth: Optional[List[Dict[str, Any]]] = None
    ) -> EvaluationResult:
        """
        Evaluate extraction results.
        
        Args:
            results: Extraction results to evaluate.
            ground_truth: Optional ground truth data. If None, uses loaded data.
            
        Returns:
            EvaluationResult with computed metrics.
        """
        # Convert ExtractionResult objects to dictionaries
        predictions = []
        confidence_scores = []
        
        for r in results:
            if isinstance(r, ExtractionResult):
                predictions.append(r.to_dict())
                confidence_scores.append(r.confidence_scores)
            else:
                predictions.append(r)
                confidence_scores.append(r.get('confidence_scores', {}))
        
        # Get ground truth
        if ground_truth is None:
            if self.ground_truth is None:
                raise ValueError(
                    "No ground truth available. "
                    "Load ground truth or provide it as argument."
                )
            
            # Match predictions to ground truth by filename
            gt_data = []
            for pred in predictions:
                source_file = pred.get('source_file', '')
                gt_record = self.ground_truth.get_by_filename(source_file)
                
                if gt_record:
                    gt_data.append(gt_record)
                else:
                    # Create empty record if no match found
                    logger.warning(f"No ground truth for: {source_file}")
                    gt_data.append({})
            
            ground_truth = gt_data
        
        # Calculate metrics
        result = self.metrics_calculator.evaluate(
            predictions=predictions,
            ground_truth=ground_truth,
            confidence_scores=confidence_scores
        )
        
        logger.info(
            f"Evaluation complete: {result.overall_accuracy*100:.1f}% accuracy "
            f"on {result.total_samples} samples"
        )
        
        return result
    
    def evaluate_single(
        self,
        result: Union[ExtractionResult, Dict[str, Any]],
        ground_truth: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Evaluate a single extraction result.
        
        Args:
            result: Single extraction result.
            ground_truth: Ground truth for this result.
            
        Returns:
            Dictionary with per-field comparison results.
        """
        if isinstance(result, ExtractionResult):
            prediction = result.to_dict()
            confidence = result.confidence_scores
        else:
            prediction = result
            confidence = result.get('confidence_scores', {})
        
        if ground_truth is None:
            if self.ground_truth is None:
                raise ValueError("No ground truth available")
            
            source_file = prediction.get('source_file', '')
            ground_truth = self.ground_truth.get_by_filename(source_file) or {}
        
        return self.metrics_calculator.evaluate_single(
            prediction=prediction,
            ground_truth=ground_truth,
            confidence_scores=confidence
        )
    
    def generate_report(
        self,
        evaluation_result: EvaluationResult,
        output_path: Optional[str] = None,
        format: str = 'txt'
    ) -> str:
        """
        Generate an evaluation report.
        
        Args:
            evaluation_result: Evaluation result to report.
            output_path: Path for report file. If None, returns string.
            format: Report format ('txt', 'json', 'html').
            
        Returns:
            Report string or path to saved file.
        """
        if format == 'txt':
            report = evaluation_result.print_report()
        elif format == 'json':
            report = json.dumps(evaluation_result.to_dict(), indent=2)
        elif format == 'html':
            report = self._generate_html_report(evaluation_result)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        if output_path:
            ensure_directory(Path(output_path).parent)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report)
            logger.info(f"Report saved to: {output_path}")
            return output_path
        
        return report
    
    def _generate_html_report(self, result: EvaluationResult) -> str:
        """Generate HTML formatted report."""
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Invoice Extraction Evaluation Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        h2 {{ color: #555; border-bottom: 2px solid #ddd; padding-bottom: 5px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
        th {{ background-color: #4472C4; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .metric-card {{ display: inline-block; margin: 10px; padding: 15px; 
                       background: #f8f9fa; border-radius: 5px; min-width: 150px; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #4472C4; }}
        .metric-label {{ color: #666; }}
        .good {{ color: #28a745; }}
        .medium {{ color: #ffc107; }}
        .poor {{ color: #dc3545; }}
    </style>
</head>
<body>
    <h1>Invoice Extraction Evaluation Report</h1>
    <p>Generated: {result.timestamp}</p>
    
    <h2>Overall Metrics</h2>
    <div class="metric-card">
        <div class="metric-value">{result.overall_accuracy*100:.1f}%</div>
        <div class="metric-label">Accuracy</div>
    </div>
    <div class="metric-card">
        <div class="metric-value">{result.overall_extraction_rate*100:.1f}%</div>
        <div class="metric-label">Extraction Rate</div>
    </div>
    <div class="metric-card">
        <div class="metric-value">{result.avg_confidence:.2f}</div>
        <div class="metric-label">Avg Confidence</div>
    </div>
    <div class="metric-card">
        <div class="metric-value">{result.total_samples}</div>
        <div class="metric-label">Total Samples</div>
    </div>
    
    <h2>Field-Level Metrics</h2>
    <table>
        <tr>
            <th>Field</th>
            <th>Accuracy</th>
            <th>Extraction Rate</th>
            <th>Partial Match</th>
            <th>Extracted</th>
            <th>Correct</th>
            <th>Avg Confidence</th>
        </tr>
"""
        
        for name, m in result.field_metrics.items():
            acc_class = 'good' if m.accuracy >= 0.9 else ('medium' if m.accuracy >= 0.7 else 'poor')
            html += f"""        <tr>
            <td>{name}</td>
            <td class="{acc_class}">{m.accuracy*100:.1f}%</td>
            <td>{m.extraction_rate*100:.1f}%</td>
            <td>{m.partial_accuracy*100:.1f}%</td>
            <td>{m.extracted_count}/{m.total_samples}</td>
            <td>{m.correct_count}</td>
            <td>{m.avg_confidence:.2f}</td>
        </tr>
"""
        
        html += """    </table>
</body>
</html>"""
        
        return html
    
    def save_detailed_results(
        self,
        results: Union[List[ExtractionResult], List[Dict[str, Any]]],
        output_path: str,
        ground_truth: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Save detailed per-sample evaluation results.
        
        Args:
            results: Extraction results.
            output_path: Output file path.
            ground_truth: Optional ground truth data.
            
        Returns:
            Path to saved file.
        """
        detailed = []
        
        for idx, result in enumerate(results):
            if isinstance(result, ExtractionResult):
                result_dict = result.to_dict()
            else:
                result_dict = result
            
            # Get ground truth
            if ground_truth:
                gt = ground_truth[idx] if idx < len(ground_truth) else {}
            elif self.ground_truth:
                source_file = result_dict.get('source_file', '')
                gt = self.ground_truth.get_by_filename(source_file) or {}
            else:
                gt = {}
            
            # Evaluate this sample
            comparison = self.evaluate_single(result, gt)
            
            detailed.append({
                'sample_index': idx,
                'source_file': result_dict.get('source_file', ''),
                'extraction': result_dict,
                'ground_truth': gt,
                'comparison': comparison
            })
        
        # Save to file
        ensure_directory(Path(output_path).parent)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(detailed, f, indent=2, default=str)
        
        logger.info(f"Detailed results saved to: {output_path}")
        return output_path
