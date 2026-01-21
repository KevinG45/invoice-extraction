"""
Database Handler Module.

This module provides database storage for invoice extraction results.
Uses SQLite by default, with SQLAlchemy for ORM support.

Features:
    - Automatic schema creation
    - Duplicate detection
    - Transaction support
    - Query helpers

Author: ML Engineering Team
"""

import os
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
from datetime import datetime

from config import get_config
from src.utils.logger import get_logger
from src.utils.helpers import ensure_directory
from src.utils.exceptions import DatabaseError
from src.model_inference.extraction_result import ExtractionResult

# Initialize module logger
logger = get_logger(__name__)


class DatabaseHandler:
    """
    Handles database operations for invoice extraction results.
    
    Provides methods for storing, retrieving, and querying extraction
    results in a SQLite database.
    
    Attributes:
        db_path: Path to the SQLite database file
        table_name: Name of the main table
        engine: SQLAlchemy engine instance
        
    Example:
        >>> db = DatabaseHandler()
        >>> db.insert(extraction_result)
        >>> all_invoices = db.get_all()
    """
    
    def __init__(self, db_path: Optional[str] = None) -> None:
        """
        Initialize the database handler.
        
        Args:
            db_path: Path to database file. If None, uses configuration.
        """
        # Load configuration
        if db_path:
            self.db_path = Path(db_path)
        else:
            output_dir = Path(get_config("paths.output_dir", "outputs"))
            db_name = get_config("output.database.name", "invoice_extractions.db")
            self.db_path = output_dir / db_name
        
        self.table_name = get_config("output.database.table_name", "invoice_headers")
        self.avoid_duplicates = get_config("output.database.avoid_duplicates", True)
        self.create_if_not_exists = get_config("output.database.create_if_not_exists", True)
        
        # Ensure directory exists
        ensure_directory(self.db_path.parent)
        
        # Check dependencies and initialize
        self._check_dependencies()
        self._initialize_database()
        
        logger.info(f"DatabaseHandler initialized (db: {self.db_path})")
    
    def _check_dependencies(self) -> None:
        """Check if required libraries are available."""
        try:
            import sqlite3
            self._sqlite3 = sqlite3
        except ImportError:
            raise ImportError("sqlite3 is required for database operations")
        
        # SQLAlchemy is optional but preferred
        try:
            import sqlalchemy
            self._sqlalchemy = sqlalchemy
            self._use_sqlalchemy = True
        except ImportError:
            logger.debug("SQLAlchemy not available, using raw sqlite3")
            self._sqlalchemy = None
            self._use_sqlalchemy = False
    
    def _initialize_database(self) -> None:
        """Create database and tables if they don't exist."""
        if not self.create_if_not_exists and not self.db_path.exists():
            raise DatabaseError(
                "create",
                f"Database does not exist: {self.db_path}"
            )
        
        # Create tables
        self._create_tables()
    
    def _create_tables(self) -> None:
        """Create the required database tables."""
        create_sql = f"""
        CREATE TABLE IF NOT EXISTS {self.table_name} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT,
            invoice_date TEXT,
            vendor_name TEXT,
            customer_name TEXT,
            total_amount TEXT,
            payment_due_date TEXT,
            source_file TEXT,
            extraction_timestamp TEXT,
            model_name TEXT,
            processing_time REAL,
            success INTEGER,
            extraction_rate REAL,
            average_confidence REAL,
            invoice_number_confidence REAL,
            invoice_date_confidence REAL,
            vendor_name_confidence REAL,
            customer_name_confidence REAL,
            total_amount_confidence REAL,
            payment_due_date_confidence REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(invoice_number, vendor_name) ON CONFLICT IGNORE
        )
        """
        
        try:
            conn = self._sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(create_sql)
            
            # Create index for faster lookups
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_invoice_number 
                ON {self.table_name} (invoice_number)
            """)
            
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_vendor_name 
                ON {self.table_name} (vendor_name)
            """)
            
            conn.commit()
            conn.close()
            
            logger.debug(f"Database tables created/verified")
            
        except Exception as e:
            raise DatabaseError("create tables", str(e))
    
    def insert(self, result: ExtractionResult) -> bool:
        """
        Insert a single extraction result into the database.
        
        Args:
            result: ExtractionResult to insert.
            
        Returns:
            True if inserted successfully, False if duplicate.
            
        Raises:
            DatabaseError: If insertion fails.
        """
        # Check for duplicates if enabled
        if self.avoid_duplicates and result.invoice_number:
            if self.exists(result.invoice_number, result.vendor_name):
                logger.debug(
                    f"Duplicate detected, skipping: {result.invoice_number}"
                )
                return False
        
        insert_sql = f"""
        INSERT INTO {self.table_name} (
            invoice_number, invoice_date, vendor_name, customer_name,
            total_amount, payment_due_date, source_file, extraction_timestamp,
            model_name, processing_time, success, extraction_rate,
            average_confidence, invoice_number_confidence, invoice_date_confidence,
            vendor_name_confidence, customer_name_confidence,
            total_amount_confidence, payment_due_date_confidence
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        values = (
            result.invoice_number or '',
            result.invoice_date or '',
            result.vendor_name or '',
            result.customer_name or '',
            result.total_amount or '',
            result.payment_due_date or '',
            result.source_file or '',
            result.extraction_timestamp or datetime.now().isoformat(),
            result.model_name or '',
            result.processing_time,
            1 if result.success else 0,
            result.extraction_rate,
            result.average_confidence,
            result.confidence_scores.get('invoice_number', 0),
            result.confidence_scores.get('invoice_date', 0),
            result.confidence_scores.get('vendor_name', 0),
            result.confidence_scores.get('customer_name', 0),
            result.confidence_scores.get('total_amount', 0),
            result.confidence_scores.get('payment_due_date', 0),
        )
        
        try:
            conn = self._sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(insert_sql, values)
            conn.commit()
            conn.close()
            
            logger.debug(f"Inserted record: {result.invoice_number}")
            return True
            
        except self._sqlite3.IntegrityError:
            logger.debug(f"Duplicate record ignored: {result.invoice_number}")
            return False
            
        except Exception as e:
            raise DatabaseError("insert", str(e))
    
    def insert_batch(self, results: List[ExtractionResult]) -> Dict[str, int]:
        """
        Insert multiple extraction results.
        
        Args:
            results: List of ExtractionResult objects.
            
        Returns:
            Dictionary with 'inserted' and 'skipped' counts.
        """
        inserted = 0
        skipped = 0
        
        for result in results:
            if self.insert(result):
                inserted += 1
            else:
                skipped += 1
        
        logger.info(f"Batch insert complete: {inserted} inserted, {skipped} skipped")
        return {'inserted': inserted, 'skipped': skipped}
    
    def exists(
        self,
        invoice_number: str,
        vendor_name: Optional[str] = None
    ) -> bool:
        """
        Check if a record with the given invoice number exists.
        
        Args:
            invoice_number: Invoice number to check.
            vendor_name: Optional vendor name for more specific check.
            
        Returns:
            True if record exists, False otherwise.
        """
        if vendor_name:
            query = f"""
            SELECT COUNT(*) FROM {self.table_name}
            WHERE invoice_number = ? AND vendor_name = ?
            """
            params = (invoice_number, vendor_name)
        else:
            query = f"""
            SELECT COUNT(*) FROM {self.table_name}
            WHERE invoice_number = ?
            """
            params = (invoice_number,)
        
        try:
            conn = self._sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(query, params)
            count = cursor.fetchone()[0]
            conn.close()
            
            return count > 0
            
        except Exception as e:
            logger.error(f"Existence check failed: {e}")
            return False
    
    def get_all(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Retrieve all records from the database.
        
        Args:
            limit: Maximum number of records to retrieve.
            
        Returns:
            List of record dictionaries.
        """
        query = f"SELECT * FROM {self.table_name} ORDER BY id DESC"
        if limit:
            query += f" LIMIT {limit}"
        
        try:
            conn = self._sqlite3.connect(self.db_path)
            conn.row_factory = self._sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query)
            
            rows = cursor.fetchall()
            results = [dict(row) for row in rows]
            
            conn.close()
            return results
            
        except Exception as e:
            raise DatabaseError("get_all", str(e))
    
    def get_by_invoice_number(self, invoice_number: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a record by invoice number.
        
        Args:
            invoice_number: Invoice number to search for.
            
        Returns:
            Record dictionary or None if not found.
        """
        query = f"""
        SELECT * FROM {self.table_name}
        WHERE invoice_number = ?
        LIMIT 1
        """
        
        try:
            conn = self._sqlite3.connect(self.db_path)
            conn.row_factory = self._sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, (invoice_number,))
            
            row = cursor.fetchone()
            conn.close()
            
            return dict(row) if row else None
            
        except Exception as e:
            raise DatabaseError("get_by_invoice_number", str(e))
    
    def search(
        self,
        vendor_name: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        min_amount: Optional[float] = None,
        max_amount: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Search records with various filters.
        
        Args:
            vendor_name: Filter by vendor name (partial match).
            date_from: Filter by invoice date (from).
            date_to: Filter by invoice date (to).
            min_amount: Filter by minimum total amount.
            max_amount: Filter by maximum total amount.
            
        Returns:
            List of matching record dictionaries.
        """
        conditions = []
        params = []
        
        if vendor_name:
            conditions.append("vendor_name LIKE ?")
            params.append(f"%{vendor_name}%")
        
        if date_from:
            conditions.append("invoice_date >= ?")
            params.append(date_from)
        
        if date_to:
            conditions.append("invoice_date <= ?")
            params.append(date_to)
        
        if min_amount is not None:
            conditions.append("CAST(total_amount AS REAL) >= ?")
            params.append(min_amount)
        
        if max_amount is not None:
            conditions.append("CAST(total_amount AS REAL) <= ?")
            params.append(max_amount)
        
        query = f"SELECT * FROM {self.table_name}"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY invoice_date DESC"
        
        try:
            conn = self._sqlite3.connect(self.db_path)
            conn.row_factory = self._sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            rows = cursor.fetchall()
            results = [dict(row) for row in rows]
            
            conn.close()
            return results
            
        except Exception as e:
            raise DatabaseError("search", str(e))
    
    def get_count(self) -> int:
        """Get the total number of records in the database."""
        try:
            conn = self._sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {self.table_name}")
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception as e:
            raise DatabaseError("get_count", str(e))
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the stored data.
        
        Returns:
            Dictionary with various statistics.
        """
        stats = {}
        
        try:
            conn = self._sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Total count
            cursor.execute(f"SELECT COUNT(*) FROM {self.table_name}")
            stats['total_records'] = cursor.fetchone()[0]
            
            # Success rate
            cursor.execute(f"""
                SELECT 
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
                    COUNT(*) as total
                FROM {self.table_name}
            """)
            row = cursor.fetchone()
            if row[1] > 0:
                stats['success_rate'] = row[0] / row[1]
            else:
                stats['success_rate'] = 0
            
            # Average confidence
            cursor.execute(f"""
                SELECT AVG(average_confidence) 
                FROM {self.table_name}
                WHERE success = 1
            """)
            stats['avg_confidence'] = cursor.fetchone()[0] or 0
            
            # Unique vendors
            cursor.execute(f"""
                SELECT COUNT(DISTINCT vendor_name) 
                FROM {self.table_name}
            """)
            stats['unique_vendors'] = cursor.fetchone()[0]
            
            conn.close()
            return stats
            
        except Exception as e:
            logger.error(f"Could not get statistics: {e}")
            return {}
    
    def delete(self, invoice_number: str) -> bool:
        """
        Delete a record by invoice number.
        
        Args:
            invoice_number: Invoice number to delete.
            
        Returns:
            True if deleted, False if not found.
        """
        try:
            conn = self._sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                f"DELETE FROM {self.table_name} WHERE invoice_number = ?",
                (invoice_number,)
            )
            deleted = cursor.rowcount > 0
            conn.commit()
            conn.close()
            
            if deleted:
                logger.debug(f"Deleted record: {invoice_number}")
            
            return deleted
            
        except Exception as e:
            raise DatabaseError("delete", str(e))
    
    def close(self) -> None:
        """Close any open database connections."""
        # With sqlite3, connections are closed per-operation
        # This method is for interface consistency
        pass
