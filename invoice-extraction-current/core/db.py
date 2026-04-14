"""
SQLite persistence layer for extracted invoice data.

Uses SQLAlchemy ORM with three tables:
  - invoices        (one row per invoice, all header fields)
  - line_items      (one row per line item, FK → invoices)
  - validation_reports (one row per invoice, FK → invoices)
"""

import json
import re
import logging
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from core.config import DATABASE_PATH

Base = declarative_base()


def _to_str(value):
    """Convert dicts/lists to JSON strings; pass through strings and None."""
    if value is None or isinstance(value, str):
        return value
    return json.dumps(value)


# FIXED: Bug #10, #33 — Normalize dates to ISO format YYYY-MM-DD
def _normalize_date(date_str: str) -> str:
    """
    Convert various date formats to ISO YYYY-MM-DD.
    
    FIXED: Bug P1-3 — Enhanced date parsing to handle more formats
    
    Handles:
      - DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY (Indian/European format, dayfirst=True)
      - YYYY-MM-DD (ISO, pass through)
      - MM/DD/YYYY, MM-DD-YYYY (US format)
      - DD Mon YYYY, DD Month YYYY (e.g., "15 Jan 2024", "15 January 2024")
      - Mon DD, YYYY (e.g., "Jan 15, 2024")
      - Other formats via dateutil parser
    
    Returns original string if parsing fails.
    """
    if not date_str or not isinstance(date_str, str):
        return date_str
    
    date_str = date_str.strip()
    if not date_str:
        return date_str
    
    # Already ISO format
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        return date_str
    
    try:
        # Try DD/MM/YYYY, DD-MM-YYYY, or DD.MM.YYYY (Indian/European format)
        match = re.match(r'^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})$', date_str)
        if match:
            day, month, year = match.groups()
            # Validate day/month ranges
            d, m = int(day), int(month)
            if 1 <= d <= 31 and 1 <= m <= 12:
                return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
        # Try YYYY/MM/DD or YYYY.MM.DD
        match = re.match(r'^(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})$', date_str)
        if match:
            year, month, day = match.groups()
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
        # Try textual formats: "15 Jan 2024", "January 15, 2024", etc.
        # Use dateutil parser with dayfirst=True for Indian context
        from dateutil import parser as date_parser
        parsed = date_parser.parse(date_str, dayfirst=True)
        return parsed.strftime("%Y-%m-%d")
    except Exception:
        # Return original if parsing fails
        return date_str


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # -- source / processing --
    source_file = Column(String, unique=True, nullable=False)
    source_path = Column(Text)
    processed_at = Column(DateTime)
    overall_confidence = Column(Float)
    validated = Column(Boolean, default=False)

    # -- header fields --
    invoice_number = Column(String)
    invoice_date = Column(String)
    due_date = Column(String)
    purchase_order_number = Column(String)

    # vendor
    vendor_name = Column(String)
    vendor_address = Column(Text)
    vendor_email = Column(String)
    vendor_phone = Column(String)
    vendor_tax_id = Column(String)
    vendor_website = Column(String)

    # bill_to
    bill_to_name = Column(String)
    bill_to_address = Column(Text)
    bill_to_email = Column(String)

    # ship_to
    ship_to_name = Column(String)
    ship_to_address = Column(Text)

    # amounts
    subtotal = Column(Float)
    discount = Column(Float)
    tax_rate = Column(Float)
    tax_amount = Column(Float)
    shipping = Column(Float)
    total_amount = Column(Float)
    amount_paid = Column(Float)
    amount_due = Column(Float)

    # misc
    currency = Column(String)
    payment_terms = Column(String)
    payment_method = Column(String)
    bank_details = Column(Text)
    notes = Column(Text)

    # -- metadata extras --
    pdf_type = Column(String)
    page_count = Column(Integer)
    ocr_engine = Column(String)
    tables_found = Column(Integer)
    text_length = Column(Integer)
    processing_seconds = Column(Float)

    # relationships
    line_items = relationship("LineItem", back_populates="invoice", cascade="all, delete-orphan")
    validation_report = relationship("ValidationReport", back_populates="invoice",
                                     uselist=False, cascade="all, delete-orphan")
    
    # FIXED: Bug #20 — Index for duplicate detection
    __table_args__ = (
        Index("ix_dedup", "invoice_number", "vendor_name", "total_amount"),
    )


class LineItem(Base):
    __tablename__ = "line_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)

    description = Column(Text)
    hsn_sac = Column(String)
    quantity = Column(Float)
    unit_price = Column(Float)
    discount = Column(Float)
    tax_rate = Column(Float)
    tax_amount = Column(Float)
    total = Column(Float)
    # FIXED: Bug #19 — Add currency field to line items
    currency = Column(String)

    invoice = relationship("Invoice", back_populates="line_items")


