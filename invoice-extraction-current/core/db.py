"""
SQLite persistence layer for extracted invoice data.

Uses SQLAlchemy ORM with three tables:
  - invoices        (one row per invoice, all header fields)
  - line_items      (one row per line item, FK → invoices)
  - validation_reports (one row per invoice, FK → invoices)
"""

import json
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
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

    invoice = relationship("Invoice", back_populates="line_items")


class ValidationReport(Base):
    __tablename__ = "validation_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)

    passed = Column(Boolean, default=False)
    score = Column(Float)
    issues = Column(Text)  # JSON string of warnings / math_checks

    invoice = relationship("Invoice", back_populates="validation_report")


# ---------------------------------------------------------------------------
# Engine / Session factory  (lazy singleton)
# ---------------------------------------------------------------------------

_engine = None
_Session = None


def _get_engine():
    global _engine
    if _engine is None:
        DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(f"sqlite:///{DATABASE_PATH}", echo=False)
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
    meta = data.get("metadata", {})
    val = data.get("validation", {})

    source_file = meta.get("source_file")
    if not source_file:
        raise ValueError("Extraction dict has no metadata.source_file")

    session = _get_session()
    try:
        # -- invoices row --
        vendor = data.get("vendor") or {}
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
            invoice_date=data.get("invoice_date"),
            due_date=data.get("due_date"),
            purchase_order_number=data.get("purchase_order_number"),

            vendor_name=vendor.get("name"),
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
