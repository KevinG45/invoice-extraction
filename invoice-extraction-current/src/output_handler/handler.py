"""
Main Output Handler Module.

This module provides the unified OutputHandler class that coordinates
all output operations (Excel and Database).

Author: ML Engineering Team
"""

from pathlib import Path
from typing import List, Optional, Dict, Any, Union

from config import get_config
from src.utils.logger import get_logger
from src.model_inference.extraction_result import ExtractionResult
from .excel_exporter import ExcelExporter
from .database_handler import DatabaseHandler
from .json_exporter import JSONExporter
from .dataframe_exporter import DataFrameExporter

# Initialize module logger
logger = get_logger(__name__)


class OutputHandler:
    """
    Unified output handler for extraction results.
    
    Coordinates output to multiple formats: Excel, Database, JSON, and DataFrame.
    Can be configured to use one or multiple output methods.
    
    Attributes:
        excel_enabled: Whether Excel export is enabled
        database_enabled: Whether database storage is enabled
        json_enabled: Whether JSON export is enabled
        dataframe_enabled: Whether DataFrame export is enabled
        excel_exporter: ExcelExporter instance
        database_handler: DatabaseHandler instance
        json_exporter: JSONExporter instance
        dataframe_exporter: DataFrameExporter instance
        
    Example:
        >>> handler = OutputHandler()
        >>> handler.save(results)  # Saves to all enabled formats
        >>> 
        >>> # Or save to specific outputs
        >>> handler.to_excel(results, "output.xlsx")
        >>> handler.to_json(results, "output.json")
        >>> handler.to_csv(results, "output.csv")
        >>> handler.to_database(results)
    """
    
    def __init__(
        self,
        excel_enabled: Optional[bool] = None,
        database_enabled: Optional[bool] = None,
        json_enabled: Optional[bool] = None,
        dataframe_enabled: Optional[bool] = None
    ) -> None:
        """
        Initialize the output handler.
        
        Args:
            excel_enabled: Override config for Excel output.
            database_enabled: Override config for database output.
            json_enabled: Override config for JSON output.
            dataframe_enabled: Override config for DataFrame output.
        """
        # Load configuration
        self.excel_enabled = excel_enabled if excel_enabled is not None else \
            get_config("output.excel.enabled", True)
        self.database_enabled = database_enabled if database_enabled is not None else \
            get_config("output.database.enabled", True)
        self.json_enabled = json_enabled if json_enabled is not None else \
            get_config("output.json.enabled", True)
        self.dataframe_enabled = dataframe_enabled if dataframe_enabled is not None else \
            get_config("output.dataframe.enabled", True)
        
        # Initialize exporters (lazy loading)
        self._excel_exporter = None
        self._database_handler = None
        self._json_exporter = None
        self._dataframe_exporter = None
        
        logger.info(
            f"OutputHandler initialized "
            f"(excel={self.excel_enabled}, database={self.database_enabled}, "
            f"json={self.json_enabled}, dataframe={self.dataframe_enabled})"
        )
    
    @property
    def excel_exporter(self) -> ExcelExporter:
        """Get or create the Excel exporter."""
        if self._excel_exporter is None:
            self._excel_exporter = ExcelExporter()
        return self._excel_exporter
    
    @property
    def database_handler(self) -> DatabaseHandler:
        """Get or create the database handler."""
        if self._database_handler is None:
            self._database_handler = DatabaseHandler()
        return self._database_handler
    
    @property
    def json_exporter(self) -> JSONExporter:
        """Get or create the JSON exporter."""
        if self._json_exporter is None:
            self._json_exporter = JSONExporter()
        return self._json_exporter
    
    @property
    def dataframe_exporter(self) -> DataFrameExporter:
        """Get or create the DataFrame exporter."""
        if self._dataframe_exporter is None:
            self._dataframe_exporter = DataFrameExporter()
        return self._dataframe_exporter
    
    def save(
        self,
        results: Union[ExtractionResult, List[ExtractionResult]],
        excel_filename: Optional[str] = None,
        json_filename: Optional[str] = None,
        csv_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Save results to all enabled outputs.
        
        Args:
            results: Single result or list of results.
            excel_filename: Custom Excel filename (optional).
            json_filename: Custom JSON filename (optional).
            csv_filename: Custom CSV filename (optional).
            
        Returns:
            Dictionary with output details:
            {
                'excel_path': 'path/to/file.xlsx',
                'database_records': {'inserted': 5, 'skipped': 0},
                'json_path': 'path/to/file.json',
                'csv_path': 'path/to/file.csv'
            }
            
        Example:
            >>> output_info = handler.save(results)
            >>> print(f"Excel: {output_info['excel_path']}")
            >>> print(f"JSON: {output_info['json_path']}")
            >>> print(f"CSV: {output_info['csv_path']}")
        """
        # Normalize to list
        if isinstance(results, ExtractionResult):
            results = [results]
        
        output_info = {
            'excel_path': None,
            'database_records': None,
            'json_path': None,
            'csv_path': None,
            'line_items_csv_path': None
        }
        
        # Export to Excel
        if self.excel_enabled:
            try:
                excel_path = self.to_excel(results, excel_filename)
                output_info['excel_path'] = excel_path
            except Exception as e:
                logger.error(f"Excel export failed: {e}")
        
        # Save to database
        if self.database_enabled:
            try:
                db_result = self.to_database(results)
                output_info['database_records'] = db_result
            except Exception as e:
                logger.error(f"Database save failed: {e}")
        
        # Export to JSON
        if self.json_enabled:
            try:
                json_path = self.to_json(results, json_filename)
                output_info['json_path'] = json_path
            except Exception as e:
                logger.error(f"JSON export failed: {e}")
        
        # Export to CSV (DataFrame)
        if self.dataframe_enabled:
            try:
                csv_path = self.to_csv(results, csv_filename)
                output_info['csv_path'] = csv_path
            except Exception as e:
                logger.error(f"CSV export failed: {e}")
            
            # Export line items CSV if any results have line items
            try:
                has_line_items = any(
                    getattr(r, 'line_items', None)
                    for r in results
                )
                if has_line_items:
                    li_csv = self.dataframe_exporter.line_items_to_csv(results)
                    output_info['line_items_csv_path'] = li_csv
            except Exception as e:
                logger.error(f"Line items CSV export failed: {e}")
        
        return output_info
    
    def to_excel(
        self,
        results: Union[ExtractionResult, List[ExtractionResult]],
        filename: Optional[str] = None,
        output_dir: Optional[str] = None
    ) -> str:
        """
        Export results to Excel file.
        
        Args:
            results: Results to export.
            filename: Output filename.
            output_dir: Output directory.
            
        Returns:
            Path to created Excel file.
        """
        if isinstance(results, ExtractionResult):
            results = [results]
        
        return self.excel_exporter.export(results, filename, output_dir)
    
    def to_database(
        self,
        results: Union[ExtractionResult, List[ExtractionResult]]
    ) -> Dict[str, int]:
        """
        Save results to database.
        
        Args:
            results: Results to save.
            
        Returns:
            Dictionary with 'inserted' and 'skipped' counts.
        """
        if isinstance(results, ExtractionResult):
            results = [results]
        
        return self.database_handler.insert_batch(results)
    
    def to_json(
        self,
        results: Union[ExtractionResult, List[ExtractionResult]],
        filename: Optional[str] = None,
        output_dir: Optional[str] = None
    ) -> str:
        """
        Export results to JSON file.
        
        Args:
            results: Results to export.
            filename: Output filename.
            output_dir: Output directory.
            
        Returns:
            Path to created JSON file.
        """
        if isinstance(results, ExtractionResult):
            results = [results]
        
        return self.json_exporter.export(results, filename, output_dir)
    
    def to_csv(
        self,
        results: Union[ExtractionResult, List[ExtractionResult]],
        filename: Optional[str] = None,
        output_dir: Optional[str] = None
    ) -> str:
        """
        Export results to CSV file.
        
        Args:
            results: Results to export.
            filename: Output filename.
            output_dir: Output directory.
            
        Returns:
            Path to created CSV file.
        """
        if isinstance(results, ExtractionResult):
            results = [results]
        
        return self.dataframe_exporter.to_csv(results, filename, output_dir)
    
    def to_dataframe(self, results: Union[ExtractionResult, List[ExtractionResult]]):
        """
        Convert results to pandas DataFrame.
        
        Args:
            results: Results to convert.
            
        Returns:
            pandas DataFrame with extraction results.
        """
        if isinstance(results, ExtractionResult):
            results = [results]
        
        return self.dataframe_exporter.to_dataframe(results)
    
    def to_parquet(
        self,
        results: Union[ExtractionResult, List[ExtractionResult]],
        filename: Optional[str] = None,
        output_dir: Optional[str] = None
    ) -> str:
        """
        Export results to Parquet file.
        
        Args:
            results: Results to export.
            filename: Output filename.
            output_dir: Output directory.
            
        Returns:
            Path to created Parquet file.
        """
        if isinstance(results, ExtractionResult):
            results = [results]
        
        return self.dataframe_exporter.to_parquet(results, filename, output_dir)
    
    def get_database_stats(self) -> Dict[str, Any]:
        """
        Get statistics from the database.
        
        Returns:
            Dictionary with database statistics.
        """
        return self.database_handler.get_statistics()
    
    def search_database(
        self,
        vendor_name: Optional[str] = None,
        invoice_number: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search the database for records.
        
        Args:
            vendor_name: Filter by vendor name.
            invoice_number: Filter by invoice number.
            date_from: Filter by date from.
            date_to: Filter by date to.
            
        Returns:
            List of matching records.
        """
        if invoice_number:
            result = self.database_handler.get_by_invoice_number(invoice_number)
            return [result] if result else []
        
        return self.database_handler.search(
            vendor_name=vendor_name,
            date_from=date_from,
            date_to=date_to
        )
    
    def get_all_records(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all records from the database.
        
        Args:
            limit: Maximum number of records.
            
        Returns:
            List of all records.
        """
        return self.database_handler.get_all(limit)
    
    def close(self) -> None:
        """Close all output handlers."""
        if self._database_handler:
            self._database_handler.close()
