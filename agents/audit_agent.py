"""Audit Agent — Systematically verify extraction confidence."""

import logging
from typing import Any
from .state import InvoiceProcessingState

logger = logging.getLogger(__name__)

def audit_node(state: InvoiceProcessingState) -> dict[str, Any]:
    """LangGraph node: calculate a reliable confidence score based on data completeness and math."""
    extracted = state.get("extracted_data", {})
    if not extracted:
        return {"extraction_confidence": 0.0}

    score = 1.0
    deductions = []

    # 1. Mandatory Fields Check (-0.20 each)
    mandatory_fields = ["supplier_name", "invoice_number", "total_ttc", "invoice_date"]
    for field in mandatory_fields:
        val = extracted.get(field)
        if val is None or (isinstance(val, str) and not val.strip()):
            score -= 0.20
            deductions.append(f"Missing mandatory field: {field}")

    # 2. Mathematical Audit (-0.20)
    total_ht = extracted.get("total_ht")
    tva_amount = extracted.get("tva_amount")
    total_ttc = extracted.get("total_ttc")

    if total_ht is not None and tva_amount is not None and total_ttc is not None:
        # Check if HT + TVA approx equals TTC (allowing for small rounding errors)
        if abs((total_ht + tva_amount) - total_ttc) > 0.1:
            score -= 0.20
            deductions.append("Mathematical inconsistency: total_ht + tva_amount != total_ttc")
    else:
        # If any are missing but not all (partial math), deduct
        if any([total_ht, tva_amount, total_ttc]) and not all([total_ht, tva_amount, total_ttc]):
             score -= 0.10
             deductions.append("Incomplete tax totals for mathematical audit")

    # 3. Secondary Fields (-0.05 each)
    secondary_fields = ["iban", "bic", "vat_number", "siret", "po_number"]
    for field in secondary_fields:
        val = extracted.get(field)
        if val is None or (isinstance(val, str) and not val.strip()):
            score -= 0.05
            deductions.append(f"Missing secondary field: {field}")

    # Ensure score doesn't go below 0
    final_score = max(0.0, round(score, 2))
    
    if deductions:
        logger.info("Audit Agent deductions for %s: %s", extracted.get("invoice_number"), ", ".join(deductions))
        logger.info("Final Audit Confidence: %.2f", final_score)
    else:
        logger.info("Audit Agent: Perfect extraction confidence (1.0)")

    return {
        "extraction_confidence": final_score
    }
