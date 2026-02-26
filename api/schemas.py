"""Pydantic schemas for API requests and responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class LineItem(BaseModel):
    description: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    total: Optional[float] = None


class ExtractedDataResponse(BaseModel):
    supplier_name: Optional[str] = None
    vat_number: Optional[str] = None
    siret: Optional[str] = None
    iban: Optional[str] = None
    bic: Optional[str] = None
    po_number: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    line_items: list[LineItem] = Field(default_factory=list)
    total_ht: Optional[float] = None
    tva_rate: Optional[float] = None
    tva_amount: Optional[float] = None
    total_ttc: Optional[float] = None
    currency: Optional[str] = None


class ValidationDetailResponse(BaseModel):
    field: str
    valid: bool
    message: str


class ProcessingResultResponse(BaseModel):
    success: Optional[bool] = None
    erp_invoice_id: Optional[str] = None
    message: Optional[str] = None
    rejected: Optional[bool] = None
    failures: Optional[list[dict[str, str]]] = None
    recommendation: Optional[str] = None
    status: Optional[str] = None
    confidence_score: Optional[float] = None


class InvoiceResponse(BaseModel):
    id: int
    filename: str
    status: str
    extracted_data: Optional[ExtractedDataResponse] = None
    validation_results: Optional[list[ValidationDetailResponse]] = None
    processing_result: Optional[ProcessingResultResponse] = None
    errors: list[str] = Field(default_factory=list)
    confidence_score: Optional[float] = None
    created_at: datetime


class InvoiceListResponse(BaseModel):
    invoices: list[InvoiceResponse]
    total: int


class UserNotificationResponse(BaseModel):
    id: int
    invoice_id: Optional[int] = None
    message: str
    requires_manual_review: bool
    created_at: datetime


class UserNotificationListResponse(BaseModel):
    notifications: list[UserNotificationResponse]
    total: int