class ValidationReport(Base):
    __tablename__ = "validation_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)

    passed = Column(Boolean, default=False)
    score = Column(Float)
    issues = Column(Text)  # JSON string of warnings / math_checks

    invoice = relationship("Invoice", back_populates="validation_report")


# FIXED: Bug #21 — Audit trail for SOX compliance
class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    table_name = Column(String, nullable=False)
    record_id = Column(Integer)
    action = Column(String)       # INSERT / UPDATE / DELETE
    user_id = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    old_value = Column(Text)      # JSON string
    new_value = Column(Text)      # JSON string


# ---------------------------------------------------------------------------
# Engine / Session factory  (lazy singleton)
# FIXED: Bug P1-7 — Added proper connection pooling for SQLite
# ---------------------------------------------------------------------------

from sqlalchemy.pool import QueuePool

_engine = None
_Session = None


def _get_engine():
    """Get or create SQLAlchemy engine with connection pooling."""
    global _engine
    if _engine is None:
        DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
        # FIXED: Bug P1-7 — Configure connection pool for better concurrency
        # - pool_size: max connections in pool
        # - max_overflow: extra connections beyond pool_size when under load
        # - pool_timeout: seconds to wait for connection from pool
        # - pool_recycle: recycle connections after N seconds (prevent stale)
        _engine = create_engine(
            f"sqlite:///{DATABASE_PATH}",
            echo=False,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=3600,  # Recycle after 1 hour
            connect_args={"check_same_thread": False}  # Allow multi-thread access
        )
    return _engine


def _get_session():
    global _Session
    if _Session is None:
        _Session = sessionmaker(bind=_get_engine())
    return _Session()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def init_db():
    """Create all tables if they don't already exist."""
    Base.metadata.create_all(_get_engine())


