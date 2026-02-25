"""End-to-end test for the LangGraph invoice processing workflow.

This test bypasses OCR/LLM by directly injecting extracted data into the state,
then runs the validation → process/reject part of the graph.
"""

import json
from pathlib import Path

import pytest

from mcp_erp_server.erp_database import init_database


@pytest.fixture(autouse=True)
def setup_db(tmp_path):
    db_path = tmp_path / "test_erp.db"
    init_database(db_path)
    import mcp_erp_server.erp_database as db_mod
    original_path = db_mod._DB_PATH
    db_mod._DB_PATH = db_path
    yield
    db_mod._DB_PATH = original_path


class TestProcessingNode:
    def test_successful_invoice_creation(self):
        """Invoice should be created in ERP when all data is valid."""
        from agents.processing_agent import process_node

        state = {
            "extracted_data": {
                "supplier_name": "TechnoVision SAS",
                "vat_number": "FR82123456789",
                "siret": "12345678900014",
                "iban": "FR7630006000011234567890189",
                "bic": "BNPAFRPP",
                "po_number": "PO-2025-001",
                "invoice_number": "FAC-2025-0042",
                "invoice_date": "2025-02-15",
                "line_items": [
                    {"description": "Server", "quantity": 2, "unit_price": 3500, "total": 7000},
                ],
                "total_ht": 12100.00,
                "tva_rate": 20.0,
                "tva_amount": 2420.00,
                "total_ttc": 14520.00,
                "currency": "EUR",
            },
            "errors": [],
        }

        result = process_node(state)
        assert result["status"] == "processed"
        assert result["processing_result"]["success"] is True
        assert result["processing_result"]["erp_invoice_id"].startswith("ERP-INV-")

    def test_invalid_supplier_rejects(self):
        """Invoice creation should fail for unknown supplier."""
        from agents.processing_agent import process_node

        state = {
            "extracted_data": {
                "supplier_name": "Unknown Corp",
                "vat_number": "FR00000000000",
                "siret": "00000000000000",
                "po_number": "PO-2025-001",
                "invoice_number": "FAC-FAKE",
                "invoice_date": "2025-02-20",
                "total_ht": 100, "tva_amount": 20, "total_ttc": 120,
                "currency": "EUR",
            },
            "errors": [],
        }

        result = process_node(state)
        assert result["status"] == "error"
        assert result["processing_result"]["success"] is False


class TestRejectNode:
    def test_rejection_report(self):
        """Reject node should produce a proper rejection report."""
        from agents.processing_agent import reject_node

        state = {
            "extracted_data": {
                "invoice_number": "FAC-2025-0099",
                "supplier_name": "Unknown Corp",
            },
            "validation_results": [
                {"field": "supplier", "valid": True, "message": "OK", "details": {}},
                {"field": "vat_number", "valid": False, "message": "VAT not found", "details": {}},
                {"field": "siret", "valid": False, "message": "SIRET not found", "details": {}},
                {"field": "supplier_bank", "valid": True, "message": "OK", "details": {}},
                {"field": "purchase_order", "valid": False, "message": "PO not found", "details": {}},
            ],
            "errors": [],
        }

        result = reject_node(state)
        assert result["status"] == "rejected"
        assert result["processing_result"]["rejected"] is True
        assert result["processing_result"]["failure_count"] == 3
        assert len(result["processing_result"]["failures"]) == 3
