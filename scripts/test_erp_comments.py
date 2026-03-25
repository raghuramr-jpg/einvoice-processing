import asyncio
import json
from mcp_erp_server.server import create_erp_invoice
from mcp_erp_server.erp_database import get_db

async def main():
    # Attempt to post an invoice directly
    result_str = create_erp_invoice(
        supplier_name="TechnoVision SAS",
        vat_number="FR82123456789",
        siret="12345678900014",
        po_number="PO-2025-001",
        invoice_number="INV-TEST-001",
        invoice_date="2025-03-24",
        total_ht=1000.0,
        tva_amount=200.0,
        total_ttc=1200.0,
        line_items="[]",
        currency="EUR",
        notes="Manager Exception: Approved manually.",
    )
    result = json.loads(result_str)
    print("ERP Result:", result)
    
    if result.get("success"):
        erp_invoice_id = result["erp_invoice_id"]
        # Query db to verify `notes` is saved
        import sqlite3
        with get_db('mcp_erp_server/erp_data.db') as conn:
            row = conn.execute("SELECT notes FROM erp_invoices WHERE erp_invoice_id = ?", (erp_invoice_id,)).fetchone()
            if row:
                print("Notes from DB:", row[0])
            else:
                print("Invoice not found in DB")

if __name__ == "__main__":
    asyncio.run(main())
