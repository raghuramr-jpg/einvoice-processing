import asyncio
import json
from datetime import datetime
from api.database import AsyncSessionLocal, Invoice, LineItem, init_db

async def seed_perfect_invoice():
    await init_db()
    async with AsyncSessionLocal() as session:
        # Create the "Perfect" invoice
        invoice = Invoice(
            filename="golden_invoice_technovision.png",
            status="posted",
            supplier_name="TechnoVision SAS",
            vat_number="FR82123456789",
            siret="12345678900014",
            iban="FR7630006000011234567890189",
            bic="BNPAFRPP",
            po_number="PO-2025-001",
            invoice_number="INV-2025-GOLD",
            invoice_date="2025-03-24",
            total_ht=3000.00,
            tva_rate=20.0,
            tva_amount=600.00,
            total_ttc=3600.00,
            currency="EUR",
            confidence_score=1.0,
            human_review_notes="Automated extraction successful. Confidence 1.0. All ERP validations passed (VAT, SIRET, IBAN, PO). Invoice posted to ERP.",
            validation_results=json.dumps([
                {"field": "vat_number", "valid": True, "message": "VAT FR82123456789 matches TechnoVision SAS"},
                {"field": "siret", "valid": True, "message": "SIRET 12345678900014 matches TechnoVision SAS"},
                {"field": "iban", "valid": True, "message": "IBAN FR76...0189 matches TechnoVision SAS"},
                {"field": "purchase_order", "valid": True, "message": "PO-2025-001 is open and has sufficient balance"}
            ]),
            processing_result=json.dumps({
                "success": True,
                "erp_invoice_id": "ERP-INV-GOLD777",
                "message": "Invoice posted successfully to ERP.",
                "status": "posted"
            }),
            errors=json.dumps([]),
            created_at=datetime.utcnow()
        )
        session.add(invoice)
        await session.commit()
        await session.refresh(invoice)

        # Add line items
        items = [
            LineItem(invoice_id=invoice.id, description="Monitor 4K v2", quantity=2.0, unit_price=500.0, total=1000.0),
            LineItem(invoice_id=invoice.id, description="Laptop Pro X1", quantity=1.0, unit_price=2000.0, total=2000.0)
        ]
        for itm in items:
            session.add(itm)
        
        await session.commit()
        print(f"✅ Perfect invoice seeded with ID: {invoice.id}. Should show as 'posted' in dashboard.")

if __name__ == "__main__":
    asyncio.run(seed_perfect_invoice())
