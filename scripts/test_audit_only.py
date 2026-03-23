import logging
from agents.audit_agent import audit_node
from agents.state import InvoiceProcessingState

logging.basicConfig(level=logging.INFO)

def test_audit():
    # Test case: Missing supplier and PO, math is OK
    state: InvoiceProcessingState = {
        "extracted_data": {
            "supplier_name": None,
            "invoice_number": "INV-123",
            "total_ht": 100.0,
            "tva_amount": 20.0,
            "total_ttc": 120.0,
            "invoice_date": "2026-01-01",
            "po_number": None
        }
    }
    
    result = audit_node(state)
    confidence = result.get("extraction_confidence")
    
    print(f"Audit Result Confidence: {confidence}")
    
    # Expected deductions:
    # - Supplier Name (-0.20)
    # - PO Number (-0.05)
    # - SIRET (-0.05)
    # - IBAN (-0.05)
    # - BIC (-0.05)
    # - VAT (-0.05)
    # Total deduction: ~0.45 or so depending on secondary fields
    
    if confidence < 1.0:
        print("✅ SUCCESS: Audit Agent correctly downgraded confidence.")
    else:
        print("❌ FAILURE: Audit Agent returned 1.0 confidence for missing data.")

if __name__ == "__main__":
    test_audit()
