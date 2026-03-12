"""Validation Agent — calls MCP ERP tools to verify invoice data integrity."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from .ingestion_agent import _get_llm
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


class ValidationDetailModel(BaseModel):
    field: str = Field(description="The field being validated (e.g. 'supplier', 'vat_number', 'siret', 'supplier_bank', 'purchase_order', 'supplier_policy')")
    valid: bool = Field(description="True if validation passed, False otherwise")
    message: str = Field(description="Validation result message")
    details: dict[str, Any] = Field(description="Additional details returned by the tool", default_factory=dict)

class ValidationOutputSchema(BaseModel):
    validation_results: list[ValidationDetailModel] = Field(description="List of all validation checks performed")
    all_validations_passed: bool = Field(description="True if ALL validations passed, False otherwise")

# ---------------------------------------------------------------------------
# LangChain Tools wrapping MCP Tools
# ---------------------------------------------------------------------------

@tool
def validate_vat(vat_number: str) -> str:
    """Validate a VAT number against the ERP supplier master data.
    Args:
        vat_number: The EU VAT number (e.g. FR82123456789)
    """
    return json.dumps(_get_client().call_tool("validate_vat", {"vat_number": vat_number}))

@tool
def validate_siret(siret: str) -> str:
    """Validate a French SIRET number against the ERP supplier master data.
    Args:
        siret: 14-digit French SIRET number
    """
    return json.dumps(_get_client().call_tool("validate_siret", {"siret": siret}))

@tool
def validate_supplier_bank(iban: str, bic: str) -> str:
    """Validate supplier bank details (IBAN and BIC) against ERP master data."""
    return json.dumps(_get_client().call_tool("validate_supplier_bank", {"iban": iban, "bic": bic}))

@tool
def validate_purchase_order(po_number: str) -> str:
    """Validate a Purchase Order number exists in the ERP and is in a receivable state."""
    return json.dumps(_get_client().call_tool("validate_purchase_order", {"po_number": po_number}))

@tool
def get_supplier_details(supplier_name: str) -> str:
    """Look up a supplier by name in the ERP master data."""
    return json.dumps(_get_client().call_tool("get_supplier_details", {"supplier_name": supplier_name}))

@tool
def validate_supplier_policy(vat_number: str, po_number: str = "", total_amount: float = 0.0, currency: str = "EUR") -> str:
    """Validate invoice details against the supplier's policies in the ERP."""
    return json.dumps(_get_client().call_tool("validate_supplier_policy", {
        "vat_number": vat_number,
        "po_number": po_number,
        "total_amount": total_amount,
        "currency": currency,
    }))



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

    tools = [
        validate_vat,
        validate_siret,
        validate_supplier_bank,
        validate_purchase_order,
        get_supplier_details,
        validate_supplier_policy
    ]

    llm = _get_llm()

    system_prompt = """You are an expert ERP Validation Agent.
You receive extracted data from an invoice. Your job is to validate this data using the provided ERP tools.
Always perform the following checks if the data is available:
1. Valid supplier name or VAT/SIRET
2. Valid bank details (IBAN/BIC)
3. Valid Purchase Order (if present)
4. Supplier Policy (amount limits, PO requirements, etc) - ALWAYS pass the correct invoice currency, and ALWAYS check policy if VAT and Amount are known.

Take your time to call all necessary tools. 
Once you have gathered all the tool responses, compile them into a structured ValidationOutputSchema.
Ensure the 'details' field contains the parsed JSON from the tool if available as context.
"""

    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=system_prompt,
        response_format=ValidationOutputSchema,
    )
    
    extracted_json = json.dumps(extracted, indent=2)
    input_state = {
        "messages": [HumanMessage(content=f"Please validate this extracted invoice data:\n\n{extracted_json}")]
    }
    
    logger.info("Invoking Validation Agent with extracted data")
    
    try:
        result = agent.invoke(input_state)
        structured_response = result.get("structured_response")
        
        if not structured_response:
            raise ValueError("Validation agent did not return a structured response.")
            
        output_dict = structured_response.model_dump()
        all_passed = output_dict.get("all_validations_passed", False)
        
        logger.info(
            "Validation complete: %d checks performed (all_passed=%s)",
            len(output_dict.get("validation_results", [])),
            all_passed,
        )
        
        return {
            "validation_results": output_dict["validation_results"],
            "all_validations_passed": all_passed,
            "status": "validated",
            "errors": errors,
        }
        
    except Exception as e:
        msg = f"Validation Agent execution failed: {e}"
        logger.error(msg, exc_info=True)
        errors.append(msg)
        return {"status": "error", "errors": errors}
