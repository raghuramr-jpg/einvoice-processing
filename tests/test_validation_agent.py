"""Tests for the Validation Agent — verifies MCP tool calling and aggregation."""

import json
from pathlib import Path

from unittest.mock import MagicMock, patch

from mcp_erp_server.erp_database import init_database
from agents.validation_agent import ValidationDetailModel, ValidationOutputSchema


@pytest.fixture
def mock_agent():
    """Mock the create_react_agent to return deterministic results for tests without calling the LLM."""
    with patch("agents.validation_agent.create_react_agent") as mock_create:
        mock_agent_instance = MagicMock()
        mock_create.return_value = mock_agent_instance
        yield mock_agent_instance


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
    def test_all_valid(self, mock_agent):
        """All validations should pass for a known supplier with correct data."""
        from agents.validation_agent import validation_node

        # Setup mock behavior
        mock_schema = ValidationOutputSchema(
            all_validations_passed=True,
            validation_results=[
                ValidationDetailModel(field="supplier", valid=True, message="ok"),
                ValidationDetailModel(field="vat_number", valid=True, message="ok"),
                ValidationDetailModel(field="siret", valid=True, message="ok"),
                ValidationDetailModel(field="supplier_bank", valid=True, message="ok"),
                ValidationDetailModel(field="purchase_order", valid=True, message="ok"),
                ValidationDetailModel(field="supplier_policy", valid=True, message="ok"),
            ]
        )
        mock_agent.invoke.return_value = {"structured_response": mock_schema}

        state = {
            "extracted_data": {
                "supplier_name": "TechnoVision",
                "vat_number": "FR82123456789",
                "siret": "12345678900014",
                "iban": "FR7630006000011234567890189",
                "bic": "BNPAFRPP",
                "po_number": "PO-2025-001",
                "total_ttc": 14520.00,
                "currency": "EUR",
            },
            "errors": [],
        }

        result = validation_node(state)
        assert result["all_validations_passed"] is True
        assert result["status"] == "validated"
        assert len(result["validation_results"]) == 6  # 6 checks
        for v in result["validation_results"]:
            assert v.valid is True

    def test_invalid_vat(self, mock_agent):
        """VAT validation should fail for unknown VAT number."""
        from agents.validation_agent import validation_node

        # Setup mock behavior
        mock_schema = ValidationOutputSchema(
            all_validations_passed=False,
            validation_results=[
                ValidationDetailModel(field="vat_number", valid=False, message="fail"),
            ]
        )
        mock_agent.invoke.return_value = {"structured_response": mock_schema}

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
        vat_result = next(v for v in result["validation_results"] if v.field == "vat_number")
        assert vat_result.valid is False

    def test_missing_fields(self, mock_agent):
        """Missing fields should produce validation failures."""
        from agents.validation_agent import validation_node

        # Setup mock behavior
        mock_schema = ValidationOutputSchema(
            all_validations_passed=False,
            validation_results=[
                ValidationDetailModel(field="supplier", valid=True, message="ok"),
                ValidationDetailModel(field="vat_number", valid=False, message="miss"),
                ValidationDetailModel(field="siret", valid=False, message="miss"),
                ValidationDetailModel(field="supplier_bank", valid=False, message="miss"),
                ValidationDetailModel(field="purchase_order", valid=False, message="miss"),
                ValidationDetailModel(field="supplier_policy", valid=False, message="miss"),
            ]
        )
        mock_agent.invoke.return_value = {"structured_response": mock_schema}

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
        failures = [v for v in result["validation_results"] if not v.valid]
        assert len(failures) == 5

    def test_no_extracted_data(self):
        """Should return error status when no extracted data exists."""
        from agents.validation_agent import validation_node

        result = validation_node({"errors": []})
        assert result["status"] == "error"

    # -----------------------------------------------------------------------
    # Policy-specific tests
    # -----------------------------------------------------------------------

    def test_policy_amount_exceeded(self, mock_agent):
        """Dupont invoice over EUR 10,000 cap → supplier_policy.valid = False."""
        from agents.validation_agent import validation_node

        mock_schema = ValidationOutputSchema(
            all_validations_passed=False,
            validation_results=[
                ValidationDetailModel(field="supplier_policy", valid=False, message="maximum value exceeds limit"),
            ]
        )
        mock_agent.invoke.return_value = {"structured_response": mock_schema}

        state = {
            "extracted_data": {
                "supplier_name": "Fournitures Dupont",
                "vat_number": "FR55987654321",   # Dupont — max EUR 10,000
                "siret": "98765432100028",
                "iban": "FR7610011000202345678901234",
                "bic": "PSSTFRPP",
                "po_number": "PO-2025-002",
                "total_ttc": 14280.00,            # Exceeds EUR 10,000 cap
                "currency": "EUR",
            },
            "errors": [],
        }

        result = validation_node(state)
        assert result["all_validations_passed"] is False
        policy_result = next(v for v in result["validation_results"] if v.field == "supplier_policy")
        assert policy_result.valid is False
        assert "maximum" in policy_result.message.lower() or "exceeds" in policy_result.message.lower()

    def test_policy_requires_po_missing(self, mock_agent):
        """GreenSupply invoice without PO → supplier_policy.valid = False."""
        from agents.validation_agent import validation_node

        mock_schema = ValidationOutputSchema(
            all_validations_passed=False,
            validation_results=[
                ValidationDetailModel(field="supplier_policy", valid=False, message="missing purchase order"),
            ]
        )
        mock_agent.invoke.return_value = {"structured_response": mock_schema}

        state = {
            "extracted_data": {
                "supplier_name": "GreenSupply France",
                "vat_number": "FR19234567890",   # requires_po=1
                "siret": "23456789000042",
                "iban": "FR7630004000034567890123456",
                "bic": "BNPAFRPP",
                "po_number": "",                   # No PO!
                "total_ttc": 9576.00,
                "currency": "EUR",
            },
            "errors": [],
        }

        result = validation_node(state)
        assert result["all_validations_passed"] is False
        policy_result = next(v for v in result["validation_results"] if v.field == "supplier_policy")
        assert policy_result.valid is False
        assert "purchase order" in policy_result.message.lower() or "po" in policy_result.message.lower()

    def test_policy_no_po_optional_supplier_passes(self, mock_agent):
        """LogiServ invoice without PO and under EUR 5,000 → passes policy."""
        from agents.validation_agent import validation_node

        mock_schema = ValidationOutputSchema(
            all_validations_passed=True,
            validation_results=[
                ValidationDetailModel(field="supplier_policy", valid=True, message="ok"),
            ]
        )
        mock_agent.invoke.return_value = {"structured_response": mock_schema}

        state = {
            "extracted_data": {
                "supplier_name": "LogiServ Europe",
                "vat_number": "FR31456789012",   # requires_po=0, po_free_limit=5000
                "siret": "45678901200035",
                "iban": "FR7620041000013456789012345",
                "bic": "CEPAFRPP",
                "po_number": "",                   # No PO — allowed for spot services
                "total_ttc": 3900.00,              # Under EUR 5,000 PO-free limit
                "currency": "EUR",
            },
            "errors": [],
        }

        result = validation_node(state)
        policy_result = next(v for v in result["validation_results"] if v.field == "supplier_policy")
        assert policy_result.valid is True

    def test_policy_no_po_optional_supplier_over_po_free_limit_fails(self, mock_agent):
        """LogiServ invoice without PO but ABOVE EUR 5,000 → fails policy."""
        from agents.validation_agent import validation_node

        mock_schema = ValidationOutputSchema(
            all_validations_passed=False,
            validation_results=[
                ValidationDetailModel(field="supplier_policy", valid=False, message="missing purchase order"),
            ]
        )
        mock_agent.invoke.return_value = {"structured_response": mock_schema}

        state = {
            "extracted_data": {
                "supplier_name": "LogiServ Europe",
                "vat_number": "FR31456789012",   # requires_po=0, po_free_limit=5000
                "siret": "45678901200035",
                "iban": "FR7620041000013456789012345",
                "bic": "CEPAFRPP",
                "po_number": "",                   # No PO
                "total_ttc": 8500.00,              # Exceeds EUR 5,000 PO-free limit
                "currency": "EUR",
            },
            "errors": [],
        }

        result = validation_node(state)
        policy_result = next(v for v in result["validation_results"] if v.field == "supplier_policy")
        assert policy_result.valid is False
        assert "po" in policy_result.message.lower() or "purchase" in policy_result.message.lower()

    def test_policy_approval_required(self):
        """MétalPro invoice above EUR 40,000 approval threshold → requires_approval=True."""
        from mcp_erp_server.server import validate_supplier_policy

        result = json.loads(validate_supplier_policy(
            vat_number="FR67890123456",  # MétalPro — approval_required_above=40000
            po_number="PO-2025-006",
            total_amount=47600.00,
            currency="EUR",
        ))

        assert result["valid"] is True
        assert result["requires_approval"] is True
        assert "approval" in result["message"].lower()

    def test_policy_approval_not_required_below_threshold(self):
        """MétalPro invoice below EUR 40,000 threshold → requires_approval=False."""
        from mcp_erp_server.server import validate_supplier_policy

        result = json.loads(validate_supplier_policy(
            vat_number="FR67890123456",  # MétalPro — approval_required_above=40000
            po_number="PO-2025-006",
            total_amount=25000.00,
            currency="EUR",
        ))

        assert result["valid"] is True
        assert result["requires_approval"] is False

    def test_policy_currency_mismatch(self):
        """Invoice in USD for EUR-only supplier → supplier_policy.valid = False."""
        from mcp_erp_server.server import validate_supplier_policy

        result = json.loads(validate_supplier_policy(
            vat_number="FR82123456789",  # TechnoVision — EUR only
            po_number="PO-2025-001",
            total_amount=5000.00,
            currency="USD",              # Wrong currency!
        ))

        assert result["valid"] is False
        assert "currency" in result["message"].lower() or "mismatch" in result["message"].lower()

    def test_policy_includes_payment_terms(self):
        """Successful policy check should return payment_terms_days."""
        from mcp_erp_server.server import validate_supplier_policy

        result = json.loads(validate_supplier_policy(
            vat_number="FR55987654321",  # Dupont — 45-day terms
            po_number="PO-2025-002",
            total_amount=5000.00,
            currency="EUR",
        ))

        assert result["valid"] is True
        assert result["payment_terms_days"] == 45

    def test_policy_details_returned(self):
        """Successful check returns policy_details dict with supplier rules."""
        from mcp_erp_server.server import validate_supplier_policy

        result = json.loads(validate_supplier_policy(
            vat_number="FR82123456789",  # TechnoVision
            po_number="PO-2025-001",
            total_amount=10000.00,
            currency="EUR",
        ))

        assert result["valid"] is True
        pd = result["policy_details"]
        assert pd["requires_po"] is True
        assert pd["max_amount"] == 50000.00
        assert pd["approval_required_above"] == 30000.00
        assert pd["currency"] == "EUR"
