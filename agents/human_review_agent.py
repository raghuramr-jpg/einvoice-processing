"""Human Review Agent — prepares failed or low-confidence invoices for manual review."""

from __future__ import annotations

import logging
import os
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama

from .state import InvoiceProcessingState

logger = logging.getLogger(__name__)


def _get_llm():
    """Reuse LLM configuration from ingestion agent."""
    from .ingestion_agent import _get_llm
    return _get_llm()


_HUMAN_REVIEW_SYSTEM_PROMPT = """You are an Accounts Payable specialist assistant. 
Your task is to review the results of an automated invoice processing pipeline and explain to a human reviewer why this invoice was flagged for manual review.

You will be provided with:
1. Extraction confidence score (0.0 to 1.0).
2. Validation results (Success/Failure for specific fields like VAT, SIRET, PO, etc.).
3. Any system errors that occurred.

YOUR GOAL:
Write a concise, human-friendly summary (2-4 sentences) that explains the main issues. 
Be specific about which validations failed or why the extraction is considered low-confidence.
If it's a simple fix (e.g., "PO number was missing"), mention it.
"""

def human_review_node(state: InvoiceProcessingState) -> dict[str, Any]:
    """LangGraph node: prepare explanation for human review.
    """
    confidence = state.get("extraction_confidence", 1.0)
    validations = state.get("validation_results", [])
    errors = state.get("errors", [])
    
    # Identify failures
    failures = [v for v in validations if not v["valid"]]
    
    # Context for LLM
    context = {
        "confidence_score": confidence,
        "validation_failures": [
            {"field": f["field"], "message": f["message"]} for f in failures
        ],
        "system_errors": errors
    }
    
    llm = _get_llm()
    
    prompt = f"""Please review these processing results and provide a 2-4 sentence explanation for a human reviewer:

{context}
"""
    
    try:
        response = llm.invoke([
            SystemMessage(content=_HUMAN_REVIEW_SYSTEM_PROMPT),
            HumanMessage(content=prompt)
        ])
        
        notes = response.content if hasattr(response, 'content') else str(response)
    except Exception as e:
        logger.error(f"Failed to generate human review notes: {e}")
        notes = f"Manual review required due to failures. (LLM explanation failed: {e})"

    logger.info("Generated human review notes: %s", notes[:100] + "...")

    return {
        "human_review_notes": notes,
        "review_required": True,
        "status": "requires_review"
    }
