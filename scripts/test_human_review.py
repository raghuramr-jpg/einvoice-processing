"""Verification script for Human Review Agent."""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from agents.graph import process_invoice
from unittest.mock import MagicMock, patch

# Mock LLM for the test
class MockLLM(MagicMock):
    def bind_tools(self, tools, **kwargs):
        return self
        
    def invoke(self, messages):
        # Return a sample explanation
        return MagicMock(content="Automated validation failed for the PO number and VAT. Extraction confidence is 0.75, which is below the threshold. Please review the invoice manually.")
    
    def with_structured_output(self, schema):
        mock_structured = MagicMock()
        # Return an object that model_dump() returns a dict
        def mock_invoke(*args, **kwargs):
            if "Extract invoice data" in str(args):
                return MagicMock(
                    supplier_name=None, # Missing mandatory field
                    invoice_number="INV-001", 
                    confidence_score=1.0, # LLM thinks it's 1.0
                    model_dump=lambda: {"supplier_name": None, "invoice_number": "INV-001", "confidence_score": 1.0}
                )
            # Return ValidationOutputSchema
            return MagicMock(
                all_validations_passed=False,
                validation_results=[{"field": "vat_number", "valid": False, "message": "VAT mismatch", "details": {}}],
                model_dump=lambda: {
                    "all_validations_passed": False,
                    "validation_results": [{"field": "vat_number", "valid": False, "message": "VAT mismatch", "details": {}}]
                }
            )
        mock_structured.invoke = mock_invoke
        return mock_structured

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_human_review_trigger():
    # Use an invoice that is known to fail
    invoice_path = project_root / "tests" / "sample_invoices" / "invoice_dupont_fail_amount.pdf"
    
    # Mocking the LLM, Embeddings, and Chroma calls
    with patch("agents.utils.get_llm", return_value=MockLLM()), \
         patch("agents.ingestion_agent.OllamaEmbeddings"), \
         patch("agents.ingestion_agent.Chroma") as mock_chroma:
        
        # Setup mock chroma response
        mock_vector_store = MagicMock()
        mock_vector_store.similarity_search.return_value = [
            MagicMock(metadata={"name": "Dupont", "vat_number": "FR123456789"})
        ]
        mock_chroma.return_value = mock_vector_store

        logger.info(f"Processing failing invoice with COMPREHENSIVE MOCK: {invoice_path.name}")
        
        # Run the graph
        try:
            result = await process_invoice(str(invoice_path))
        except Exception as e:
            import traceback
            logger.error("Graph execution failed!")
            traceback.print_exc()
            return
    
    logger.info(f"Final Status: {result.get('status')}")
    logger.info(f"Human Review Notes: {result.get('human_review_notes')}")
    
    # Assertions
    status = result.get("status")
    notes = result.get("human_review_notes")
    
    # Since human_review -> reject, the final status in the state might be 'rejected' 
    # but the human_review_notes should be populated.
    # Wait, in my graph.py: workflow.add_node("human_review", human_review_node)
    # workflow.add_edge("human_review", "reject")
    # So human_review node returns {"status": "requires_review", ...}
    # Then reject node is called. Reject node returns {"status": "rejected", ...}
    # So the status WILL be 'rejected'.
    
    if notes:
        print("\n✅ SUCCESS: Human review notes were generated!")
        print(f"Notes: {notes}")
    else:
        print("\n❌ FAILURE: No human review notes generated.")
        
    if status == "rejected":
        print("✅ SUCCESS: Status is 'rejected' as expected (after human review prep).")
    else:
        print(f"❌ FAILURE: Unexpected status: {status}")

if __name__ == "__main__":
    asyncio.run(test_human_review_trigger())
