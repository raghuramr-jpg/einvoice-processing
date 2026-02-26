"""Database layer — SQLAlchemy async with SQLite (or PostgreSQL)."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./invoices.db")


# ---------------------------------------------------------------------------
# Async engine (for FastAPI)
# ---------------------------------------------------------------------------
async_engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False)


# ---------------------------------------------------------------------------
# ORM Base
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    vat_number = Column(String(100), nullable=True)
    iban = Column(String(100), nullable=True)
    is_valid = Column(Integer, default=1)  # 1 indicating True, 0 indicating False
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "vat_number": self.vat_number,
            "iban": self.iban,
            "is_valid": bool(self.is_valid),
            "created_at": self.created_at,
        }


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="pending")
    
    # Extracted Fields
    supplier_name = Column(String, nullable=True)
    vat_number = Column(String, nullable=True)
    siret = Column(String, nullable=True)
    iban = Column(String, nullable=True)
    bic = Column(String, nullable=True)
    po_number = Column(String, nullable=True)
    invoice_number = Column(String, nullable=True)
    invoice_date = Column(String, nullable=True)
    total_ht = Column(Float, nullable=True)
    tva_rate = Column(Float, nullable=True)
    tva_amount = Column(Float, nullable=True)
    total_ttc = Column(Float, nullable=True)
    currency = Column(String, nullable=True)
    confidence_score = Column(Float, nullable=True)    # Score from 0.0 to 1.0

    raw_ocr_text = Column(Text, nullable=True)
    
    # Store the messages
    validation_results = Column(Text, nullable=True)   # JSON string
    processing_result = Column(Text, nullable=True)    # JSON string
    errors = Column(Text, nullable=True)               # JSON string
    
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    line_items = relationship("LineItem", back_populates="invoice", cascade="all, delete-orphan", lazy="selectin")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "filename": self.filename,
            "status": self.status,
            "extracted_data": {
                "supplier_name": self.supplier_name,
                "vat_number": self.vat_number,
                "siret": self.siret,
                "iban": self.iban,
                "bic": self.bic,
                "po_number": self.po_number,
                "invoice_number": self.invoice_number,
                "invoice_date": self.invoice_date,
                "total_ht": self.total_ht,
                "tva_rate": self.tva_rate,
                "tva_amount": self.tva_amount,
                "total_ttc": self.total_ttc,
                "currency": self.currency,
                "line_items": [li.to_dict() for li in self.line_items]
            },
            "validation_results": json.loads(self.validation_results) if self.validation_results else None,
            "processing_result": json.loads(self.processing_result) if self.processing_result else None,
            "errors": json.loads(self.errors) if self.errors else [],
            "confidence_score": self.confidence_score,
            "created_at": self.created_at,
        }

class LineItem(Base):
    __tablename__ = "line_items"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    description = Column(String, nullable=True)
    quantity = Column(Float, nullable=True)
    unit_price = Column(Float, nullable=True)
    total = Column(Float, nullable=True)
    
    invoice = relationship("Invoice", back_populates="line_items")
    
    def to_dict(self) -> dict:
        return {
            "description": self.description,
            "quantity": self.quantity,
            "unit_price": self.unit_price,
            "total": self.total
        }


class UserNotification(Base):
    __tablename__ = "user_notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(Integer, nullable=True)
    message = Column(Text, nullable=False)
    requires_manual_review = Column(Integer, default=1)  # 1 indicating True for sqlite
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "invoice_id": self.invoice_id,
            "message": self.message,
            "requires_manual_review": bool(self.requires_manual_review),
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# DB lifecycle
# ---------------------------------------------------------------------------
async def init_db():
    """Create tables if they don't exist."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
