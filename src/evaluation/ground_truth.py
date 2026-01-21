"""
Ground Truth Loader Module.

This module handles loading and managing ground truth data
for evaluation of invoice extraction results.

Supported Formats:
    - JSON files
    - CSV files
    - Excel files

Author: ML Engineering Team
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
import csv

from src.utils.logger import get_logger
from src.utils.exceptions import ConfigurationError

# Initialize module logger
logger = get_logger(__name__)


class GroundTruthLoader:
    """
    Loads ground truth data from various file formats.
    
    Supports JSON, CSV, and Excel formats for ground truth data.
    Provides methods for loading, validating, and accessing ground truth.
    
    Attributes:
        data: Loaded ground truth data
        file_path: Path to ground truth file
        
    Example:
        >>> loader = GroundTruthLoader("ground_truth.json")
        >>> gt_data = loader.get_all()
        >>> gt_for_file = loader.get_by_filename("invoice_001.pdf")
    """
    
    # Required fields in ground truth
    REQUIRED_FIELDS = [
        'invoice_number',
        'invoice_date',
        'vendor_name',
        'customer_name',
        'total_amount',
        'payment_due_date'
    ]
    
    def __init__(self, file_path: Optional[str] = None) -> None:
        """
        Initialize the ground truth loader.
        
        Args:
            file_path: Path to ground truth file. If None, creates empty loader.
        """
        self.file_path = Path(file_path) if file_path else None
        self.data: List[Dict[str, Any]] = []
        self._file_index: Dict[str, int] = {}
        
        if self.file_path:
            self.load(self.file_path)
    
    def load(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Load ground truth from file.
        
        Args:
            file_path: Path to ground truth file.
            
        Returns:
            List of ground truth records.
            
        Raises:
            FileNotFoundError: If file doesn't exist.
            ConfigurationError: If format is not supported.
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Ground truth file not found: {path}")
        
        extension = path.suffix.lower()
        
        if extension == '.json':
            self.data = self._load_json(path)
        elif extension == '.csv':
            self.data = self._load_csv(path)
        elif extension in ['.xlsx', '.xls']:
            self.data = self._load_excel(path)
        else:
            raise ConfigurationError(
                "ground_truth",
                f"Unsupported format: {extension}"
            )
        
        # Build index
        self._build_index()
        
        logger.info(f"Loaded {len(self.data)} ground truth records from {path.name}")
        return self.data
    
    def _load_json(self, path: Path) -> List[Dict[str, Any]]:
        """Load ground truth from JSON file."""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Handle both list and dict formats
        if isinstance(data, dict):
            # If dict, it might be keyed by filename
            if 'records' in data:
                return data['records']
            else:
                # Convert dict to list with filename as key
                return [
                    {**v, 'source_file': k}
                    for k, v in data.items()
                ]
        
        return data
    
    def _load_csv(self, path: Path) -> List[Dict[str, Any]]:
        """Load ground truth from CSV file."""
        data = []
        
        with open(path, 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append(dict(row))
        
        return data
    
    def _load_excel(self, path: Path) -> List[Dict[str, Any]]:
        """Load ground truth from Excel file."""
        try:
            import openpyxl
        except ImportError:
            raise ImportError(
                "openpyxl is required for Excel support. "
                "Install with: pip install openpyxl"
            )
        
        workbook = openpyxl.load_workbook(path, read_only=True)
        sheet = workbook.active
        
        data = []
        headers = None
        
        for row_idx, row in enumerate(sheet.iter_rows(values_only=True)):
            if row_idx == 0:
                # First row is headers
                headers = [str(cell).strip() if cell else f'col_{i}' 
                          for i, cell in enumerate(row)]
            else:
                record = {}
                for i, cell in enumerate(row):
                    if i < len(headers):
                        record[headers[i]] = cell
                data.append(record)
        
        workbook.close()
        return data
    
    def _build_index(self) -> None:
        """Build an index for faster lookups by filename."""
        self._file_index = {}
        
        for idx, record in enumerate(self.data):
            filename = record.get('source_file') or record.get('filename')
            if filename:
                # Store with normalized filename (without path)
                normalized = Path(filename).name
                self._file_index[normalized] = idx
                self._file_index[filename] = idx
    
    def get_all(self) -> List[Dict[str, Any]]:
        """
        Get all ground truth records.
        
        Returns:
            List of all ground truth records.
        """
        return self.data
    
    def get_by_index(self, index: int) -> Optional[Dict[str, Any]]:
        """
        Get ground truth record by index.
        
        Args:
            index: Record index.
            
        Returns:
            Ground truth record or None.
        """
        if 0 <= index < len(self.data):
            return self.data[index]
        return None
    
    def get_by_filename(self, filename: str) -> Optional[Dict[str, Any]]:
        """
        Get ground truth record by source filename.
        
        Args:
            filename: Source file name (with or without path).
            
        Returns:
            Ground truth record or None.
        """
        # Try exact match first
        if filename in self._file_index:
            return self.data[self._file_index[filename]]
        
        # Try normalized filename
        normalized = Path(filename).name
        if normalized in self._file_index:
            return self.data[self._file_index[normalized]]
        
        return None
    
    def validate(self) -> Dict[str, Any]:
        """
        Validate the loaded ground truth data.
        
        Returns:
            Dictionary with validation results.
        """
        results = {
            'total_records': len(self.data),
            'valid_records': 0,
            'invalid_records': 0,
            'missing_fields': {},
            'errors': []
        }
        
        for idx, record in enumerate(self.data):
            is_valid = True
            
            for field in self.REQUIRED_FIELDS:
                if field not in record or not record[field]:
                    is_valid = False
                    if field not in results['missing_fields']:
                        results['missing_fields'][field] = 0
                    results['missing_fields'][field] += 1
            
            if is_valid:
                results['valid_records'] += 1
            else:
                results['invalid_records'] += 1
        
        logger.info(
            f"Ground truth validation: {results['valid_records']}/{results['total_records']} valid"
        )
        
        return results
    
    def __len__(self) -> int:
        """Return number of ground truth records."""
        return len(self.data)
    
    def __iter__(self):
        """Iterate over ground truth records."""
        return iter(self.data)
    
    def __getitem__(self, index: int) -> Dict[str, Any]:
        """Get record by index."""
        return self.data[index]


def create_sample_ground_truth(output_path: str) -> str:
    """
    Create a sample ground truth file for reference.
    
    Args:
        output_path: Path for the sample file.
        
    Returns:
        Path to created file.
    """
    sample_data = {
        "records": [
            {
                "source_file": "invoice_001.pdf",
                "invoice_number": "INV-2024-001",
                "invoice_date": "2024-01-15",
                "vendor_name": "Acme Corporation",
                "customer_name": "XYZ Industries",
                "total_amount": "1250.00",
                "payment_due_date": "2024-02-15"
            },
            {
                "source_file": "invoice_002.pdf",
                "invoice_number": "INV-2024-002",
                "invoice_date": "2024-01-20",
                "vendor_name": "Best Supplies Inc.",
                "customer_name": "ABC Company",
                "total_amount": "3500.50",
                "payment_due_date": "2024-02-20"
            }
        ]
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(sample_data, f, indent=2)
    
    logger.info(f"Created sample ground truth file: {output_path}")
    return output_path
