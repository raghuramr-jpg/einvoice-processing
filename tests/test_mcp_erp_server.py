"""Tests for the MCP ERP Server tools."""

import json
import tempfile
from pathlib import Path

import pytest

# We need to init with a temp DB for isolated tests
from mcp_erp_server.erp_database import init_database


@pytest.fixture(autouse=True)
def setup_db(tmp_path):
    """Initialize a fresh ERP database for each test."""
    db_path = tmp_path / "test_erp.db"
    init_database(db_path)

    # Monkey-patch the server module to use test DB
    import mcp_erp_server.erp_database as db_mod
    original_path = db_mod._DB_PATH
    db_mod._DB_PATH = db_path
    yield
    db_mod._DB_PATH = original_path


class TestValidateVat:
    def test_valid_vat(self):
        from mcp_erp_server.server import validate_vat
        result = json.loads(validate_vat("FR82123456789"))
        assert result["valid"] is True
        assert "TechnoVision" in result["company_name"]

    def test_invalid_vat(self):
        from mcp_erp_server.server import validate_vat
        result = json.loads(validate_vat("FR00000000000"))
        assert result["valid"] is False

    def test_vat_case_insensitive(self):
        from mcp_erp_server.server import validate_vat
        result = json.loads(validate_vat("fr82123456789"))
        assert result["valid"] is True


class TestValidateSiret:
    def test_valid_siret(self):
        from mcp_erp_server.server import validate_siret
        result = json.loads(validate_siret("12345678900014"))
        assert result["valid"] is True
        assert "TechnoVision" in result["company_name"]

    def test_invalid_siret(self):
        from mcp_erp_server.server import validate_siret
        result = json.loads(validate_siret("00000000000000"))
        assert result["valid"] is False


class TestValidateSupplierBank:
    def test_valid_bank(self):
        from mcp_erp_server.server import validate_supplier_bank
        result = json.loads(validate_supplier_bank(
            iban="FR7630006000011234567890189",
            bic="BNPAFRPP",
        ))
        assert result["valid"] is True
        assert "TechnoVision" in result["supplier_name"]

    def test_invalid_bank(self):
        from mcp_erp_server.server import validate_supplier_bank
        result = json.loads(validate_supplier_bank(
            iban="FR0000000000000000000000000",
            bic="XXXXXFRPP",
        ))
        assert result["valid"] is False


class TestValidatePurchaseOrder:
    def test_open_po(self):
        from mcp_erp_server.server import validate_purchase_order
        result = json.loads(validate_purchase_order("PO-2025-001"))
        assert result["valid"] is True
        assert result["status"] == "open"
        assert result["total_amount"] == 15000.00

    def test_closed_po(self):
        from mcp_erp_server.server import validate_purchase_order
        result = json.loads(validate_purchase_order("PO-2025-005"))
        assert result["valid"] is False
        assert result["status"] == "closed"

    def test_missing_po(self):
        from mcp_erp_server.server import validate_purchase_order
        result = json.loads(validate_purchase_order("PO-FAKE-999"))
        assert result["valid"] is False


class TestGetSupplierDetails:
    def test_found(self):
        from mcp_erp_server.server import get_supplier_details
        result = json.loads(get_supplier_details("TechnoVision"))
        assert result["found"] is True
        assert result["supplier"]["vat_number"] == "FR82123456789"

    def test_partial_match(self):
        from mcp_erp_server.server import get_supplier_details
        result = json.loads(get_supplier_details("Dupont"))
        assert result["found"] is True
        assert "Dupont" in result["supplier"]["name"]

    def test_not_found(self):
        from mcp_erp_server.server import get_supplier_details
        result = json.loads(get_supplier_details("Nonexistent Corp"))
        assert result["found"] is False


class TestCreateErpInvoice:
    def test_successful_creation(self):
        from mcp_erp_server.server import create_erp_invoice
        result = json.loads(create_erp_invoice(
            supplier_name="TechnoVision SAS",
            vat_number="FR82123456789",
            siret="12345678900014",
            po_number="PO-2025-001",
            invoice_number="FAC-2025-0042",
            invoice_date="2025-02-15",
            total_ht=12100.00,
            tva_amount=2420.00,
            total_ttc=14520.00,
        ))
        assert result["success"] is True
        assert result["erp_invoice_id"].startswith("ERP-INV-")

    def test_invalid_vat_rejected(self):
        from mcp_erp_server.server import create_erp_invoice
        result = json.loads(create_erp_invoice(
            supplier_name="Fake",
            vat_number="FR00000000000",
            siret="00000000000000",
            po_number="PO-2025-001",
            invoice_number="FAC-FAKE",
            invoice_date="2025-02-15",
            total_ht=100, tva_amount=20, total_ttc=120,
        ))
        assert result["success"] is False
