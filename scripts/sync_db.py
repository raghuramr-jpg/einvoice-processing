"""Sync ERP Suppliers (with Policies) to ChromaDB Vector Store.

Reads all active suppliers from the SQLite ERP simulated Database,
joins their policies, and saves enriched Documents into a local
ChromaDB collection. The document text includes policy details so the
ingestion agent can retrieve business rules alongside supplier identity.
"""

import sys
import os
import sqlite3
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_community.embeddings import OllamaEmbeddings

# Database Paths
ERP_DB_PATH = Path(__file__).parent.parent / "mcp_erp_server" / "erp_data.db"
CHROMA_PERSIST_DIR = Path(__file__).parent.parent / "chroma_db"


def sync_suppliers():
    if not ERP_DB_PATH.exists():
        print(f"Error: ERP DB not found at {ERP_DB_PATH}")
        sys.exit(1)

    print("Connecting to ERP Database...")
    conn = sqlite3.connect(ERP_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Fetch all active suppliers with their policies (LEFT JOIN so suppliers
    # without a policy record are still included)
    cursor.execute("""
        SELECT
            s.id, s.name, s.vat_number, s.siret, s.iban, s.bic,
            s.address, s.city, s.country,
            COALESCE(p.requires_po, 1)               AS requires_po,
            COALESCE(p.max_amount, 50000.0)           AS max_amount,
            COALESCE(p.allowed_without_po_max, 0.0)   AS allowed_without_po_max,
            COALESCE(p.currency, 'EUR')               AS currency,
            COALESCE(p.approval_required_above, 0.0)  AS approval_required_above,
            COALESCE(p.payment_terms_days, 30)        AS payment_terms_days,
            COALESCE(p.notes, '')                     AS notes
        FROM suppliers s
        LEFT JOIN supplier_policies p ON p.supplier_id = s.id
        WHERE s.active = 1
    """)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("No active suppliers found in ERP Database.")
        sys.exit(0)

    print(f"Fetched {len(rows)} active suppliers (with policies).")

    docs = []
    for row in rows:
        po_policy = "requires a Purchase Order" if row["requires_po"] else "does NOT require a Purchase Order"
        po_free_note = (
            f" (PO-free invoices allowed up to {row['allowed_without_po_max']:.0f} {row['currency']})"
            if not row["requires_po"] and row["allowed_without_po_max"] > 0 else ""
        )
        approval_note = (
            f" Manual approval required above {row['approval_required_above']:.0f} {row['currency']}."
            if row["approval_required_above"] > 0 else ""
        )

        # Rich text description for semantic embedding
        content = (
            f"Supplier Name: {row['name']}\n"
            f"Address: {row['address']}, {row['city']}, {row['country']}\n"
            f"VAT: {row['vat_number']}  SIRET: {row['siret']}\n"
            f"Invoice Policy: {po_policy}{po_free_note}. "
            f"Maximum invoice cap {row['currency']} {row['max_amount']:.0f}. "
            f"Payment terms {row['payment_terms_days']} days.{approval_note}\n"
            f"Business Notes: {row['notes']}"
        )

        # Full metadata — passed back to the ingestion agent for structured use
        metadata = {
            "id":                     row["id"],
            "name":                   row["name"],
            "vat_number":             row["vat_number"],
            "siret":                  row["siret"],
            "iban":                   row["iban"],
            # Policy fields
            "requires_po":            int(row["requires_po"]),
            "max_amount":             float(row["max_amount"]),
            "allowed_without_po_max": float(row["allowed_without_po_max"]),
            "currency":               row["currency"],
            "approval_required_above": float(row["approval_required_above"]),
            "payment_terms_days":     int(row["payment_terms_days"]),
        }

        docs.append(Document(page_content=content, metadata=metadata))

    # Test embedding model availability
    try:
        embeddings = OllamaEmbeddings(model="nomic-embed-text")
        embeddings.embed_query("test")
    except Exception as e:
        print(f"Warning: Testing Ollama 'nomic-embed-text' model failed: {e}")
        print("Please ensure Ollama is running and you have pulled the model:")
        print("  ollama pull nomic-embed-text")
        print("\nAlternatively, adjust this script to use OpenAIEmbeddings if using an API key.")
        sys.exit(1)

    print("Initializing ChromaDB and re-indexing enriched supplier+policy documents...")

    # Delete existing collection before re-creating to avoid stale records
    import chromadb
    chroma_client = chromadb.PersistentClient(path=str(CHROMA_PERSIST_DIR))
    try:
        chroma_client.delete_collection("erp_suppliers")
        print("Deleted existing 'erp_suppliers' collection — will rebuild fresh.")
    except Exception:
        pass  # Collection may not exist on first run

    vector_store = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        collection_name="erp_suppliers",
        persist_directory=str(CHROMA_PERSIST_DIR),
    )

    print(f"\nSuccessfully synced {len(docs)} supplier+policy records into ChromaDB at {CHROMA_PERSIST_DIR}")
    print("\nSample document embedded:")
    print(f"  {docs[0].page_content}")


if __name__ == "__main__":
    sync_suppliers()
