"""
DataFrame Exporter Module.

This module provides pandas DataFrame generation and export for invoice
extraction results. Supports multiple output formats (CSV, Parquet, Pickle).

Features:
    - Convert results to pandas DataFrame
    - Export to CSV, Parquet, or Pickle
    - Column selection and ordering
    - Data type optimization
    - Timestamp indexing

Author: ML Engineering Team
"""

from pathlib import Path
from typing import List, Optional, Union, Dict, Any
import pandas as pd
from datetime import datetime

from config import get_config
from src.utils.logger import get_logger
from src.utils.helpers import ensure_directory, generate_timestamp
from src.utils.exceptions import ExportError
from src.model_inference.extraction_result import ExtractionResult

# Initialize module logger
logger = get_logger(__name__)


class DataFrameExporter:
    """
    Exports extraction results to pandas DataFrame and various formats.
    
    Creates DataFrames from extraction results with proper data types
    and supports multiple export formats for data science workflows.
    
    Attributes:
        output_dir: Directory for output files
        include_metadata: Whether to include metadata columns
        include_confidence: Whether to include confidence columns
        
    Example:
        >>> exporter = DataFrameExporter()
        >>> df = exporter.to_dataframe(results)
        >>> print(df.head())
        
        >>> # Save to CSV
        >>> path = exporter.to_csv(results, "extractions.csv")
        
        >>> # Save to Parquet
        >>> path = exporter.to_parquet(results, "extractions.parquet")
    """
    
    # Column order for DataFrame
    CORE_COLUMNS = [
        'invoice_number',
        'invoice_date',
        'vendor_name',
        'customer_name',
        'total_amount',
        'payment_due_date'
    ]
    
    METADATA_COLUMNS = [
        'source_file',
        'extraction_timestamp',
        'model_name',
        'processing_time',
        'success',
        'extraction_rate',
        'average_confidence',
        'line_items_count',
        'line_items_total'
    ]
    
    CONFIDENCE_COLUMNS = [
        'invoice_number_confidence',
        'invoice_date_confidence',
        'vendor_name_confidence',
        'customer_name_confidence',
        'total_amount_confidence',
        'payment_due_date_confidence'
    ]
    
    def __init__(self) -> None:
        """Initialize the DataFrame exporter with configuration."""
        self.output_dir = Path(get_config("paths.output_dir", "outputs")) / "extractions"
        self.include_metadata = get_config("output.dataframe.include_metadata", True)
        self.include_confidence = get_config("output.dataframe.include_confidence", True)
        self.optimize_dtypes = get_config("output.dataframe.optimize_dtypes", True)
        
        logger.debug(f"DataFrameExporter initialized (output_dir: {self.output_dir})")
    
    def to_dataframe(
        self,
        results: Union[ExtractionResult, List[ExtractionResult]],
        include_metadata: Optional[bool] = None,
        include_confidence: Optional[bool] = None
    ) -> pd.DataFrame:
        """
        Convert extraction results to pandas DataFrame.
        
        Args:
            results: Single result or list of results.
            include_metadata: Override config for metadata columns.
            include_confidence: Override config for confidence columns.
            
        Returns:
            pandas DataFrame with extraction results.
            
        Example:
            >>> df = exporter.to_dataframe(results)
            >>> print(df.shape)
            (10, 12)
        """
        # Normalize to list
        if isinstance(results, ExtractionResult):
            results = [results]
        
        if not results:
            # Return empty DataFrame with correct columns
            return self._create_empty_dataframe()
        
        # Override settings if provided
        incl_metadata = include_metadata if include_metadata is not None else self.include_metadata
        incl_confidence = include_confidence if include_confidence is not None else self.include_confidence
        
        # Convert results to list of dictionaries
        data_dicts = []
        for result in results:
            row = self._result_to_row(result, incl_metadata, incl_confidence)
            data_dicts.append(row)
        
        # Create DataFrame
        df = pd.DataFrame(data_dicts)
        
        # Reorder columns
        columns = self._get_column_order(incl_metadata, incl_confidence)
        # Only include columns that exist in the DataFrame
        columns = [col for col in columns if col in df.columns]
        df = df[columns]
        
        # Optimize data types if enabled
        if self.optimize_dtypes:
            df = self._optimize_dtypes(df)
        
        logger.debug(f"Created DataFrame with shape {df.shape}")
        return df
    
    def to_csv(
        self,
        results: Union[ExtractionResult, List[ExtractionResult]],
        filename: Optional[str] = None,
        output_dir: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Export results to CSV file.
        
        Args:
            results: Single result or list of results.
            filename: Output filename. If None, auto-generated.
            output_dir: Output directory. If None, uses configured dir.
            **kwargs: Additional arguments passed to pandas.to_csv()
            
        Returns:
            Path to the created CSV file.
            
        Example:
            >>> path = exporter.to_csv(results, "data.csv", index=False)
        """
        # Get DataFrame
        df = self.to_dataframe(results)
        
        # Determine output path
        if output_dir:
            out_dir = Path(output_dir)
        else:
            out_dir = self.output_dir
        
        ensure_directory(out_dir)
        
        if filename is None:
            timestamp = generate_timestamp()
            filename = f"invoice_extractions_{timestamp}.csv"
        
        filepath = out_dir / filename
        
        try:
            # Default parameters
            csv_params = {
                'index': False,
                'encoding': 'utf-8-sig',  # BOM for Excel compatibility
            }
            csv_params.update(kwargs)
            
            # Write CSV
            df.to_csv(filepath, **csv_params)
            
            logger.info(f"CSV file saved: {filepath} ({len(df)} records)")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"CSV export failed: {e}")
            raise ExportError(str(filepath), str(e))
    
    def to_parquet(
        self,
        results: Union[ExtractionResult, List[ExtractionResult]],
        filename: Optional[str] = None,
        output_dir: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Export results to Parquet file.
        
        Parquet is a columnar storage format optimized for big data.
        Requires pyarrow or fastparquet package.
        
        Args:
            results: Single result or list of results.
            filename: Output filename. If None, auto-generated.
            output_dir: Output directory. If None, uses configured dir.
            **kwargs: Additional arguments passed to pandas.to_parquet()
            
        Returns:
            Path to the created Parquet file.
            
        Example:
            >>> path = exporter.to_parquet(results, "data.parquet")
        """
        # Get DataFrame
        df = self.to_dataframe(results)
        
        # Determine output path
        if output_dir:
            out_dir = Path(output_dir)
        else:
            out_dir = self.output_dir
        
        ensure_directory(out_dir)
        
        if filename is None:
            timestamp = generate_timestamp()
            filename = f"invoice_extractions_{timestamp}.parquet"
        
        filepath = out_dir / filename
        
        try:
            # Default parameters
            parquet_params = {
                'index': False,
                'compression': 'snappy'
            }
            parquet_params.update(kwargs)
            
            # Write Parquet
            df.to_parquet(filepath, **parquet_params)
            
            logger.info(f"Parquet file saved: {filepath} ({len(df)} records)")
            return str(filepath)
            
        except ImportError:
            logger.error("Parquet export requires pyarrow or fastparquet package")
            raise ExportError(
                str(filepath),
                "Install with: pip install pyarrow"
            )
        except Exception as e:
            logger.error(f"Parquet export failed: {e}")
            raise ExportError(str(filepath), str(e))
    
    def to_pickle(
        self,
        results: Union[ExtractionResult, List[ExtractionResult]],
        filename: Optional[str] = None,
        output_dir: Optional[str] = None
    ) -> str:
        """
        Export results to Pickle file.
        
        Pickle preserves all DataFrame properties including data types.
        Warning: Only unpickle files from trusted sources.
        
        Args:
            results: Single result or list of results.
            filename: Output filename. If None, auto-generated.
            output_dir: Output directory. If None, uses configured dir.
            
        Returns:
            Path to the created Pickle file.
        """
        # Get DataFrame
        df = self.to_dataframe(results)
        
        # Determine output path
        if output_dir:
            out_dir = Path(output_dir)
        else:
            out_dir = self.output_dir
        
        ensure_directory(out_dir)
        
        if filename is None:
            timestamp = generate_timestamp()
            filename = f"invoice_extractions_{timestamp}.pkl"
        
        filepath = out_dir / filename
        
        try:
            # Write Pickle
            df.to_pickle(filepath)
            
            logger.info(f"Pickle file saved: {filepath} ({len(df)} records)")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Pickle export failed: {e}")
            raise ExportError(str(filepath), str(e))
    
    def to_excel(
        self,
        results: Union[ExtractionResult, List[ExtractionResult]],
        filename: Optional[str] = None,
        output_dir: Optional[str] = None,
        sheet_name: str = "Extractions",
        **kwargs
    ) -> str:
        """
        Export DataFrame to Excel file.
        
        Alternative to ExcelExporter with simpler formatting.
        
        Args:
            results: Single result or list of results.
            filename: Output filename. If None, auto-generated.
            output_dir: Output directory. If None, uses configured dir.
            sheet_name: Name of the worksheet.
            **kwargs: Additional arguments passed to pandas.to_excel()
            
        Returns:
            Path to the created Excel file.
        """
        # Get DataFrame
        df = self.to_dataframe(results)
        
        # Determine output path
        if output_dir:
            out_dir = Path(output_dir)
        else:
            out_dir = self.output_dir
        
        ensure_directory(out_dir)
        
        if filename is None:
            timestamp = generate_timestamp()
            filename = f"invoice_extractions_{timestamp}.xlsx"
        
        filepath = out_dir / filename
        
        try:
            # Default parameters
            excel_params = {
                'index': False,
                'sheet_name': sheet_name,
                'engine': 'openpyxl'
            }
            excel_params.update(kwargs)
            
            # Write Excel
            df.to_excel(filepath, **excel_params)
            
            logger.info(f"Excel file saved: {filepath} ({len(df)} records)")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Excel export failed: {e}")
            raise ExportError(str(filepath), str(e))
    
    def _result_to_row(
        self,
        result: ExtractionResult,
        include_metadata: bool,
        include_confidence: bool
    ) -> Dict[str, Any]:
        """
        Convert ExtractionResult to dictionary row for DataFrame.
        
        Args:
            result: ExtractionResult to convert.
            include_metadata: Include metadata columns.
            include_confidence: Include confidence columns.
            
        Returns:
            Dictionary representation for DataFrame row.
        """
        # Core fields
        row = {
            'invoice_number': result.invoice_number,
            'invoice_date': result.invoice_date,
            'vendor_name': result.vendor_name,
            'customer_name': result.customer_name,
            'total_amount': result.total_amount,
            'payment_due_date': result.payment_due_date,
        }
        
        # Metadata fields
        if include_metadata:
            line_items_count = getattr(result, 'line_items_count', 0)
            line_items_total = getattr(result, 'line_items_total', None)
            row.update({
                'source_file': result.source_file,
                'extraction_timestamp': result.extraction_timestamp,
                'model_name': result.model_name,
                'processing_time': result.processing_time,
                'success': result.success,
                'extraction_rate': result.extraction_rate,
                'average_confidence': result.average_confidence,
                'line_items_count': line_items_count,
                'line_items_total': float(line_items_total) if line_items_total is not None else None
            })
        
        # Confidence scores
        if include_confidence:
            for field in self.CORE_COLUMNS:
                row[f'{field}_confidence'] = result.confidence_scores.get(field, 0.0)
        
        return row
    
    def _get_column_order(
        self,
        include_metadata: bool,
        include_confidence: bool
    ) -> List[str]:
        """
        Get the desired column order for DataFrame.
        
        Args:
            include_metadata: Include metadata columns.
            include_confidence: Include confidence columns.
            
        Returns:
            List of column names in order.
        """
        columns = self.CORE_COLUMNS.copy()
        
        if include_metadata:
            columns.extend(self.METADATA_COLUMNS)
        
        if include_confidence:
            columns.extend(self.CONFIDENCE_COLUMNS)
        
        return columns
    
    def _optimize_dtypes(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Optimize DataFrame data types for memory efficiency.
        
        Args:
            df: DataFrame to optimize.
            
        Returns:
            Optimized DataFrame.
        """
        # Convert date strings to datetime
        date_columns = ['invoice_date', 'payment_due_date', 'extraction_timestamp']
        for col in date_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        # Convert amount to float
        if 'total_amount' in df.columns:
            df['total_amount'] = pd.to_numeric(df['total_amount'], errors='coerce')
        
        # Convert boolean
        if 'success' in df.columns:
            df['success'] = df['success'].astype(bool)
        
        # Convert confidence scores to float32
        confidence_cols = [col for col in df.columns if col.endswith('_confidence')]
        for col in confidence_cols:
            df[col] = df[col].astype('float32')
        
        # Convert rates to float32
        rate_cols = ['extraction_rate', 'average_confidence', 'processing_time']
        for col in rate_cols:
            if col in df.columns:
                df[col] = df[col].astype('float32')
        
        return df
    
    def _create_empty_dataframe(self) -> pd.DataFrame:
        """
        Create an empty DataFrame with correct columns.
        
        Returns:
            Empty DataFrame with proper structure.
        """
        columns = self._get_column_order(self.include_metadata, self.include_confidence)
        return pd.DataFrame(columns=columns)
    
    def get_summary_statistics(
        self,
        results: Union[ExtractionResult, List[ExtractionResult]]
    ) -> pd.DataFrame:
        """
        Get summary statistics for extraction results.
        
        Args:
            results: Single result or list of results.
            
        Returns:
            DataFrame with summary statistics.
            
        Example:
            >>> stats = exporter.get_summary_statistics(results)
            >>> print(stats)
        """
        df = self.to_dataframe(results)
        
        # Numeric columns for statistics
        numeric_cols = [
            'total_amount',
            'processing_time',
            'extraction_rate',
            'average_confidence',
            'line_items_count',
            'line_items_total'
        ]
        numeric_cols = [col for col in numeric_cols if col in df.columns]
        
        if numeric_cols:
            stats = df[numeric_cols].describe()
            return stats
        else:
            return pd.DataFrame()
    
    def line_items_to_dataframe(
        self,
        results: Union[ExtractionResult, List[ExtractionResult]]
    ) -> pd.DataFrame:
        """
        Convert line items from results into a flat DataFrame.
        
        Each row is a single line item with its parent invoice reference.
        
        Args:
            results: Single result or list of results.
            
        Returns:
            pandas DataFrame of line items.
        """
        if isinstance(results, ExtractionResult):
            results = [results]
        
        rows = []
        for result in results:
            items = getattr(result, 'line_items', [])
            invoice_id = result.invoice_number or result.source_file or 'Unknown'
            for item in items:
                row = item.to_dict()
                row['invoice_number'] = invoice_id
                rows.append(row)
        
        if not rows:
            return pd.DataFrame(columns=[
                'invoice_number', 'row_index', 'item_code', 'description',
                'quantity', 'unit', 'unit_price', 'total',
                'tax_rate', 'tax_amount', 'discount', 'confidence'
            ])
        
        df = pd.DataFrame(rows)
        
        # Reorder so invoice_number is first
        cols = ['invoice_number'] + [c for c in df.columns if c != 'invoice_number']
        df = df[cols]
        
        logger.debug(f"Created line items DataFrame with shape {df.shape}")
        return df
    
    def line_items_to_csv(
        self,
        results: Union[ExtractionResult, List[ExtractionResult]],
        filename: Optional[str] = None,
        output_dir: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Export line items to a separate CSV file.
        
        Args:
            results: Single result or list of results.
            filename: Output filename. If None, auto-generated.
            output_dir: Output directory. If None, uses configured dir.
            
        Returns:
            Path to created CSV file.
        """
        df = self.line_items_to_dataframe(results)
        
        if output_dir:
            out_dir = Path(output_dir)
        else:
            out_dir = self.output_dir
        
        ensure_directory(out_dir)
        
        if filename is None:
            timestamp = generate_timestamp()
            filename = f"invoice_line_items_{timestamp}.csv"
        
        filepath = out_dir / filename
        
        try:
            csv_params = {
                'index': False,
                'encoding': 'utf-8-sig',
            }
            csv_params.update(kwargs)
            df.to_csv(filepath, **csv_params)
            
            logger.info(f"Line items CSV saved: {filepath} ({len(df)} rows)")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Line items CSV export failed: {e}")
            raise ExportError(str(filepath), str(e))
