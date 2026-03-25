import json
import sqlite3
from mcp_erp_server import server as erp_server

def test_erp_insertion():
    print("Testing ERP insertion via server function...")
    try:
        # TechnoVision SAS data
        result_json = erp_server.create_erp_invoice(
            supplier_name="TechnoVision SAS",
            vat_number="FR82123456789",
            siret="12345678900014",
            po_number="PO-2025-001",
            invoice_number="TEST-DIAG-001",
            invoice_date="2025-03-24",
            total_ht=1000.0,
            tva_amount=200.0,
            total_ttc=1200.0
        )
        result = json.loads(result_json)
        print(f"Result: {result}")
        
        # Verify in DB
        conn = sqlite3.connect('mcp_erp_server/erp_data.db')
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM erp_invoices WHERE invoice_number = 'TEST-DIAG-001'").fetchone()
        if row:
            print(f"✅ Verified in DB: {dict(row)}")
        else:
            print("❌ Not found in DB after call!")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_erp_insertion()
