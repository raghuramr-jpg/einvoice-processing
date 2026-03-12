"""Ingestion Agent — OCR + LLM extraction of structured invoice data."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_chroma import Chroma
from langchain_community.embeddings import OllamaEmbeddings
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from .state import InvoiceProcessingState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LLM configuration
# ---------------------------------------------------------------------------

def _get_llm() -> ChatOpenAI:
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    
    if provider == "ollama":
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        logger.info("Using Ollama LLM at: %s", base_url)
        # Use LangChain's ChatOpenAI but point it to Ollama's local OpenAI-compatible endpoint
        return ChatOpenAI(
            model=os.getenv("LLM_MODEL", "llama3.1"),
            base_url=base_url,
            api_key="ollama",  # API key is required by the client but ignored by Ollama
            temperature=0,
        )
    else:
        logger.info("Using OpenAI LLM")
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

class LineItem(BaseModel):
    description: str | None = Field(description="Description of the item", default=None)
    quantity: float | None = Field(description="Quantity of the item", default=None)
    unit_price: float | None = Field(description="Unit price of the item", default=None)
    total: float | None = Field(description="Total price for the line item", default=None)

class InvoiceExtractionSchema(BaseModel):
    supplier_name: str | None = Field(description="Name of the supplier", default=None)
    vat_number: str | None = Field(description="TVA (VAT) number with FR prefix e.g. FR82123456789", default=None)
    siret: str | None = Field(description="SIRET number (14 digits)", default=None)
    iban: str | None = Field(description="IBAN for the supplier account", default=None)
    bic: str | None = Field(description="BIC for the supplier account", default=None)
    po_number: str | None = Field(description="PO / Bon de commande reference e.g. PO-2025-001", default=None)
    invoice_number: str | None = Field(description="Invoice number", default=None)
    invoice_date: str | None = Field(description="Invoice date in YYYY-MM-DD format", default=None)
    line_items: list[LineItem] = Field(description="List of line items in the invoice", default_factory=list)
    total_ht: float | None = Field(description="Total hors taxes (HT)", default=None)
    tva_rate: float | None = Field(description="TVA percentage e.g. 20.0 for 20%", default=None)
    tva_amount: float | None = Field(description="TVA amount", default=None)
    total_ttc: float | None = Field(description="Total toutes taxes comprises (TTC)", default=None)
    currency: str | None = Field(description="Currency e.g. EUR", default="EUR")
    confidence_score: float = Field(
        description="Confidence score from 0.0 to 1.0. Start at 1.0. Subtract 0.20 for any major missing fields (e.g. SIRET, TVA, PO Number). Subtract 0.20 if math does not make sense. Subtract 0.10 for minor missing fields. If not an invoice, < 0.5",
        default=0.5
    )

_EXTRACTION_SYSTEM_PROMPT = """You are an expert Accounts Payable invoice data extraction agent.
You receive raw OCR text from a French supplier invoice and must extract structured data.

IMPORTANT: This is a French business document. Look for:
- TVA (VAT) numbers with FR prefix
- SIRET numbers (14 digits)
- IBAN/BIC for French banks
- PO / Bon de commande references
- Amounts: HT (hors taxes), TVA, TTC (toutes taxes comprises)

RULES FOR CONFIDENCE SCORE:
- Start at 1.0.
- Subtract 0.20 for ANY major missing fields (e.g. SIRET, TVA, PO Number).
- Subtract 0.20 if the math doesn't make sense (e.g., total_ht + tva_amount != total_ttc).
- Subtract 0.10 for minor missing fields (e.g., IBAN, line items not perfectly matching total).
- If the document does not look like an invoice at all, or most fields are null, score should be less than 0.5."""


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

        # Step 2: Retrieve candidate suppliers from Vector DB
        logger.info("Retrieving candidate suppliers from Vector DB")
        try:
            base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
            # Strip /v1 or /v1/ for OllamaEmbeddings which expects the base Ollama URL
            embeddings_url = base_url.replace("/v1/", "").replace("/v1", "")
            logger.info("Using Ollama Embeddings at: %s", embeddings_url)
            
            embeddings = OllamaEmbeddings(
                model="nomic-embed-text",
                base_url=embeddings_url
            )
            persist_dir = str(Path(__file__).parent.parent / "chroma_db")
            vector_store = Chroma(
                collection_name="erp_suppliers",
                embedding_function=embeddings,
                persist_directory=persist_dir
            )
            
            # Use the first 1000 characters (usually containing vendor header) for semantic search
            query_text = raw_text[:1000]
            docs = vector_store.similarity_search(query_text, k=3)
            candidate_suppliers = [doc.metadata for doc in docs]
        except Exception as e:
            logger.warning(f"Failed to retrieve candidate suppliers from RAG: {e}")
            candidate_suppliers = []

        llm = _get_llm()
        
        candidates_json = json.dumps(candidate_suppliers, indent=2)
        
        dynamic_system_prompt = _EXTRACTION_SYSTEM_PROMPT + f"""
        
CANDIDATE SUPPLIERS FROM ERP:
{candidates_json}

If the vendor in the OCR text appears to be one of these Candidate Suppliers (even if spelled differently, abbreviated, or missing details), you MUST prioritize extracting the exact Name, vat_number, and siret from the Candidate Supplier record rather than guessing from the OCR text.
"""
        # Create the LangGraph Agent with system instructions and strict schema output
        agent = create_react_agent(
            model=llm,
            tools=[],
            state_modifier=dynamic_system_prompt,
            response_format=InvoiceExtractionSchema,
        )
        
        input_state = {
            "messages": [HumanMessage(content=f"Extract invoice data from the following OCR text:\n\n{raw_text}")]
        }
        
        result = agent.invoke(input_state)
        
        # The result state contains "structured_response" with our parsed Pydantic object
        extracted_obj = result.get("structured_response")
        if not extracted_obj:
            raise ValueError("Agent failed to return a structured response.")
            
        extracted = extracted_obj.model_dump()
        extracted["raw_ocr_text"] = raw_text
        
        confidence = float(extracted.get("confidence_score", 0.5))

        logger.info("Extracted invoice data: supplier=%s, invoice=%s, confidence=%.2f",
                     extracted.get("supplier_name"), extracted.get("invoice_number"), confidence)

        return {
            "extracted_data": extracted,
            "extraction_confidence": confidence,
            "candidate_suppliers": candidate_suppliers,
            "status": "ingested",
            "errors": errors,
        }

    except Exception as e:
        msg = f"Ingestion failed: {e}"
        logger.error(msg, exc_info=True)
        errors.append(msg)
        return {"status": "error", "errors": errors}
