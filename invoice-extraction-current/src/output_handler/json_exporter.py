"""
JSON Exporter Module.

This module provides JSON file generation for invoice extraction results.
Supports both single-file and batch export with pretty-printing options.

Features:
    - Individual JSON files per invoice
    - Batch JSON array export
    - Pretty-printed formatting
    - Metadata inclusion
    - Timestamped filenames

Author: ML Engineering Team
"""

import json
from pathlib import Path
from typing import List, Optional, Union, Dict, Any
from datetime import datetime

from config import get_config
from src.utils.logger import get_logger
from src.utils.helpers import ensure_directory, generate_timestamp
from src.utils.exceptions import ExportError
from src.model_inference.extraction_result import ExtractionResult

# Initialize module logger
logger = get_logger(__name__)


class JSONExporter:
    """
    Exports extraction results to JSON format.
    
    Creates JSON files with extraction results in structured format,
    suitable for API integration and data interchange.
    
    Attributes:
        output_dir: Directory for output files
        pretty_print: Whether to format JSON with indentation
        indent: Number of spaces for indentation
        include_metadata: Whether to include processing metadata
        
    Example:
        >>> exporter = JSONExporter()
        >>> filepath = exporter.export(results, "extractions.json")
        >>> print(f"Saved to: {filepath}")
        
        >>> # Export individual files
        >>> paths = exporter.export_individual(results)
        >>> print(f"Created {len(paths)} files")
    """
    
    def __init__(self) -> None:
        """Initialize the JSON exporter with configuration."""
        self.output_dir = Path(get_config("paths.output_dir", "outputs")) / "extractions"
        self.pretty_print = get_config("output.json.pretty_print", True)
        self.indent = get_config("output.json.indent", 2)
        self.include_metadata = get_config("output.json.include_metadata", True)
        self.include_confidence = get_config("output.json.include_confidence", True)
        
        logger.debug(f"JSONExporter initialized (output_dir: {self.output_dir})")
    
    def export(
        self,
        results: Union[ExtractionResult, List[ExtractionResult]],
        filename: Optional[str] = None,
        output_dir: Optional[str] = None
    ) -> str:
        """
        Export extraction results to a single JSON file.
        
        Args:
            results: Single result or list of results to export.
            filename: Output filename. If None, auto-generated.
            output_dir: Output directory. If None, uses configured dir.
            
        Returns:
            Path to the created JSON file.
            
        Raises:
            ExportError: If export fails.
            
        Example:
            >>> path = exporter.export(results, "invoice_data.json")
        """
        # Normalize to list
        if isinstance(results, ExtractionResult):
            results = [results]
        
        if not results:
            raise ExportError("No results", "No results to export")
        
        # Determine output path
        if output_dir:
            out_dir = Path(output_dir)
        else:
            out_dir = self.output_dir
        
        ensure_directory(out_dir)
        
        if filename is None:
            timestamp = generate_timestamp()
            filename = f"invoice_extractions_{timestamp}.json"
        
        filepath = out_dir / filename
        
        try:
            # Convert results to dictionaries
            data = {
                "metadata": {
                    "export_timestamp": datetime.now().isoformat(),
                    "record_count": len(results),
                    "system_version": "1.0.0"
                } if self.include_metadata else None,
                "extractions": [self._result_to_dict(r) for r in results]
            }
            
            # Remove None metadata if not included
            if not self.include_metadata:
                del data["metadata"]
            
            # Write JSON file
            with open(filepath, 'w', encoding='utf-8') as f:
                if self.pretty_print:
                    json.dump(data, f, indent=self.indent, ensure_ascii=False)
                else:
                    json.dump(data, f, ensure_ascii=False)
            
            logger.info(f"JSON file saved: {filepath} ({len(results)} records)")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"JSON export failed: {e}")
            raise ExportError(str(filepath), str(e))
    
    def export_individual(
        self,
        results: List[ExtractionResult],
        output_dir: Optional[str] = None,
        filename_template: Optional[str] = None
    ) -> List[str]:
        """
        Export each result to an individual JSON file.
        
        Useful for processing systems that expect one file per invoice.
        
        Args:
            results: List of extraction results.
            output_dir: Output directory. If None, uses configured dir.
            filename_template: Template for filenames. Use {invoice_number}, 
                             {timestamp}, {index}. Default: "invoice_{invoice_number}.json"
            
        Returns:
            List of paths to created files.
            
        Example:
            >>> paths = exporter.export_individual(
            ...     results,
            ...     filename_template="inv_{invoice_number}_{timestamp}.json"
            ... )
        """
        if not results:
            raise ExportError("No results", "No results to export")
        
        # Determine output path
        if output_dir:
            out_dir = Path(output_dir)
        else:
            out_dir = self.output_dir
        
        ensure_directory(out_dir)
        
        if filename_template is None:
            filename_template = "invoice_{invoice_number}_{index}.json"
        
        created_files = []
        timestamp = generate_timestamp()
        
        for idx, result in enumerate(results):
            try:
                # Generate filename
                invoice_num = result.invoice_number or "unknown"
                # Clean invoice number for filename
                invoice_num = self._sanitize_filename(invoice_num)
                
                filename = filename_template.format(
                    invoice_number=invoice_num,
                    timestamp=timestamp,
                    index=idx + 1
                )
                
                filepath = out_dir / filename
                
                # Convert to dict
                data = self._result_to_dict(result)
                
                # Write file
                with open(filepath, 'w', encoding='utf-8') as f:
                    if self.pretty_print:
                        json.dump(data, f, indent=self.indent, ensure_ascii=False)
                    else:
                        json.dump(data, f, ensure_ascii=False)
                
                created_files.append(str(filepath))
                
            except Exception as e:
                logger.warning(f"Failed to export result {idx}: {e}")
                continue
        
        logger.info(f"Created {len(created_files)} individual JSON files in {out_dir}")
        return created_files
    
    def export_batch_array(
        self,
        results: List[ExtractionResult],
        filename: Optional[str] = None,
        output_dir: Optional[str] = None
    ) -> str:
        """
        Export results as a simple JSON array (no metadata wrapper).
        
        Args:
            results: List of extraction results.
            filename: Output filename.
            output_dir: Output directory.
            
        Returns:
            Path to created JSON file.
        """
        if not results:
            raise ExportError("No results", "No results to export")
        
        # Determine output path
        if output_dir:
            out_dir = Path(output_dir)
        else:
            out_dir = self.output_dir
        
        ensure_directory(out_dir)
        
        if filename is None:
            timestamp = generate_timestamp()
            filename = f"invoice_array_{timestamp}.json"
        
        filepath = out_dir / filename
        
        try:
            # Convert results to list of dictionaries
            data = [self._result_to_dict(r) for r in results]
            
            # Write JSON file
            with open(filepath, 'w', encoding='utf-8') as f:
                if self.pretty_print:
                    json.dump(data, f, indent=self.indent, ensure_ascii=False)
                else:
                    json.dump(data, f, ensure_ascii=False)
            
            logger.info(f"JSON array saved: {filepath} ({len(results)} records)")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"JSON array export failed: {e}")
            raise ExportError(str(filepath), str(e))
    
    def _result_to_dict(self, result: ExtractionResult) -> Dict[str, Any]:
        """
        Convert ExtractionResult to dictionary for JSON export.
        
        Args:
            result: ExtractionResult to convert.
            
        Returns:
            Dictionary representation.
        """
        data = {
            "invoice_number": result.invoice_number,
            "invoice_date": result.invoice_date,
            "vendor_name": result.vendor_name,
            "customer_name": result.customer_name,
            "total_amount": result.total_amount,
            "payment_due_date": result.payment_due_date,
        }
        
        # Add line items if present (HybridExtractionResult)
        line_items = getattr(result, 'line_items', [])
        if line_items:
            data["line_items"] = [item.to_dict() for item in line_items]
            data["line_items_count"] = len(line_items)
            line_total = getattr(result, 'line_items_total', None)
            data["line_items_total"] = float(line_total) if line_total is not None else None
        
        # Add confidence scores if enabled
        if self.include_confidence:
            data["confidence_scores"] = result.confidence_scores
        
        # Add metadata if enabled
        if self.include_metadata:
            data["metadata"] = {
                "source_file": result.source_file,
                "extraction_timestamp": result.extraction_timestamp,
                "model_name": result.model_name,
                "processing_time": result.processing_time,
                "success": result.success,
                "extraction_rate": result.extraction_rate,
                "average_confidence": result.average_confidence
            }
            
            # Add total validation if present
            total_validation = getattr(result, 'total_validation', None)
            if total_validation:
                data["metadata"]["total_validation"] = total_validation
            
            # Add warnings and errors if present
            if result.warnings:
                data["metadata"]["warnings"] = result.warnings
            if result.errors:
                data["metadata"]["errors"] = result.errors
        
        return data
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize string for use in filename.
        
        Args:
            filename: String to sanitize.
            
        Returns:
            Sanitized string.
        """
        # Replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # Limit length
        if len(filename) > 50:
            filename = filename[:50]
        
        return filename
    
    def to_json_string(
        self,
        results: Union[ExtractionResult, List[ExtractionResult]]
    ) -> str:
        """
        Convert results to JSON string (without saving to file).
        
        Args:
            results: Single result or list of results.
            
        Returns:
            JSON string.
        """
        if isinstance(results, ExtractionResult):
            results = [results]
        
        data = [self._result_to_dict(r) for r in results]
        
        if self.pretty_print:
            return json.dumps(data, indent=self.indent, ensure_ascii=False)
        else:
            return json.dumps(data, ensure_ascii=False)
