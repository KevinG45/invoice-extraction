"""
Line Item Data Structure.

This module defines the LineItem dataclass for representing
individual line items extracted from invoices.

Author: ML Engineering Team
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from decimal import Decimal, InvalidOperation


@dataclass
class LineItem:
    """
    Represents a single line item from an invoice.
    
    Attributes:
        item_code: Product/service code or SKU
        description: Item description
        quantity: Quantity ordered
        unit_price: Price per unit
        total: Line total (quantity × unit_price)
        unit: Unit of measurement (e.g., 'pcs', 'hrs')
        tax_rate: Optional tax rate percentage
        tax_amount: Optional tax amount
        discount: Optional discount amount
        row_index: Position in the table (0-indexed)
        confidence: Extraction confidence score
        
    Example:
        >>> item = LineItem(
        ...     item_code="WIDGET-001",
        ...     description="Blue Widget",
        ...     quantity=10.0,
        ...     unit_price=Decimal("25.00"),
        ...     total=Decimal("250.00")
        ... )
        >>> print(item.to_dict())
    """
    
    # Core fields
    item_code: Optional[str] = None
    description: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[Decimal] = None
    total: Optional[Decimal] = None
    
    # Additional fields
    unit: Optional[str] = None
    tax_rate: Optional[float] = None
    tax_amount: Optional[Decimal] = None
    discount: Optional[Decimal] = None
    
    # Metadata
    row_index: int = 0
    confidence: float = 0.0
    raw_values: Dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate and normalize fields after initialization."""
        # Ensure numeric fields are proper types
        if isinstance(self.unit_price, (int, float, str)):
            self.unit_price = self._to_decimal(self.unit_price)
        if isinstance(self.total, (int, float, str)):
            self.total = self._to_decimal(self.total)
        if isinstance(self.tax_amount, (int, float, str)):
            self.tax_amount = self._to_decimal(self.tax_amount)
        if isinstance(self.discount, (int, float, str)):
            self.discount = self._to_decimal(self.discount)
        if isinstance(self.quantity, str):
            self.quantity = self._parse_quantity(self.quantity)
    
    @staticmethod
    def _to_decimal(value) -> Optional[Decimal]:
        """Convert value to Decimal."""
        if value is None:
            return None
        try:
            # Handle string with currency symbols
            if isinstance(value, str):
                value = value.replace('$', '').replace('€', '').replace('£', '')
                value = value.replace(',', '').strip()
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None
    
    @staticmethod
    def _parse_quantity(value: str) -> Optional[float]:
        """Parse quantity from string."""
        if value is None:
            return None
        try:
            cleaned = str(value).replace(',', '').strip()
            return float(cleaned)
        except (ValueError, TypeError):
            return None
    
    @property
    def is_valid(self) -> bool:
        """Check if line item has minimum required data."""
        has_identity = bool(self.description or self.item_code)
        has_financial = (
            self.total is not None or 
            self.unit_price is not None or
            (self.quantity is not None and self.unit_price is not None)
        )
        return has_identity or has_financial
    
    @property
    def calculated_total(self) -> Optional[Decimal]:
        """Calculate total from quantity and unit price."""
        if self.quantity is not None and self.unit_price is not None:
            return Decimal(str(self.quantity)) * self.unit_price
        return None
    
    @property
    def total_matches_calculated(self) -> bool:
        """Check if extracted total matches calculated total."""
        if self.total is None or self.calculated_total is None:
            return False
        # Allow small difference for rounding
        diff = abs(self.total - self.calculated_total)
        return diff < Decimal("0.02")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for export.
        
        Returns:
            Dictionary representation suitable for JSON/DataFrame.
        """
        return {
            'item_code': self.item_code,
            'description': self.description,
            'quantity': self.quantity,
            'unit': self.unit,
            'unit_price': float(self.unit_price) if self.unit_price else None,
            'total': float(self.total) if self.total else None,
            'tax_rate': self.tax_rate,
            'tax_amount': float(self.tax_amount) if self.tax_amount else None,
            'discount': float(self.discount) if self.discount else None,
            'row_index': self.row_index,
            'confidence': self.confidence
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], row_index: int = 0) -> 'LineItem':
        """
        Create LineItem from dictionary.
        
        Args:
            data: Dictionary with line item data.
            row_index: Position in table.
            
        Returns:
            LineItem instance.
        """
        return cls(
            item_code=data.get('item_code') or data.get('Item_Code') or data.get('code'),
            description=data.get('description') or data.get('Description') or data.get('item'),
            quantity=data.get('quantity') or data.get('Quantity') or data.get('qty'),
            unit_price=data.get('unit_price') or data.get('Unit_Price') or data.get('price'),
            total=data.get('total') or data.get('Total') or data.get('amount'),
            unit=data.get('unit') or data.get('Unit'),
            tax_rate=data.get('tax_rate'),
            tax_amount=data.get('tax_amount'),
            discount=data.get('discount'),
            row_index=row_index,
            confidence=data.get('confidence', 0.0),
            raw_values=data
        )
    
    @classmethod
    def from_donut_output(cls, item_data: Dict[str, Any], row_index: int = 0) -> 'LineItem':
        """
        Create LineItem from Donut model output format.
        
        Handles CORD v2 field names (nm, cnt, price, unitprice, etc.)
        
        Args:
            item_data: Dictionary from Donut extraction.
            row_index: Position in table.
            
        Returns:
            LineItem instance.
        """
        # Donut CORD v2 uses these field names
        description = (
            item_data.get('nm') or 
            item_data.get('item_nm') or 
            item_data.get('description') or
            item_data.get('sub_nm') or
            item_data.get('name')
        )
        
        quantity = (
            item_data.get('cnt') or 
            item_data.get('num') or 
            item_data.get('quantity') or
            item_data.get('sub_cnt')
        )
        
        unit_price = (
            item_data.get('unitprice') or 
            item_data.get('price') or 
            item_data.get('unit_price')
        )
        
        total = (
            item_data.get('total_price') or 
            item_data.get('amount') or
            item_data.get('sub_total_price')
        )
        
        item_code = (
            item_data.get('item_code') or 
            item_data.get('prod_item_cd') or
            item_data.get('code')
        )
        
        return cls(
            item_code=item_code,
            description=description,
            quantity=quantity,
            unit_price=unit_price,
            total=total,
            row_index=row_index,
            confidence=0.8,  # Default confidence for Donut
            raw_values=item_data
        )
    
    def __repr__(self) -> str:
        return (
            f"LineItem(code={self.item_code}, "
            f"desc='{self.description[:20]}...' " if self.description and len(self.description) > 20 else f"desc='{self.description}', "
            f"qty={self.quantity}, "
            f"total={self.total})"
        )
