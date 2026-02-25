"""Ingestion Agent — OCR + LLM extraction of structured invoice data."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from .state import InvoiceProcessingState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LLM configuration
# ---------------------------------------------------------------------------

def _get_llm() -> ChatOpenAI:
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    
    if provider == "ollama":
        # Use LangChain's ChatOpenAI but point it to Ollama's local OpenAI-compatible endpoint
        return ChatOpenAI(
            model=os.getenv("LLM_MODEL", "llama3.1"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            api_key="ollama",  # API key is required by the client but ignored by Ollama
            temperature=0,
        )
    else:
        # Standard OpenAI client
        return ChatOpenAI(
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            temperature=0,
        )


# ---------------------------------------------------------------------------
# OCR — extract raw text from PDF or image
# ---------------------------------------------------------------------------

def _ocr_extract(file_path: str) -> str:
    """Extract text from a PDF or image file using available OCR tools."""
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return _ocr_pdf(path)
    elif suffix in (".png", ".jpg", ".jpeg", ".tiff", ".bmp"):
        return _ocr_image(path)
    elif suffix == ".txt":
        # Plain text — read directly (useful for testing)
        return path.read_text(encoding="utf-8")
    else:
        raise ValueError(f"Unsupported file type: {suffix}")


def _ocr_pdf(path: Path) -> str:
    """Extract text from PDF, trying PyMuPDF first, then Tesseract OCR."""
    # 1. Try PyMuPDF first (fast, native text extraction, no system binaries needed)
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(str(path))
        texts = [page.get_text() for page in doc]
        full_text = "\n\n".join(texts).strip()
        
        # If the PDF contains a reasonable amount of text, return it directly.
        # This prevents breaking on text-based PDFs when Poppler/Tesseract are missing.
        if len(full_text) > 50:
            return full_text
    except Exception as e:
        logger.warning(f"PyMuPDF fallback failed: {e}")

    # 2. If PDF was an image or PyMuPDF failed, fall back to OCR
    try:
        from pdf2image import convert_from_path
        import pytesseract

        images = convert_from_path(str(path))
        texts = []
        for img in images:
            text = pytesseract.image_to_string(img, lang="fra+eng")
            texts.append(text)
        return "\n\n".join(texts)
    except Exception as e:
        raise RuntimeError(
            "OCR extraction failed for image-based PDF. This often happens natively on Windows "
            "because Poppler (for pdf2image) or Tesseract are not installed or not in PATH.\n"
            "To fix, either run the project via Docker (where it is pre-installed) or install "
            f"Poppler and Tesseract on your host system. Error details: {e}"
        )


def _ocr_image(path: Path) -> str:
    """Extract text from an image using pytesseract."""
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(str(path))
        return pytesseract.image_to_string(img, lang="fra+eng")
    except Exception as e:
        raise RuntimeError(
            "OCR extraction failed for Image. This often happens natively on Windows "
            "because Tesseract executable is not installed or not in PATH.\n"
            "To fix, either run the project via Docker or install Tesseract. "
            f"Error details: {e}"
        )


# ---------------------------------------------------------------------------
# LLM Extraction prompt
# ---------------------------------------------------------------------------

_EXTRACTION_SYSTEM_PROMPT = """You are an expert Accounts Payable invoice data extraction agent.
You receive raw OCR text from a French supplier invoice and must extract structured data.

IMPORTANT: This is a French business document. Look for:
- TVA (VAT) numbers with FR prefix
- SIRET numbers (14 digits)
- IBAN/BIC for French banks
- PO / Bon de commande references
- Amounts: HT (hors taxes), TVA, TTC (toutes taxes comprises)

Return a JSON object with EXACTLY these fields (use null if not found):
{
    "supplier_name": "string",
    "vat_number": "string (e.g. FR82123456789)",
    "siret": "string (14 digits)",
    "iban": "string",
    "bic": "string",
    "po_number": "string (e.g. PO-2025-001)",
    "invoice_number": "string",
    "invoice_date": "YYYY-MM-DD",
    "line_items": [
        {"description": "string", "quantity": number, "unit_price": number, "total": number}
    ],
    "total_ht": number,
    "tva_rate": number (e.g. 20.0 for 20%),
    "tva_amount": number,
    "total_ttc": number,
    "currency": "EUR"
}

Return ONLY the JSON object, no markdown fences or additional text."""


# ---------------------------------------------------------------------------
# Agent node function
# ---------------------------------------------------------------------------

def ingestion_node(state: InvoiceProcessingState) -> dict[str, Any]:
    """LangGraph node: extract structured data from an invoice file.

    Reads state["file_path"], performs OCR, then uses LLM to extract fields.
    """
    file_path = state.get("file_path", "")
    errors: list[str] = list(state.get("errors", []))

    if not file_path:
        errors.append("No file_path provided in state")
        return {"status": "error", "errors": errors}

    try:
        # Step 1: OCR
        logger.info("Running OCR on %s", file_path)
        raw_text = _ocr_extract(file_path)
        logger.info("OCR extracted %d characters", len(raw_text))

        # Step 2: LLM extraction
        llm = _get_llm()
        messages = [
            SystemMessage(content=_EXTRACTION_SYSTEM_PROMPT),
            HumanMessage(content=f"Extract invoice data from the following OCR text:\n\n{raw_text}"),
        ]
        response = llm.invoke(messages)
        content = response.content.strip()

        # Clean up potential markdown fences
        if content.startswith("```"):
            content = content.split("\n", 1)[1]  # Remove first line
        if content.endswith("```"):
            content = content.rsplit("\n", 1)[0]  # Remove last line
        if content.startswith("json"):
            content = content[4:].strip()

        extracted = json.loads(content)
        extracted["raw_ocr_text"] = raw_text

        logger.info("Extracted invoice data: supplier=%s, invoice=%s",
                     extracted.get("supplier_name"), extracted.get("invoice_number"))

        return {
            "extracted_data": extracted,
            "extraction_confidence": 0.85,  # placeholder
            "status": "ingested",
            "errors": errors,
        }

    except json.JSONDecodeError as e:
        errors.append(f"Failed to parse LLM extraction output: {e}")
        return {"status": "error", "errors": errors}
    except Exception as e:
        errors.append(f"Ingestion failed: {e}")
        return {"status": "error", "errors": errors}
