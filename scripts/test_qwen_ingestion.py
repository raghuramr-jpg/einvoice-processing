import asyncio
import json
import logging
import os
from dotenv import load_dotenv
from agents.graph import process_invoice

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_qwen_ingestion():
    # Load environment variables
    load_dotenv()
    
    # Path to sample invoice
    sample_path = "c:\\installations\\aiprojects\\ap-invoice-agent\\uploads\\sample_invoice.pdf"
    
    if not os.path.exists(sample_path):
        logger.error(f"Sample invoice not found at {sample_path}")
        return

    logger.info(f"Testing Qwen2.5-VL ingestion with: {sample_path}")
    
    try:
        # Run the workflow
        result = await process_invoice(sample_path)
        
        # Log results
        print("\n" + "="*50)
        print("EXTRACTION RESULTS")
        print("="*50)
        print(f"Status: {result.get('status')}")
        print(f"Errors: {result.get('errors')}")
        extracted = result.get("extracted_data", {})
        print(f"Extracted Data: {json.dumps(extracted, indent=2)}")
        print(f"Confidence: {result.get('extraction_confidence')}")
        print("="*50)
        
    except Exception as e:
        logger.error(f"Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_qwen_ingestion())
