"""Tests for the Validation Agent — verifies MCP tool calling and aggregation."""

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


class TestValidationAgent:
    def test_all_valid(self):
        """All validations should pass for a known supplier with correct data."""
        from agents.validation_agent import validation_node

        state = {
            "extracted_data": {
                "supplier_name": "TechnoVision",
                "vat_number": "FR82123456789",
                "siret": "12345678900014",
                "iban": "FR7630006000011234567890189",
                "bic": "BNPAFRPP",
                "po_number": "PO-2025-001",
            },
            "errors": [],
        }

        result = validation_node(state)
        assert result["all_validations_passed"] is True
        assert result["status"] == "validated"
        assert len(result["validation_results"]) == 5  # 5 checks
        for v in result["validation_results"]:
            assert v["valid"] is True

    def test_invalid_vat(self):
        """VAT validation should fail for unknown VAT number."""
        from agents.validation_agent import validation_node

        state = {
            "extracted_data": {
                "supplier_name": "TechnoVision",
                "vat_number": "FR00000000000",
                "siret": "12345678900014",
                "iban": "FR7630006000011234567890189",
                "bic": "BNPAFRPP",
                "po_number": "PO-2025-001",
            },
            "errors": [],
        }

        result = validation_node(state)
        assert result["all_validations_passed"] is False
        vat_result = next(v for v in result["validation_results"] if v["field"] == "vat_number")
        assert vat_result["valid"] is False

    def test_missing_fields(self):
        """Missing fields should produce validation failures."""
        from agents.validation_agent import validation_node

        state = {
            "extracted_data": {
                "supplier_name": "TechnoVision",
                # Missing: vat_number, siret, iban, bic, po_number
            },
            "errors": [],
        }

        result = validation_node(state)
        assert result["all_validations_passed"] is False
        # supplier should pass, rest should fail
        failures = [v for v in result["validation_results"] if not v["valid"]]
        assert len(failures) == 4

    def test_no_extracted_data(self):
        """Should return error status when no extracted data exists."""
        from agents.validation_agent import validation_node

        result = validation_node({"errors": []})
        assert result["status"] == "error"
