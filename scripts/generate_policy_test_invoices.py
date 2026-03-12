"""Generate realistic French supplier invoice PDFs for testing supplier policies.

Scenarios:
  1. TechnoVision SAS         — PASS (valid PO, amount within limits)
  2. Fournitures Dupont SARL  — FAIL amount exceeds EUR 10,000 cap
  3. LogiServ Europe SA       — PASS without PO (PO-optional, under EUR 5,000 limit)
  4. GreenSupply France       — FAIL missing PO (PO required)
  5. MétalPro Industries      — PASS but triggers approval (above EUR 40,000 threshold)
"""

import os
import sys
from pathlib import Path
from datetime import date

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT

OUTPUT_DIR = Path(__file__).parent.parent / "tests" / "sample_invoices"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle(name="InvoiceTitle",   fontSize=20, leading=24, spaceAfter=6,  textColor=colors.HexColor("#1a1a2e")))
    ss.add(ParagraphStyle(name="SectionHeader",  fontSize=11, leading=14, spaceBefore=8, textColor=colors.HexColor("#16213e"), fontName="Helvetica-Bold"))
    ss.add(ParagraphStyle(name="Body",           fontSize=9,  leading=12))
    ss.add(ParagraphStyle(name="BodyRight",      fontSize=9,  leading=12, alignment=TA_RIGHT))
    ss.add(ParagraphStyle(name="Small",          fontSize=8,  leading=10, textColor=colors.grey))
    ss.add(ParagraphStyle(name="PolicyBanner",   fontSize=8,  leading=11, textColor=colors.HexColor("#6b2737"),
                          fontName="Helvetica-Bold", spaceBefore=4))
    return ss


def _amount_row(label, amount, currency="EUR", bold=False):
    style_name = "Helvetica-Bold" if bold else "Helvetica"
    return [
        Paragraph(f"<font name='{style_name}'>{label}</font>", ParagraphStyle(name=f"ar_{label}", fontSize=9)),
        Paragraph(
            f"<font name='{style_name}'>{amount:,.2f} {currency}</font>",
            ParagraphStyle(name=f"arv_{label}", fontSize=9, alignment=TA_RIGHT),
        ),
    ]


