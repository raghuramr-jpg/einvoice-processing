"""Sync ERP Suppliers to ChromaDB Vector Store.

Reads all active suppliers from the SQLite ERP simulated Database
and saves them as Documents into a local ChromaDB collection.
"""

import sys
import os
import sqlite3
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_community.embeddings import OllamaEmbeddings # Adjust based on user's LLM preference

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
    
    # Fetch all active suppliers
    cursor.execute("SELECT * FROM suppliers WHERE active = 1")
    rows = cursor.fetchall()
    
    if not rows:
        print("No active suppliers found in ERP Database.")
        sys.exit(0)

    print(f"Fetched {len(rows)} active suppliers.")

    docs = []
    for row in rows:
        # Create a rich text representation for the vector embedding
        content = f"Supplier Name: {row['name']}\nAddress: {row['address']}, {row['city']}, {row['country']}"
        
        # Keep exact mapping IDs in metadata
        metadata = {
            "id": row["id"],
            "name": row["name"],
            "vat_number": row["vat_number"],
            "siret": row["siret"],
            "iban": row["iban"]
        }
        
        docs.append(Document(page_content=content, metadata=metadata))

    # We use OllamaEmbeddings by default to match Quick Start assuming local LLM.
    # If the user has OpenAI configured, they can swap this.
    try:
        embeddings = OllamaEmbeddings(model="nomic-embed-text")
        # Attempt a quick embedding to ensure the model is available
        embeddings.embed_query("test")
    except Exception as e:
        print(f"Warning: Testing Ollama 'nomic-embed-text' model failed: {e}")
        print("Please ensure Ollama is running and you have pulled the model:")
        print("  ollama pull nomic-embed-text")
        print("\nAlternatively, adjust this script to use OpenAIEmbeddings if using an API key.")
        sys.exit(1)

    print("Initializing ChromaDB and indexing documents...")
    vector_store = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        collection_name="erp_suppliers",
        persist_directory=str(CHROMA_PERSIST_DIR)
    )

    print(f"Successfully synced {len(docs)} suppliers into Chroma vector store at {CHROMA_PERSIST_DIR}")

if __name__ == "__main__":
    sync_suppliers()
