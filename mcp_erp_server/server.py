"""FastMCP server exposing ERP validation and invoice creation tools.

Run standalone:
    python -m mcp_erp_server.server          # stdio transport
    python -m mcp_erp_server.server --sse     # SSE transport on port 8001
"""

from __future__ import annotations

import json
import sys
from datetime import date

from mcp.server.fastmcp import FastMCP

from .erp_database import (
    create_invoice,
    find_purchase_order,
    find_supplier_bank,
    find_supplier_by_name,
    find_supplier_by_siret,
    find_supplier_by_vat,
    find_supplier_policy,
    init_database,
)

# Initialize the database on import
init_database()

# Create the FastMCP server
mcp = FastMCP(
    "erp-server",
    instructions="MCP server for ERP operations - validates supplier data and creates invoices",
)


# ---------------------------------------------------------------------------
# Tool 1: Validate VAT Number
# ---------------------------------------------------------------------------
@mcp.tool()
def validate_vat(vat_number: str) -> str:
    """Validate a VAT number against the ERP supplier master data.

    Args:
        vat_number: The EU VAT number to validate (e.g. FR82123456789)

    Returns:
        JSON with validation result: {valid, company_name, message}
    """
    supplier = find_supplier_by_vat(vat_number.strip().upper())
    if supplier:
        return json.dumps({
            "valid": True,
            "company_name": supplier["name"],
            "message": f"VAT {vat_number} is registered to {supplier['name']}",
        })
    return json.dumps({
        "valid": False,
        "company_name": None,
        "message": f"VAT {vat_number} not found in ERP supplier master data",
    })


# ---------------------------------------------------------------------------
# Tool 2: Validate SIRET
# ---------------------------------------------------------------------------
@mcp.tool()
def validate_siret(siret: str) -> str:
    """Validate a French SIRET number against the ERP supplier master data.

    Args:
        siret: 14-digit French SIRET number

    Returns:
        JSON with validation result: {valid, company_name, address, message}
    """
    supplier = find_supplier_by_siret(siret.strip())
    if supplier:
        return json.dumps({
            "valid": True,
            "company_name": supplier["name"],
            "address": f"{supplier['address']}, {supplier['city']}, {supplier['country']}",
            "message": f"SIRET {siret} is valid for {supplier['name']}",
        })
    return json.dumps({
        "valid": False,
        "company_name": None,
        "address": None,
        "message": f"SIRET {siret} not found in ERP supplier master data",
    })


# ---------------------------------------------------------------------------
# Tool 3: Validate Supplier Bank Details
# ---------------------------------------------------------------------------
@mcp.tool()
def validate_supplier_bank(iban: str, bic: str) -> str:
    """Validate supplier bank details (IBAN and BIC) against ERP master data.

    Args:
        iban: International Bank Account Number
        bic: Bank Identifier Code (SWIFT)

    Returns:
        JSON with validation result: {valid, bank_name, supplier_name, message}
    """
    supplier = find_supplier_bank(iban.strip().replace(" ", ""), bic.strip().upper())
    if supplier:
        return json.dumps({
            "valid": True,
            "supplier_name": supplier["name"],
            "message": f"Bank details match supplier {supplier['name']}",
        })
    return json.dumps({
        "valid": False,
        "supplier_name": None,
        "message": f"IBAN/BIC combination not found in ERP supplier bank records",
    })


# ---------------------------------------------------------------------------
# Tool 4: Validate Purchase Order
# ---------------------------------------------------------------------------
@mcp.tool()
def validate_purchase_order(po_number: str) -> str:
    """Validate a Purchase Order number exists in the ERP and is in a receivable state.

    Args:
        po_number: The PO reference number (e.g. PO-2025-001)

    Returns:
        JSON with: {valid, status, total_amount, currency, description, message}
    """
    po = find_purchase_order(po_number.strip())
    if not po:
        return json.dumps({
            "valid": False,
            "status": None,
            "total_amount": None,
            "message": f"Purchase Order {po_number} not found in ERP",
        })

    receivable_statuses = {"open", "partially_received"}
    is_valid = po["status"] in receivable_statuses

    return json.dumps({
        "valid": is_valid,
        "status": po["status"],
        "total_amount": po["total_amount"],
        "currency": po["currency"],
        "description": po["description"],
        "message": (
            f"PO {po_number} is {po['status']} (amount: {po['total_amount']} {po['currency']})"
            if is_valid
            else f"PO {po_number} exists but status is '{po['status']}' — cannot receive invoices"
        ),
    })


