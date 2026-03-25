import asyncio
import json
from datetime import datetime
from api.database import AsyncSessionLocal, Invoice, UserNotification, LineItem, init_db

async def seed_data():
    await init_db()
    async with AsyncSessionLocal() as session:
        # Create a mock invoice that requires review
        invoice = Invoice(
            filename="mock_failed_invoice.pdf",
            status="rejected",
            supplier_name="Fournitures Dupont SARL",
            vat_number="FR55987654321",
            siret="98765432100028",
            iban="FR7610011000202345678901234",
            bic="PSSTFRPP",
            po_number="PO-2025-002",
            invoice_number="DUPONT-001",
            invoice_date="2025-02-15",
            total_ht=8000.00,
            tva_rate=20.0,
            tva_amount=1600.00,
            total_ttc=9600.00,
            currency="EUR",
            confidence_score=0.65,
            human_review_notes="Automated validation failed: The total TTC (9,600.00 EUR) exceeds the maximum allowed cap (10,000.00 EUR) and the PO limit (8,500.00 EUR) for this supplier. Manual review is required to confirm over-budget approval.",
            validation_results=json.dumps([
                {"field": "total_ttc", "valid": False, "message": "Total 9600.00 exceeds PO budget of 8500.00"},
                {"field": "extraction_confidence", "valid": False, "message": "Low OCR confidence for line items"}
            ]),
            errors=json.dumps([]),
            created_at=datetime.utcnow()
        )
        session.add(invoice)
        await session.commit()
        await session.refresh(invoice)

        # Add line items
        items = [
            LineItem(invoice_id=invoice.id, description="Premium Office Paper - A4 (Boxes)", quantity=50, unit_price=40.0, total=2000.0),
            LineItem(invoice_id=invoice.id, description="Ergonomic Chairs V2", quantity=12, unit_price=500.0, total=6000.0)
        ]
        for itm in items:
            session.add(itm)
        
        await session.commit()

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
