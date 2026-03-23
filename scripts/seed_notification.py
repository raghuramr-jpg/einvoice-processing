import asyncio
import json
from datetime import datetime
from api.database import AsyncSessionLocal, Invoice, UserNotification, init_db

async def seed_data():
    await init_db()
    async with AsyncSessionLocal() as session:
        # Create a mock invoice that requires review
        invoice = Invoice(
            filename="mock_failed_invoice.pdf",
            status="rejected",
            supplier_name="Mock Supplier",
            invoice_number="MOCK-001",
            confidence_score=0.65,
            human_review_notes="Automated validation failed for the PO number. SIRET was also non-compliant. High extraction error rate on line items. Manual review needed to fix extraction errors.",
            validation_results=json.dumps([
                {"field": "purchase_order", "valid": False, "message": "PO not found in ERP"},
                {"field": "siret", "valid": False, "message": "Invalid SIRET format"}
            ]),
            errors=json.dumps([]),
            created_at=datetime.utcnow()
        )
        session.add(invoice)
        await session.commit()
        await session.refresh(invoice)

        # Create the notification
        notification = UserNotification(
            invoice_id=invoice.id,
            message=invoice.human_review_notes,
            requires_manual_review=1,
            created_at=datetime.utcnow()
        )
        session.add(notification)
        await session.commit()
        
        print(f"Seed data created for Invoice ID: {invoice.id}")

if __name__ == "__main__":
    asyncio.run(seed_data())