# ---------------------------------------------------------------------------
# Tool 5: Get Supplier Details
# ---------------------------------------------------------------------------
@mcp.tool()
def get_supplier_details(supplier_name: str) -> str:
    """Look up a supplier by name in the ERP master data.

    Args:
        supplier_name: Full or partial supplier name to search for

    Returns:
        JSON with supplier details or not-found message
    """
    supplier = find_supplier_by_name(supplier_name.strip())
    if supplier:
        return json.dumps({
            "found": True,
            "supplier": {
                "id": supplier["id"],
                "name": supplier["name"],
                "vat_number": supplier["vat_number"],
                "siret": supplier["siret"],
                "iban": supplier["iban"],
                "bic": supplier["bic"],
                "address": f"{supplier['address']}, {supplier['city']}, {supplier['country']}",
                "active": bool(supplier["active"]),
            },
        })
    return json.dumps({
        "found": False,
        "supplier": None,
        "message": f"No active supplier found matching '{supplier_name}'",
    })


# ---------------------------------------------------------------------------
# Tool 5.5: Validate Supplier Policy
# ---------------------------------------------------------------------------
@mcp.tool()
def validate_supplier_policy(
    vat_number: str,
    po_number: str = "",
    total_amount: float = 0.0,
    currency: str = "EUR",
) -> str:
    """Validate invoice details against the supplier's policies in the ERP.

    Checks:
      - Invoice amount vs max allowed cap
      - PO requirement (unless supplier allows PO-free up to a limit)
      - Currency match against supplier policy
      - Whether the amount triggers a manual approval requirement

    Args:
        vat_number: Supplier VAT number used to identify the supplier
        po_number: The PO number present on the invoice (if any)
        total_amount: The total amount (TTC) of the invoice
        currency: Currency code on the invoice (default EUR)

    Returns:
        JSON with:
          valid (bool), requires_approval (bool), payment_terms_days (int),
          policy_details (dict), message (str)
    """
    supplier = find_supplier_by_vat(vat_number.strip().upper())
    if not supplier:
        return json.dumps({
            "valid": False,
            "requires_approval": False,
            "payment_terms_days": None,
            "policy_details": {},
            "message": f"Cannot validate policy: supplier with VAT {vat_number} not found",
        })

    policy = find_supplier_policy(supplier["id"])
    if not policy:
        return json.dumps({
            "valid": True,
            "requires_approval": False,
            "payment_terms_days": 30,
            "policy_details": {},
            "message": f"No specific policy configured for {supplier['name']}. Proceeding with defaults.",
        })

    policy_details = {
        "requires_po": bool(policy["requires_po"]),
        "max_amount": policy["max_amount"],
        "allowed_without_po_max": policy["allowed_without_po_max"],
        "currency": policy["currency"],
        "approval_required_above": policy["approval_required_above"],
        "payment_terms_days": policy["payment_terms_days"],
        "notes": policy["notes"],
    }

    # --- Check 1: Currency mismatch ---
    if currency.strip().upper() != policy["currency"].strip().upper():
        return json.dumps({
            "valid": False,
            "requires_approval": False,
            "payment_terms_days": policy["payment_terms_days"],
            "policy_details": policy_details,
            "message": (
                f"Currency mismatch: invoice is in {currency.upper()} but "
                f"{supplier['name']} policy requires {policy['currency']}."
            ),
        })

    # --- Check 2: Invoice amount exceeds hard cap ---
    if policy["max_amount"] and total_amount > policy["max_amount"]:
        return json.dumps({
            "valid": False,
            "requires_approval": False,
            "payment_terms_days": policy["payment_terms_days"],
            "policy_details": policy_details,
            "message": (
                f"Invoice amount {total_amount:.2f} {currency} exceeds the maximum allowed "
                f"{policy['max_amount']:.2f} {policy['currency']} for {supplier['name']}."
            ),
        })

    # --- Check 3: PO requirement ---
    has_po = bool(po_number.strip())
    if policy["requires_po"] and not has_po:
        # Strict PO suppliers — no invoice without a PO
        return json.dumps({
            "valid": False,
            "requires_approval": False,
            "payment_terms_days": policy["payment_terms_days"],
            "policy_details": policy_details,
            "message": (
                f"{supplier['name']} policy requires a valid Purchase Order. "
                "No PO number was provided on the invoice."
            ),
        })
    elif not policy["requires_po"] and not has_po:
        # PO-optional supplier — allowed only up to allowed_without_po_max
        po_free_limit = policy["allowed_without_po_max"]
        if po_free_limit and total_amount > po_free_limit:
            return json.dumps({
                "valid": False,
                "requires_approval": False,
                "payment_terms_days": policy["payment_terms_days"],
                "policy_details": policy_details,
                "message": (
                    f"{supplier['name']} allows PO-free invoices only up to "
                    f"{po_free_limit:.2f} {policy['currency']}. "
                    f"This invoice amount {total_amount:.2f} {currency} exceeds that limit. "
                    "Please attach a PO."
                ),
            })

    # --- Check 4: Approval threshold ---
    requires_approval = bool(
        policy["approval_required_above"]
        and total_amount > policy["approval_required_above"]
    )

    approval_note = ""
    if requires_approval:
        approval_note = (
            f" NOTE: Amount {total_amount:.2f} {currency} exceeds the approval threshold "
            f"({policy['approval_required_above']:.2f} {policy['currency']}). "
            "Manual approval is required before payment."
        )

    return json.dumps({
        "valid": True,
        "requires_approval": requires_approval,
        "payment_terms_days": policy["payment_terms_days"],
        "policy_details": policy_details,
        "message": (
            f"Invoice passes all supplier policies for {supplier['name']}."
            + approval_note
        ),
    })