def build_invoice(
    output_path: Path,
    invoice_number: str,
    invoice_date: str,
    supplier: dict,
    buyer: dict,
    line_items: list[dict],
    po_number: str | None,
    tva_rate: float = 20.0,
    policy_note: str = "",
):
    """Build a single invoice PDF."""
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )
    ss = _styles()
    story = []

    # --- Header ---
    header_data = [
        [
            Paragraph("<b>FACTURE</b>", ss["InvoiceTitle"]),
            Paragraph(
                f"N° <b>{invoice_number}</b><br/>Date: {invoice_date}<br/>"
                + (f"Bon de commande: <b>{po_number}</b>" if po_number else "<font color='red'>SANS BON DE COMMANDE</font>"),
                ParagraphStyle(name="hdr_right", fontSize=10, alignment=TA_RIGHT),
            ),
        ]
    ]
    header_table = Table(header_data, colWidths=["60%", "40%"])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0f4ff")),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (0, -1), 10),
        ("RIGHTPADDING", (-1, 0), (-1, -1), 10),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 6 * mm))

    # --- Supplier + Buyer ---
    addr_data = [
        [
            Paragraph(
                f"<b>{supplier['name']}</b><br/>"
                f"{supplier['address']}, {supplier['city']}, {supplier['country']}<br/>"
                f"N° TVA: {supplier['vat_number']}<br/>"
                f"SIRET: {supplier['siret']}<br/>"
                f"IBAN: {supplier['iban']}<br/>"
                f"BIC: {supplier['bic']}",
                ss["Body"],
            ),
            Paragraph(
                f"<b>Destinataire:</b><br/>"
                f"{buyer['name']}<br/>{buyer['address']}",
                ss["Body"],
            ),
        ]
    ]
    addr_table = Table(addr_data, colWidths=["50%", "50%"])
    addr_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEAFTER", (0, 0), (0, -1), 0.5, colors.lightgrey),
        ("LEFTPADDING", (1, 0), (1, -1), 12),
    ]))
    story.append(addr_table)
    story.append(Spacer(1, 5 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    story.append(Spacer(1, 4 * mm))

    # --- Line Items Table ---
    story.append(Paragraph("Détail des prestations", ss["SectionHeader"]))
    story.append(Spacer(1, 2 * mm))

    item_header = ["Description", "Qté", "Prix Unit. HT", "Total HT"]
    item_rows = [item_header]
    total_ht = 0.0
    for item in line_items:
        line_total = item["qty"] * item["unit_price"]
        total_ht += line_total
        item_rows.append([
            item["description"],
            str(item["qty"]),
            f"{item['unit_price']:,.2f} €",
            f"{line_total:,.2f} €",
        ])

    items_table = Table(item_rows, colWidths=["50%", "10%", "20%", "20%"])
    items_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f9f9f9"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#dddddd")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (-1, 0), (-1, -1), 6),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 4 * mm))

    # --- Totals ---
    tva_amount = total_ht * tva_rate / 100
    total_ttc = total_ht + tva_amount

    totals_data = [
        _amount_row("Total HT", total_ht),
        _amount_row(f"TVA ({tva_rate:.0f}%)", tva_amount),
        _amount_row("Total TTC", total_ttc, bold=True),
    ]
    totals_table = Table(totals_data, colWidths=["70%", "30%"])
    totals_table.setStyle(TableStyle([
        ("LINEABOVE", (0, 2), (-1, 2), 1, colors.HexColor("#1a1a2e")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#e8f0fe")),
    ]))
    story.append(totals_table)

    # --- Policy Advisory Note ---
    if policy_note:
        story.append(Spacer(1, 5 * mm))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e0a0a0")))
        story.append(Paragraph(f"⚠ NOTE POLITIQUE FOURNISSEUR: {policy_note}", ss["PolicyBanner"]))

    # --- Footer ---
    story.append(Spacer(1, 8 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        f"Conditions de paiement: {supplier.get('payment_terms', '30 jours nets')} — "
        "Mode de paiement: Virement bancaire — Merci pour votre confiance.",
        ss["Small"],
    ))

    doc.build(story)
    print(f"  Created: {output_path.name}  (Total TTC: {total_ttc:,.2f} EUR)")


# ---------------------------------------------------------------------------
# Invoice Definitions — 5 Scenarios
# ---------------------------------------------------------------------------

BUYER = {
    "name": "Acme Corporation",
    "address": "100 Boulevard Saint-Germain, 75006 Paris",
}

INVOICES = [
    # -----------------------------------------------------------------------
    # 1. TechnoVision SAS — PASS (PO present, amount within limits)
    # -----------------------------------------------------------------------
    dict(
        filename="invoice_technovision_pass.pdf",
        invoice_number="FAC-2026-0101",
        invoice_date="2026-03-03",
        supplier={
            "name": "TechnoVision SAS",
            "address": "15 Rue de la Paix",
            "city": "Paris",
            "country": "France",
            "vat_number": "FR82123456789",
            "siret": "12345678900014",
            "iban": "FR7630006000011234567890189",
            "bic": "BNPAFRPP",
            "payment_terms": "30 jours nets",
        },
        po_number="PO-2025-001",
        line_items=[
            {"description": "Serveur Dell PowerEdge R740", "qty": 2, "unit_price": 3500.00},
            {"description": "Licence Windows Server 2022", "qty": 2, "unit_price": 800.00},
            {"description": "Installation & Configuration",  "qty": 1, "unit_price": 2000.00},
            {"description": "Support annuel Premium",        "qty": 1, "unit_price": 1500.00},
        ],
        policy_note="",
    ),
    # -----------------------------------------------------------------------
    # 2. Fournitures Dupont SARL — FAIL: amount EUR 11,900 > cap EUR 10,000
    # -----------------------------------------------------------------------
    dict(
        filename="invoice_dupont_fail_amount.pdf",
        invoice_number="FAC-2026-0102",
        invoice_date="2026-03-03",
        supplier={
            "name": "Fournitures Dupont SARL",
            "address": "42 Avenue des Champs-Élysées",
            "city": "Lyon",
            "country": "France",
            "vat_number": "FR55987654321",
            "siret": "98765432100028",
            "iban": "FR7610011000202345678901234",
            "bic": "PSSTFRPP",
            "payment_terms": "45 jours nets",
        },
        po_number="PO-2025-002",
        line_items=[
            {"description": "Fournitures de bureau (lot A)",  "qty": 10, "unit_price": 250.00},
            {"description": "Cartouches d'encre premium",     "qty": 50, "unit_price": 35.00},
            {"description": "Mobilier de bureau ergonomique", "qty": 5,  "unit_price": 980.00},
            {"description": "Papier A4 premium (carton×50)",  "qty": 20, "unit_price": 38.00},
        ],
        policy_note="ALERTE: Montant TTC 14 280,00 EUR dépasse le plafond autorisé de 10 000 EUR pour ce fournisseur. Facture rejetée.",
    ),
    # -----------------------------------------------------------------------
    # 3. LogiServ Europe SA — PASS without PO (PO optional, amount < EUR 5,000)
    # -----------------------------------------------------------------------
    dict(
        filename="invoice_logiserv_no_po_pass.pdf",
        invoice_number="FAC-2026-0103",
        invoice_date="2026-03-03",
        supplier={
            "name": "LogiServ Europe SA",
            "address": "8 Boulevard Haussmann",
            "city": "Marseille",
            "country": "France",
            "vat_number": "FR31456789012",
            "siret": "45678901200035",
            "iban": "FR7620041000013456789012345",
            "bic": "CEPAFRPP",
            "payment_terms": "60 jours nets",
        },
        po_number=None,  # No PO — allowed for spot services < EUR 5,000
        line_items=[
            {"description": "Transport express Paris–Lyon (urgence)", "qty": 1,  "unit_price": 1800.00},
            {"description": "Manutention & déchargement",             "qty": 3,  "unit_price": 250.00},
            {"description": "Frais de stockage temporaire (7 jours)", "qty": 7,  "unit_price": 50.00},
        ],
        policy_note="Prestation spot sans bon de commande autorisée (montant HT 3 250 EUR < plafond PO-libre de 5 000 EUR).",
    ),
    # -----------------------------------------------------------------------
    # 4. GreenSupply France — FAIL: no PO, but PO is REQUIRED
    # -----------------------------------------------------------------------
    dict(
        filename="invoice_green_fail_no_po.pdf",
        invoice_number="FAC-2026-0104",
        invoice_date="2026-03-03",
        supplier={
            "name": "GreenSupply France",
            "address": "120 Rue du Commerce",
            "city": "Toulouse",
            "country": "France",
            "vat_number": "FR19234567890",
            "siret": "23456789000042",
            "iban": "FR7630004000034567890123456",
            "bic": "BNPAFRPP",
            "payment_terms": "30 jours nets",
        },
        po_number=None,  # Missing PO — will fail validation
        line_items=[
            {"description": "Emballages biodégradables (lot 500 u.)", "qty": 4,  "unit_price": 850.00},
            {"description": "Sacs en kraft recyclé (carton 1000 u.)", "qty": 10, "unit_price": 195.00},
            {"description": "Frais de livraison",                     "qty": 1,  "unit_price": 120.00},
        ],
        policy_note="REJET: Bon de commande obligatoire pour GreenSupply France. Aucun numéro de BC fourni sur cette facture.",
    ),
    # -----------------------------------------------------------------------
    # 5. MétalPro Industries — PASS but triggers approval (EUR 47,600 > EUR 40,000 threshold)
    # -----------------------------------------------------------------------
    dict(
        filename="invoice_metalpro_approval.pdf",
        invoice_number="FAC-2026-0105",
        invoice_date="2026-03-03",
        supplier={
            "name": "MétalPro Industries",
            "address": "5 Impasse des Ateliers",
            "city": "Bordeaux",
            "country": "France",
            "vat_number": "FR67890123456",
            "siret": "89012345600019",
            "iban": "FR7610096000005678901234567",
            "bic": "CMCIFRPP",
            "payment_terms": "90 jours nets",
        },
        po_number="PO-2025-006",
        line_items=[
            {"description": "Charpente acier galvanisée (tonne)",     "qty": 8, "unit_price": 2800.00},
            {"description": "Découpe laser sur mesure",               "qty": 1, "unit_price": 4200.00},
            {"description": "Traitement de surface anticorrosion",    "qty": 1, "unit_price": 3200.00},
            {"description": "Transport & livraison sur chantier",     "qty": 1, "unit_price": 2000.00},
        ],
        policy_note="APPROBATION REQUISE: Montant TTC 57 120 EUR dépasse le seuil d'approbation CAPEX de 40 000 EUR. Comité d'approbation CAPEX requis avant mise en paiement.",
    ),
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Generating {len(INVOICES)} policy-test invoice PDFs into {OUTPUT_DIR}\n")

    for inv in INVOICES:
        build_invoice(
            output_path=OUTPUT_DIR / inv["filename"],
            invoice_number=inv["invoice_number"],
            invoice_date=inv["invoice_date"],
            supplier=inv["supplier"],
            buyer=BUYER,
            line_items=inv["line_items"],
            po_number=inv["po_number"],
            policy_note=inv["policy_note"],
        )

    print(f"\nDone. All {len(INVOICES)} PDFs saved to {OUTPUT_DIR}")
    print("\nScenario Summary:")
    print("  invoice_technovision_pass.pdf     → ✅ PASS (PO present, EUR 14,520 < EUR 50,000 cap)")
    print("  invoice_dupont_fail_amount.pdf    → ❌ FAIL (EUR 14,280 TTC > EUR 10,000 cap)")
    print("  invoice_logiserv_no_po_pass.pdf   → ✅ PASS (No PO — PO optional, EUR 3,900 < EUR 5,000 limit)")
    print("  invoice_green_fail_no_po.pdf      → ❌ FAIL (No PO — PO required for GreenSupply)")
    print("  invoice_metalpro_approval.pdf     → ⚠️  PASS + APPROVAL REQUIRED (EUR 57,120 > EUR 40,000 threshold)")


if __name__ == "__main__":
    main()
