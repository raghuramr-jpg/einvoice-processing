"""LangGraph workflow — orchestrates ingestion → validation → process/reject."""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, StateGraph

from .ingestion_agent import ingestion_node
from .processing_agent import process_node, reject_node
from .state import InvoiceProcessingState
from .validation_agent import validation_node

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Conditional routing
# ---------------------------------------------------------------------------

def _should_continue_after_ingestion(state: InvoiceProcessingState) -> str:
    """Route after ingestion: continue to validation or stop on error."""
    if state.get("status") == "error":
        return "error_end"
    return "validate"


def _should_process_or_reject(state: InvoiceProcessingState) -> str:
    """Route after validation: process if all passed and confidence > 0.8, reject otherwise."""
    confidence = state.get("extraction_confidence", 1.0)
    if state.get("all_validations_passed") and confidence > 0.8:
        return "process"
    return "reject"


# ---------------------------------------------------------------------------
# Error handler node
# ---------------------------------------------------------------------------

def error_node(state: InvoiceProcessingState) -> dict[str, Any]:
    """Terminal node for unrecoverable errors."""
    errors = state.get("errors", [])
    logger.error("Workflow ended with errors: %s", errors)
    return {
        "status": "error",
        "processing_result": {
            "success": False,
            "message": "Workflow failed",
            "errors": errors,
        },
    }


# ---------------------------------------------------------------------------
# Build the graph
# ---------------------------------------------------------------------------

def build_invoice_graph() -> StateGraph:
    """Construct and compile the LangGraph invoice processing workflow.

    Flow:
        ingest → [error? → error_end] → validate → [all valid? → process | reject]
    """
    workflow = StateGraph(InvoiceProcessingState)

    # Add nodes
    workflow.add_node("ingest", ingestion_node)
    workflow.add_node("validate", validation_node)
    workflow.add_node("process", process_node)
    workflow.add_node("reject", reject_node)
    workflow.add_node("error_end", error_node)

    # Set entry point
    workflow.set_entry_point("ingest")

    # Edges
    workflow.add_conditional_edges(
        "ingest",
        _should_continue_after_ingestion,
        {
            "validate": "validate",
            "error_end": "error_end",
        },
    )

    workflow.add_conditional_edges(
        "validate",
        _should_process_or_reject,
        {
            "process": "process",
            "reject": "reject",
        },
    )

    # Terminal edges
    workflow.add_edge("process", END)
    workflow.add_edge("reject", END)
    workflow.add_edge("error_end", END)

    return workflow.compile()


# Pre-compiled graph instance
invoice_graph = build_invoice_graph()


# ---------------------------------------------------------------------------
# Convenience runner
# ---------------------------------------------------------------------------

async def process_invoice(file_path: str) -> InvoiceProcessingState:
    """Run the full invoice processing workflow.

    Args:
        file_path: Path to the invoice PDF or image file.

    Returns:
        Final InvoiceProcessingState with all results.
    """
    initial_state: InvoiceProcessingState = {
        "file_path": file_path,
        "status": "pending",
        "errors": [],
    }

    logger.info("Starting invoice processing for: %s", file_path)
    result = await invoice_graph.ainvoke(initial_state)
    logger.info("Invoice processing complete: status=%s", result.get("status"))

    return result