# ---------------------------------------------------------------------------
# Tool 6: Create ERP Invoice
# ---------------------------------------------------------------------------
@mcp.tool()
def create_erp_invoice(
    supplier_name: str,
    vat_number: str,
    siret: str,
    po_number: str,
    invoice_number: str,
    invoice_date: str,
    total_ht: float,
    tva_amount: float,
    total_ttc: float,
    line_items: str = "[]",
    currency: str = "EUR",
    notes: str = "",
) -> str:
    """Create an invoice in the ERP system.

    This should only be called after all validations (VAT, SIRET, bank, PO) have passed.

    Args:
        supplier_name: Name of the supplier
        vat_number: Supplier VAT number
        siret: Supplier SIRET number
        po_number: Associated Purchase Order number
        invoice_number: The supplier's invoice reference
        invoice_date: Invoice date in ISO format (YYYY-MM-DD)
        total_ht: Total amount excluding tax (Hors Taxes)
        tva_amount: VAT/TVA amount
        total_ttc: Total amount including tax (Toutes Taxes Comprises)
        line_items: JSON string of line items (optional)
        currency: Currency code (default EUR)
        notes: Internal comments or notes attached to the invoice

    Returns:
        JSON with: {success, erp_invoice_id, message}
    """
    # Resolve supplier by VAT
    supplier = find_supplier_by_vat(vat_number.strip().upper())
    if not supplier:
        return json.dumps({
            "success": False,
            "erp_invoice_id": None,
            "message": f"Cannot create invoice: supplier with VAT {vat_number} not found",
        })

    # Verify PO exists and is receivable
    po = find_purchase_order(po_number.strip())
    if not po:
        return json.dumps({
            "success": False,
            "erp_invoice_id": None,
            "message": f"Cannot create invoice: PO {po_number} not found",
        })
    if po["status"] not in ("open", "partially_received"):
        return json.dumps({
            "success": False,
            "erp_invoice_id": None,
            "message": f"Cannot create invoice: PO {po_number} is '{po['status']}'",
        })

    # Create the invoice
    erp_invoice_id = create_invoice(
        supplier_id=supplier["id"],
        po_number=po_number,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        total_ht=total_ht,
        tva_amount=tva_amount,
        total_ttc=total_ttc,
        currency=currency,
        notes=notes,
    )

    return json.dumps({
        "success": True,
        "erp_invoice_id": erp_invoice_id,
        "message": f"Invoice {invoice_number} posted to ERP as {erp_invoice_id}",
    })


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if "--sse" in sys.argv:
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")
