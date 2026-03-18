"""
Pydantic schemas for invoice extraction data.

These models define the canonical JSON structure for extracted invoices.
Used by the FastAPI API for request/response validation and by the RAG
system for consistent data handling.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class VendorInfo(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    gstin: Optional[str] = None


class BillToInfo(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    gstin: Optional[str] = None


class LineItemSchema(BaseModel):
    description: Optional[str] = None
    hsn_sac: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    discount: Optional[float] = None
    tax_rate: Optional[float] = None
    tax_amount: Optional[float] = None
    total: Optional[float] = None
    line_total: Optional[float] = None  # alias for total


class MathChecks(BaseModel):
    line_items_sum_to_subtotal: Optional[bool] = None
    totals_consistent: Optional[bool] = None
    line_item_math_correct: Optional[bool] = None


class ValidationResult(BaseModel):
    passed: bool = False
    warnings: List[str] = Field(default_factory=list)
    math_checks: MathChecks = Field(default_factory=MathChecks)
    warning_count: int = 0


class ExtractionMetadata(BaseModel):
    source_file: str = ""
    source_path: str = ""
    file_type: str = ""
    extraction_method: str = ""
    ocr_confidence: float = 0.0
    processing_time_ms: int = 0
    pipeline_version: str = ""
    text_length: int = 0
    batch_index: Optional[int] = None


class InvoiceSchema(BaseModel):
    """Complete extracted invoice data."""
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    vendor: VendorInfo = Field(default_factory=VendorInfo)
    bill_to: BillToInfo = Field(default_factory=BillToInfo)
    line_items: List[LineItemSchema] = Field(default_factory=list)
    subtotal: Optional[float] = None
    tax_rate: Optional[float] = None
    tax_amount: Optional[float] = None
    discount: Optional[float] = None
    total_amount: Optional[float] = None
    currency: Optional[str] = None
    payment_terms: Optional[str] = None
    purchase_order_number: Optional[str] = None
    notes: Optional[str] = None
    validation: Optional[ValidationResult] = None

    class Config:
        # Allow extra fields (e.g., metadata) without error
        extra = "allow"


class ExtractResponse(BaseModel):
    """API response for single invoice extraction."""
    status: str = "success"
    data: Dict[str, Any] = Field(default_factory=dict)


class BatchExtractResponse(BaseModel):
    """API response for batch invoice extraction."""
    status: str = "success"
    total: int = 0
    successful: int = 0
    failed: int = 0
    results: List[Dict[str, Any]] = Field(default_factory=list)


class QuestionRequest(BaseModel):
    """RAG question request."""
    question: str


class QuestionResponse(BaseModel):
    """RAG question response."""
    answer: str
    sources: List[str] = Field(default_factory=list)
    chunks_used: int = 0


class IndexRequest(BaseModel):
    """RAG indexing request."""
    data: Dict[str, Any]
    filename: str = "unknown"


class IndexResponse(BaseModel):
    """RAG indexing response."""
    status: str = "indexed"
    chunks: int = 0


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
    ollama_available: bool = False
    pipeline_version: str = "2.0.0"
