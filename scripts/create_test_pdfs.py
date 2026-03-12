import os
from reportlab.pdfgen import canvas

def create_pdf(filename, title, content):
    c = canvas.Canvas(filename)
    c.setFont("Helvetica", 12)
    
    y = 800
    for line in content.split('\n'):
        c.drawString(50, y, line)
        y -= 20
        if y < 50:
            c.showPage()
            c.setFont("Helvetica", 12)
            y = 800
    c.save()

match_text = """TechnoVision SAS
15 Rue de la Paix
Paris, FR

INVOICE
Date: 2025-05-15
Invoice Number: INV-99001
PO Number: PO-2025-001

Billed To:
ACME Corp
100 Main St.
Paris, FR

Description                     Qty     Price       Total
---------------------------------------------------------
IT Equipment                    1       10000.00    10000.00
Cloud Services                  1       5000.00     5000.00

Subtotal (HT): 15000.00
VAT (20%): 3000.00
Total (TTC): 18000.00

VAT Number: FR82123456789
SIRET: 12345678900014
IBAN: FR7630006000011234567890189
BIC: BNPAFRPP
"""

mismatch_text = """TechnoVision SAS
15 Rue de la Paix
Paris, FR

INVOICE
Date: 2025-05-16
Invoice Number: INV-99002
PO Number: PO-2025-001

Billed To:
ACME Corp
100 Main St.
Paris, FR

Description                     Qty     Price       Total
---------------------------------------------------------
Enterprise Server Racks         10      8000.00     80000.00

Subtotal (HT): 80000.00
VAT (20%): 16000.00
Total (TTC): 96000.00

VAT Number: FR82123456789
SIRET: 12345678900014
IBAN: FR7630006000011234567890189
BIC: BNPAFRPP
"""

create_pdf("tests/sample_invoices/policy_match_invoice.pdf", "Match", match_text)
create_pdf("tests/sample_invoices/policy_mismatch_invoice.pdf", "Mismatch", mismatch_text)
print("PDFs created successfully.")
