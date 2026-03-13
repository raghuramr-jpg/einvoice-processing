"""Ingestion Agent — OCR + LLM extraction of structured invoice data."""

from __future__ import annotations

import base64
import json
import logging
import os
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
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
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        # Strip /v1 if present for ChatOllama
        base_url = base_url.replace("/v1/", "").replace("/v1", "")
        model_name = os.getenv("LLM_MODEL", "qwen2.5-vl")
        logger.info("Using Ollama LLM (%s) at: %s", model_name, base_url)
        return ChatOllama(
            model=model_name,
            base_url=base_url,
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
# Image Preprocessing — convert PDF/Image to base64
# ---------------------------------------------------------------------------

def _file_to_base64_images(file_path: str) -> list[str]:
    """Convert a PDF or image file into a list of base64-encoded strings (one per page)."""
    path = Path(file_path)
    suffix = path.suffix.lower()
    images_base64 = []

    if suffix == ".pdf":
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(str(path))
            for page in doc:
                pix = page.get_pixmap()
                img_data = pix.tobytes("png")
                images_base64.append(base64.b64encode(img_data).decode("utf-8"))
        except Exception as e:
            logger.warning(f"Failed to convert PDF to images: {e}")
            raise
    elif suffix in (".png", ".jpg", ".jpeg", ".tiff", ".bmp"):
        try:
            with open(path, "rb") as f:
                img_data = f.read()
                images_base64.append(base64.b64encode(img_data).decode("utf-8"))
        except Exception as e:
            logger.warning(f"Failed to read image file: {e}")
            raise
    else:
        raise ValueError(f"Unsupported file type: {suffix}")

    return images_base64


def _ocr_extract_text_fallback(file_path: str) -> str:
    """Fallback text extraction for RAG indexing."""
    path = Path(file_path)
    try:
        import fitz
        doc = fitz.open(str(path))
        return "\n\n".join(page.get_text() for page in doc).strip()
    except Exception:
        return ""


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

_EXTRACTION_SYSTEM_PROMPT = """You are an expert Accounts Payable invoice data extraction agent using a Vision-Language Model.
You receive images of a French supplier invoice and must extract structured data.

IMPORTANT: Use SEMANTIC LABEL IDENTIFICATION. This means:
1. Identify labels based on their MEANING, not just exact text (e.g., "TOTAL TTC", "Net a payer", "Amount Due", "Total" all map to total_ttc).
2. Distinguish between SUPPLIER (vendor) and CUSTOMER (bill-to) information by analyzing the layout (supplier is usually at the top or header).
3. Extract information directly from the visual context.

This is a French business document. Look for:
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
    """
    file_path = state.get("file_path", "")
    errors: list[str] = list(state.get("errors", []))

    if not file_path:
        errors.append("No file_path provided in state")
        return {"status": "error", "errors": errors}

    try:
        # Step 1: Convert file to images for VLM
        logger.info("Converting %s to images for VLM", file_path)
        images_base64 = []
        try:
            images_base64 = _file_to_base64_images(file_path)
            logger.info("Converted to %d images", len(images_base64))
        except Exception as e:
            logger.warning("Conversion to images failed: %s. Will proceed to text-only fallback.", e)

        # Step 2: Fallback text extraction (needed for RAG anyway)
        raw_text_fallback = _ocr_extract_text_fallback(file_path)
        logger.info("Fallback OCR extracted %d characters", len(raw_text_fallback))

        # Step 3: Retrieve candidate suppliers from Vector DB (RAG)
        logger.info("Retrieving candidate suppliers from Vector DB")
        candidate_suppliers = []
        try:
            base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
            embeddings_url = base_url.replace("/v1/", "").replace("/v1", "")
            
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
            
            query_text = raw_text_fallback[:1000] if raw_text_fallback else "unknown supplier"
            docs = vector_store.similarity_search(query_text, k=3)
            candidate_suppliers = [doc.metadata for doc in docs]
        except Exception as e:
            logger.warning(f"Failed to retrieve candidate suppliers from RAG: {e}")

        llm = _get_llm()
        candidates_json = json.dumps(candidate_suppliers, indent=2)
        
        # Base system prompt for both vision and text
        base_prompt = _EXTRACTION_SYSTEM_PROMPT + f"""
        
CANDIDATE SUPPLIERS FROM ERP:
{candidates_json}

If the vendor appears to be one of these Candidate Suppliers (even if spelled differently, abbreviated, or missing details), you MUST prioritize extracting the exact Name, vat_number, and siret from the Candidate Supplier record rather than guessing from the document content.
"""
        
        extracted_obj = None
        
        # Try Vision-only first if we have images and the model is supposed to be vision
        model_name = os.getenv("LLM_MODEL", "qwen2.5-vl")
        if images_base64 and ("vl" in model_name or "vision" in model_name):
            try:
                logger.info("Attempting vision-based extraction with %s", model_name)
                # Prepare multimodal message
                content = [{"type": "text", "text": "Extract all relevant fields from this invoice image(s). Use semantic label identification to find the correct data even if labels vary across formats."}]
                for b64_img in images_base64:
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64_img}"}
                    })

                structured_llm = llm.with_structured_output(InvoiceExtractionSchema)
                extracted_obj = structured_llm.invoke([
                    SystemMessage(content=base_prompt),
                    HumanMessage(content=content)
                ])
                
                if extracted_obj and extracted_obj.supplier_name:
                    logger.info("Vision-based extraction succeeded for %s", extracted_obj.supplier_name)
                else:
                    logger.warning("Vision-based extraction returned empty/partial result. Trying text-only fallback.")
                    extracted_obj = None
            except Exception as e:
                logger.warning("Vision-based extraction failed: %s. Falling back to text-only.", e)

        # Fallback to Text-only extraction
        if not extracted_obj:
            text_model_name = os.getenv("LLM_MODEL_TEXT", "qwen2.5")
            logger.info("Attempting text-based extraction with %s", text_model_name)
            
            # Switch to text-only LLM if specified or use the current one
            if text_model_name != model_name:
                base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
                base_url = base_url.replace("/v1/", "").replace("/v1", "")
                llm = ChatOllama(
                    model=text_model_name,
                    base_url=base_url,
                    temperature=0,
                )

            structured_llm = llm.with_structured_output(InvoiceExtractionSchema)
            prompt_text = f"Extract invoice data from the following OCR text using semantic label identification:\n\n{raw_text_fallback}"
            extracted_obj = structured_llm.invoke([
                SystemMessage(content=base_prompt),
                HumanMessage(content=prompt_text)
            ])

        if not extracted_obj:
            raise ValueError("LLM failed to return a structured response after all attempts.")
            
        extracted = extracted_obj.model_dump()
        extracted["raw_ocr_text"] = raw_text_fallback
        
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