def insert_extraction(data: dict) -> str:
    """
    Insert one extraction JSON dict into all 3 tables.

    Returns the source_file string on success.
    Raises ValueError if source_file is missing from metadata.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    meta = data.get("metadata", {})
    val = data.get("validation", {})

    source_file = meta.get("source_file")
    if not source_file:
        raise ValueError("Extraction dict has no metadata.source_file")

    # FIXED: Bug #28 — Validate invoice_number before insertion
    from core.llm_extractor import _is_valid_invoice_number
    invoice_num = data.get("invoice_number")
    if invoice_num and not _is_valid_invoice_number(invoice_num):
        logger.warning("[db] Invalid invoice_number rejected: %r", invoice_num)
        data["invoice_number"] = None

    session = _get_session()
    try:
        # FIXED: Bug P1-4 — Enhanced duplicate detection with invoice number uniqueness
        # Check for existing invoice with same invoice_number, vendor_name, total_amount
        vendor = data.get("vendor") or {}
        vendor_name_normalized = vendor.get("name", "").upper().strip() if vendor.get("name") else None
        invoice_num = data.get("invoice_number")
        total_amt = data.get("total_amount")
        
        # Check 1: Exact duplicate (invoice number + vendor + amount)
        if invoice_num and vendor_name_normalized and total_amt is not None:
            existing = session.query(Invoice).filter(
                Invoice.invoice_number == invoice_num,
                Invoice.vendor_name == vendor_name_normalized,
                Invoice.total_amount == total_amt
            ).first()
            
            if existing:
                logger.warning(
                    "[db] Duplicate invoice detected: invoice_number=%r, vendor=%r, total=%r. Skipping insertion.",
                    invoice_num, vendor_name_normalized, total_amt
                )
                session.close()
                return source_file  # Return without inserting
        
        # Check 2: Invoice number reuse (same invoice # + vendor, different amount)
        if invoice_num and vendor_name_normalized:
            existing_diff_amt = session.query(Invoice).filter(
                Invoice.invoice_number == invoice_num,
                Invoice.vendor_name == vendor_name_normalized,
                Invoice.total_amount != total_amt  # Different amount = potential error
            ).first()
            
            if existing_diff_amt:
                logger.error(
                    "[db] WARNING: Invoice number %r from vendor %r already exists with different amount (%.2f vs %.2f). Possible duplicate or error.",
                    invoice_num, vendor_name_normalized, existing_diff_amt.total_amount, total_amt
                )
                # Log but continue - might be legitimate (credit note, revision, etc.)
        
        # -- invoices row --
        bill_to = data.get("bill_to") or {}
        ship_to = data.get("ship_to") or {}

        extraction_time = meta.get("extraction_time")
        processed_at = None
        if extraction_time:
            try:
                processed_at = datetime.fromisoformat(extraction_time)
            except (ValueError, TypeError):
                pass

        inv = Invoice(
            source_file=source_file,
            source_path=meta.get("source_path"),
            processed_at=processed_at,
            overall_confidence=None,
            validated=val.get("passed", False),

            invoice_number=data.get("invoice_number"),
            # FIXED: Bug #10, #33 — Normalize dates to ISO format
            invoice_date=_normalize_date(data.get("invoice_date")),
            due_date=_normalize_date(data.get("due_date")),
            purchase_order_number=data.get("purchase_order_number"),

            # FIXED: Bug #25 — Normalize vendor_name (UPPER().strip())
            vendor_name=vendor.get("name", "").upper().strip() if vendor.get("name") else None,
            vendor_address=vendor.get("address"),
            vendor_email=vendor.get("email"),
            vendor_phone=vendor.get("phone"),
            vendor_tax_id=vendor.get("tax_id"),
            vendor_website=vendor.get("website"),

            bill_to_name=bill_to.get("name"),
            bill_to_address=bill_to.get("address"),
            bill_to_email=bill_to.get("email"),

            ship_to_name=ship_to.get("name"),
            ship_to_address=ship_to.get("address"),

            subtotal=data.get("subtotal"),
            discount=data.get("discount"),
            tax_rate=data.get("tax_rate"),
            tax_amount=data.get("tax_amount"),
            shipping=data.get("shipping"),
            total_amount=data.get("total_amount"),
            amount_paid=data.get("amount_paid"),
            amount_due=data.get("amount_due"),

            currency=data.get("currency"),
            payment_terms=_to_str(data.get("payment_terms")),
            payment_method=_to_str(data.get("payment_method")),
            bank_details=_to_str(data.get("bank_details")),
            notes=_to_str(data.get("notes")),

            pdf_type=meta.get("pdf_type"),
            page_count=meta.get("page_count"),
            ocr_engine=meta.get("ocr_engine"),
            tables_found=meta.get("tables_found"),
            text_length=meta.get("text_length"),
            processing_seconds=meta.get("processing_seconds"),
        )
        session.add(inv)
        session.flush()  # get inv.id

        # -- line_items rows --
        for item in data.get("line_items") or []:
            li = LineItem(
                invoice_id=inv.id,
                description=_to_str(item.get("description")),
                hsn_sac=_to_str(item.get("hsn_sac")),
                quantity=item.get("quantity"),
                unit_price=item.get("unit_price"),
                discount=item.get("discount"),
                tax_rate=item.get("tax_rate"),
                tax_amount=item.get("tax_amount"),
                total=item.get("total") or item.get("line_total"),
                # FIXED: Bug #19 - Populate line item currency field
                currency=item.get("currency") or data.get("currency"),
            )
            session.add(li)

        # -- validation_reports row --
        # Build a score: 1.0 if passed with 0 warnings, deduct per warning
        warnings = val.get("warnings") or []
        score = 1.0 if val.get("passed", False) else 0.0
        if warnings:
            score = max(0.0, 1.0 - 0.1 * len(warnings))

        issues_dict = {
            "warnings": warnings,
            "math_checks": val.get("math_checks", {}),
            "line_item_count": val.get("line_item_count", 0),
        }
        vr = ValidationReport(
            invoice_id=inv.id,
            passed=val.get("passed", False),
            score=round(score, 2),
            issues=json.dumps(issues_dict),
        )
        session.add(vr)

        session.commit()
        
        # FIXED: Bug #21 — Audit trail for SOX compliance
        try:
            audit_entry = AuditLog(
                table_name="invoices",
                record_id=inv.id,
                action="INSERT",
                user_id="system",  # Could be enhanced to track actual user
                new_value=json.dumps({
                    "invoice_number": inv.invoice_number,
                    "vendor_name": inv.vendor_name,
                    "total_amount": inv.total_amount,
                    "source_file": inv.source_file
                })
            )
            session.add(audit_entry)
            session.commit()
        except Exception as audit_err:
            logger.warning("[db] Failed to write audit log: %s", audit_err)
        
        return source_file

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def source_file_exists(source_file: str) -> bool:
    """Check if an invoice with this source_file already exists."""
    session = _get_session()
    try:
        return session.query(Invoice.id).filter_by(source_file=source_file).first() is not None
    finally:
        session.close()


def get_db():
    """
    Get a database session (generator for FastAPI dependency injection).

    Usage:
        db = next(get_db())
        try:
            result = db.query(Invoice).all()
        finally:
            db.close()
    """
    session = _get_session()
    try:
        yield session
    finally:
        session.close()
