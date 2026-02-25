"""Pydantic models for ERP entities used by the MCP ERP Server."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Supplier
# ---------------------------------------------------------------------------
class Supplier(BaseModel):
    id: int
    name: str
    vat_number: str = Field(..., description="EU VAT number, e.g. FR12345678901")
    siret: str = Field(..., description="14-digit French SIRET number")
    iban: str
    bic: str
    address: str
    city: str
    country: str = "FR"
    active: bool = True


# ---------------------------------------------------------------------------
# Purchase Order
# ---------------------------------------------------------------------------
class POStatus(str, Enum):
    OPEN = "open"
    PARTIALLY_RECEIVED = "partially_received"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class PurchaseOrder(BaseModel):
    id: int
    po_number: str
    supplier_id: int
    status: POStatus = POStatus.OPEN
    total_amount: float
    currency: str = "EUR"
    created_date: date
    description: str = ""


# ---------------------------------------------------------------------------
# Invoice (ERP-side)
# ---------------------------------------------------------------------------
class ERPInvoice(BaseModel):
    id: Optional[int] = None
    erp_invoice_id: str
    supplier_id: int
    po_number: str
    invoice_number: str
    invoice_date: date
    total_ht: float
    tva_amount: float
    total_ttc: float
    currency: str = "EUR"
    status: str = "posted"
    created_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# MCP Tool I/O Models
# ---------------------------------------------------------------------------
class ValidationResult(BaseModel):
    valid: bool
    message: str
    details: dict = Field(default_factory=dict)


class InvoicePayload(BaseModel):
    """Payload sent to create_erp_invoice MCP tool."""
    supplier_name: str
    vat_number: str
    siret: str
    po_number: str
    invoice_number: str
    invoice_date: str  # ISO format
    line_items: list[dict]
    total_ht: float
    tva_rate: float
    tva_amount: float
    total_ttc: float
    currency: str = "EUR"


class InvoiceCreationResult(BaseModel):
    success: bool
    erp_invoice_id: Optional[str] = None
    message: str
