"""Shared state definition for the LangGraph invoice processing workflow."""

from __future__ import annotations

from typing import Any, Optional

from typing_extensions import TypedDict


class ExtractedInvoiceData(TypedDict, total=False):
    """Structured data extracted from an invoice by the ingestion agent."""
    supplier_name: str
    vat_number: str
    siret: str
    iban: str
    bic: str
    po_number: str
    invoice_number: str
    invoice_date: str  # ISO format
    line_items: list[dict[str, Any]]
    total_ht: float       # Total hors taxes
    tva_rate: float       # TVA percentage
    tva_amount: float     # TVA amount
    total_ttc: float      # Total toutes taxes comprises
    currency: str
    confidence_score: float
    raw_ocr_text: str


class ValidationDetail(TypedDict):
    """Result of a single validation check."""
    field: str
    valid: bool
    message: str
    details: dict[str, Any]


class InvoiceProcessingState(TypedDict, total=False):
    """Complete state passed through the LangGraph workflow."""
    # Input
    file_path: str
    file_bytes: bytes

    # Ingestion
    extracted_data: ExtractedInvoiceData
    extraction_confidence: float
    candidate_suppliers: list[dict[str, Any]]

    # Validation
    validation_results: list[ValidationDetail]
    all_validations_passed: bool

    # Processing
    processing_result: dict[str, Any]

    # Overall
    status: str   # pending | ingested | validated | processed | rejected | error
    errors: list[str]
