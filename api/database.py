"""Database layer — SQLAlchemy async with SQLite (or PostgreSQL)."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


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


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="pending")
    extracted_data = Column(Text, nullable=True)      # JSON string
    validation_results = Column(Text, nullable=True)   # JSON string
    processing_result = Column(Text, nullable=True)    # JSON string
    errors = Column(Text, nullable=True)               # JSON string
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "filename": self.filename,
            "status": self.status,
            "extracted_data": json.loads(self.extracted_data) if self.extracted_data else None,
            "validation_results": json.loads(self.validation_results) if self.validation_results else None,
            "processing_result": json.loads(self.processing_result) if self.processing_result else None,
            "errors": json.loads(self.errors) if self.errors else [],
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
