"""FastAPI application — invoice upload, processing, and status endpoints."""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.graph import process_invoice
from api.database import AsyncSessionLocal, Invoice, LineItem, UserNotification, init_db
from api.schemas import InvoiceListResponse, InvoiceResponse, UserNotificationListResponse

# Load environment
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-30s | %(levelname)-7s | %(message)s",
)
logger = logging.getLogger(__name__)

# Upload directory
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("Database initialized")
    yield


app = FastAPI(
    title="AP Invoice Processing Agent",
    description=(
        "Agentic AI system for Accounts Payable invoice processing. "
        "Uses MCP tools to validate VAT, SIRET, supplier bank details, "
        "and PO against ERP before creating the invoice."
    ),
    version="0.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/api/invoices/upload", response_model=InvoiceResponse)
async def upload_invoice(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload an invoice PDF or image and trigger the full processing pipeline.

    The pipeline:
    1. OCR + LLM extraction (ingestion agent)
    2. ERP validation via MCP tools (validation agent)
    3. ERP invoice creation or rejection (processing agent)
    """
    # Validate file type
    allowed_extensions = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".txt"}
    suffix = Path(file.filename).suffix.lower()
    if suffix not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {suffix}. Allowed: {allowed_extensions}",
        )

    # Save uploaded file
    file_path = UPLOAD_DIR / file.filename
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    logger.info("Saved uploaded file to %s", file_path)

    # Create initial DB record
    invoice = Invoice(filename=file.filename, status="pending")
    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)

    # Run the LangGraph workflow
    try:
        result = await process_invoice(str(file_path))

        # Update DB record with results
        invoice.status = result.get("status", "error")
        
        # Save confidence score
        confidence = result.get("extraction_confidence", 1.0)
        invoice.confidence_score = confidence

        extracted = result.get("extracted_data", {})
        if extracted:
            invoice.supplier_name = extracted.get("supplier_name")
            invoice.vat_number = extracted.get("vat_number")
            invoice.siret = extracted.get("siret")
            invoice.iban = extracted.get("iban")
            invoice.bic = extracted.get("bic")
            invoice.po_number = extracted.get("po_number")
            invoice.invoice_number = extracted.get("invoice_number")
            invoice.invoice_date = extracted.get("invoice_date")
            invoice.total_ht = extracted.get("total_ht")
            invoice.tva_rate = extracted.get("tva_rate")
            invoice.tva_amount = extracted.get("tva_amount")
            invoice.total_ttc = extracted.get("total_ttc")
            invoice.currency = extracted.get("currency")
            invoice.raw_ocr_text = extracted.get("raw_ocr_text")
            
            # Line items
            line_items_data = extracted.get("line_items", [])
            for li_data in line_items_data:
                try:
                    qty = float(li_data.get("quantity")) if li_data.get("quantity") is not None else None
                except (ValueError, TypeError):
                    qty = None
                try:
                    price = float(li_data.get("unit_price")) if li_data.get("unit_price") is not None else None
                except (ValueError, TypeError):
                    price = None
                try:
                    tot = float(li_data.get("total")) if li_data.get("total") is not None else None
                except (ValueError, TypeError):
                    tot = None
                    
                line_item = LineItem(
                    invoice_id=invoice.id,
                    description=li_data.get("description"),
                    quantity=qty,
                    unit_price=price,
                    total=tot,
                )
                db.add(line_item)

        invoice.validation_results = json.dumps(result.get("validation_results")) if result.get("validation_results") else None
        invoice.processing_result = json.dumps(result.get("processing_result")) if result.get("processing_result") else None
        invoice.errors = json.dumps(result.get("errors", []))

        await db.commit()
        await db.refresh(invoice)

        # Check for manual review requirements
        needs_review = False
        review_message = ""

        if invoice.status in ("error", "rejected"):
            needs_review = True
            review_message = f"Workflow failed or was rejected. Status: {invoice.status}. Please review manually."
        elif confidence < 0.80:
            needs_review = True
            review_message = f"Low extraction confidence ({confidence:.2f}). Please review manually."

        if needs_review:
            notification = UserNotification(
                invoice_id=invoice.id,
                message=review_message,
                requires_manual_review=1
            )
            db.add(notification)
            await db.commit()

    except Exception as e:
        logger.exception("Invoice processing failed")
        invoice.status = "error"
        invoice.errors = json.dumps([str(e)])
        await db.commit()
        await db.refresh(invoice)
        
        # Also notify user on complete crash
        notification = UserNotification(
            invoice_id=invoice.id,
            message=f"System error during processing: {str(e)[:200]}...",
            requires_manual_review=1
        )
        db.add(notification)
        await db.commit()

    return invoice.to_dict()


@app.get("/api/invoices/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the processing status and details for a specific invoice."""
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")
    return invoice.to_dict()


@app.get("/api/invoices", response_model=InvoiceListResponse)
async def list_invoices(
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 50,
):
    """List all processed invoices with pagination."""
    result = await db.execute(
        select(Invoice).order_by(Invoice.created_at.desc()).offset(skip).limit(limit)
    )
    invoices = result.scalars().all()

    count_result = await db.execute(select(Invoice))
    total = len(count_result.scalars().all())

    return {
        "invoices": [inv.to_dict() for inv in invoices],
        "total": total,
    }


@app.get("/api/notifications", response_model=UserNotificationListResponse)
async def list_notifications(
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 50,
):
    """List all manual review notifications."""
    result = await db.execute(
        select(UserNotification).order_by(UserNotification.created_at.desc()).offset(skip).limit(limit)
    )
    notifications = result.scalars().all()

    count_result = await db.execute(select(UserNotification))
    total = len(count_result.scalars().all())

    return {
        "notifications": [notif.to_dict() for notif in notifications],
        "total": total,
    }


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ap-invoice-agent"}
