"""Processing Agent — creates invoice in ERP or generates rejection report."""

from __future__ import annotations

import json
import logging
from typing import Any

from .state import InvoiceProcessingState

logger = logging.getLogger(__name__)


def _get_client():
    """Reuse the MCP client from validation agent."""
    from .validation_agent import McpErpClient
    return McpErpClient()


# ---------------------------------------------------------------------------
# Processing: create ERP invoice
# ---------------------------------------------------------------------------

def process_node(state: InvoiceProcessingState) -> dict[str, Any]:
    """LangGraph node: create the invoice in ERP via MCP tool.

    Only called when all validations have passed.
    """
    extracted = state.get("extracted_data", {})
    errors: list[str] = list(state.get("errors", []))

    client = _get_client()

    try:
        result = client.call_tool("create_erp_invoice", {
            "supplier_name": extracted.get("supplier_name", ""),
            "vat_number": extracted.get("vat_number", ""),
            "siret": extracted.get("siret", ""),
            "po_number": extracted.get("po_number", ""),
            "invoice_number": extracted.get("invoice_number", ""),
            "invoice_date": extracted.get("invoice_date", ""),
            "total_ht": extracted.get("total_ht", 0),
            "tva_amount": extracted.get("tva_amount", 0),
            "total_ttc": extracted.get("total_ttc", 0),
            "line_items": json.dumps(extracted.get("line_items", [])),
            "currency": extracted.get("currency", "EUR"),
        })

        if result["success"]:
            logger.info("Invoice created in ERP: %s", result["erp_invoice_id"])
            return {
                "processing_result": result,
                "status": "processed",
                "errors": errors,
            }
        else:
            errors.append(result["message"])
            return {
                "processing_result": result,
                "status": "error",
                "errors": errors,
            }

    except Exception as e:
        errors.append(f"ERP invoice creation failed: {e}")
        return {
            "processing_result": {"success": False, "message": str(e)},
            "status": "error",
            "errors": errors,
        }


# ---------------------------------------------------------------------------
# Rejection: generate detailed report
# ---------------------------------------------------------------------------

def reject_node(state: InvoiceProcessingState) -> dict[str, Any]:
    """LangGraph node: generate rejection report when validations fail."""
    validations = state.get("validation_results", [])
    extracted = state.get("extracted_data", {})
    errors: list[str] = list(state.get("errors", []))

    failures = [v for v in validations if not v["valid"]]

    rejection_report = {
        "rejected": True,
        "invoice_number": extracted.get("invoice_number", "unknown"),
        "supplier_name": extracted.get("supplier_name", "unknown"),
        "failure_count": len(failures),
        "failures": [
            {
                "field": f["field"],
                "reason": f["message"],
            }
            for f in failures
        ],
        "recommendation": (
            "Please verify the following fields with the supplier and update "
            "ERP master data if needed before resubmitting the invoice."
        ),
    }

    logger.warning(
        "Invoice %s REJECTED: %d validation failures",
        extracted.get("invoice_number", "unknown"),
        len(failures),
    )

    return {
        "processing_result": rejection_report,
        "status": "rejected",
        "errors": errors,
    }
