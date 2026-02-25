"""Validation Agent — calls MCP ERP tools to verify invoice data integrity."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from typing import Any

from .state import InvoiceProcessingState, ValidationDetail

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# MCP Client helper — calls ERP server tools via subprocess (stdio)
# ---------------------------------------------------------------------------

class McpErpClient:
    """Lightweight MCP client that calls the ERP server tools.

    For simplicity, we call the ERP database functions directly
    (in-process) rather than going over stdio/SSE. In production,
    this would use the full MCP client SDK over a network transport.
    """

    def __init__(self):
        # Import ERP database functions directly for in-process calls
        from mcp_erp_server.erp_database import init_database
        init_database()

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call an MCP tool and return the parsed JSON result."""
        # Import and call the tool function directly
        from mcp_erp_server import server as erp_server

        tool_fn = getattr(erp_server, tool_name, None)
        if tool_fn is None:
            raise ValueError(f"Unknown MCP tool: {tool_name}")

        result_json = tool_fn(**arguments)
        return json.loads(result_json)


def _get_client() -> McpErpClient:
    return McpErpClient()


# ---------------------------------------------------------------------------
# Validation checks
# ---------------------------------------------------------------------------

def _validate_vat(client: McpErpClient, vat_number: str) -> ValidationDetail:
    result = client.call_tool("validate_vat", {"vat_number": vat_number})
    return ValidationDetail(
        field="vat_number",
        valid=result["valid"],
        message=result["message"],
        details=result,
    )


def _validate_siret(client: McpErpClient, siret: str) -> ValidationDetail:
    result = client.call_tool("validate_siret", {"siret": siret})
    return ValidationDetail(
        field="siret",
        valid=result["valid"],
        message=result["message"],
        details=result,
    )


def _validate_bank(client: McpErpClient, iban: str, bic: str) -> ValidationDetail:
    result = client.call_tool("validate_supplier_bank", {"iban": iban, "bic": bic})
    return ValidationDetail(
        field="supplier_bank",
        valid=result["valid"],
        message=result["message"],
        details=result,
    )


def _validate_po(client: McpErpClient, po_number: str) -> ValidationDetail:
    result = client.call_tool("validate_purchase_order", {"po_number": po_number})
    return ValidationDetail(
        field="purchase_order",
        valid=result["valid"],
        message=result["message"],
        details=result,
    )


def _validate_supplier(client: McpErpClient, supplier_name: str) -> ValidationDetail:
    result = client.call_tool("get_supplier_details", {"supplier_name": supplier_name})
    return ValidationDetail(
        field="supplier",
        valid=result["found"],
        message=result.get("message", f"Supplier '{supplier_name}' found in ERP") if result["found"] else result.get("message", f"Supplier '{supplier_name}' not found"),
        details=result,
    )


# ---------------------------------------------------------------------------
# Agent node function
# ---------------------------------------------------------------------------

def validation_node(state: InvoiceProcessingState) -> dict[str, Any]:
    """LangGraph node: validate extracted invoice data against ERP via MCP tools.

    Checks: supplier name, VAT, SIRET, bank details (IBAN/BIC), PO.
    """
    extracted = state.get("extracted_data")
    errors: list[str] = list(state.get("errors", []))

    if not extracted:
        errors.append("No extracted_data available for validation")
        return {"status": "error", "errors": errors}

    client = _get_client()
    validations: list[ValidationDetail] = []

    # 1. Supplier name lookup
    supplier_name = extracted.get("supplier_name")
    if supplier_name:
        logger.info("Validating supplier: %s", supplier_name)
        validations.append(_validate_supplier(client, supplier_name))
    else:
        validations.append(ValidationDetail(
            field="supplier", valid=False,
            message="Supplier name not extracted from invoice", details={},
        ))

    # 2. VAT number
    vat = extracted.get("vat_number")
    if vat:
        logger.info("Validating VAT: %s", vat)
        validations.append(_validate_vat(client, vat))
    else:
        validations.append(ValidationDetail(
            field="vat_number", valid=False,
            message="VAT number not extracted from invoice", details={},
        ))

    # 3. SIRET
    siret = extracted.get("siret")
    if siret:
        logger.info("Validating SIRET: %s", siret)
        validations.append(_validate_siret(client, siret))
    else:
        validations.append(ValidationDetail(
            field="siret", valid=False,
            message="SIRET not extracted from invoice", details={},
        ))

    # 4. Bank details
    iban = extracted.get("iban")
    bic = extracted.get("bic")
    if iban and bic:
        logger.info("Validating bank: IBAN=%s, BIC=%s", iban, bic)
        validations.append(_validate_bank(client, iban, bic))
    else:
        validations.append(ValidationDetail(
            field="supplier_bank", valid=False,
            message="IBAN/BIC not fully extracted from invoice", details={},
        ))

    # 5. Purchase Order
    po = extracted.get("po_number")
    if po:
        logger.info("Validating PO: %s", po)
        validations.append(_validate_po(client, po))
    else:
        validations.append(ValidationDetail(
            field="purchase_order", valid=False,
            message="PO number not extracted from invoice", details={},
        ))

    all_passed = all(v["valid"] for v in validations)

    logger.info(
        "Validation complete: %d/%d passed (all_passed=%s)",
        sum(1 for v in validations if v["valid"]),
        len(validations),
        all_passed,
    )

    return {
        "validation_results": validations,
        "all_validations_passed": all_passed,
        "status": "validated",
        "errors": errors,
    }
