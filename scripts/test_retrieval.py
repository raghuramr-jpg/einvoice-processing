import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from langchain_chroma import Chroma
from langchain_community.embeddings import OllamaEmbeddings

# Database Paths
CHROMA_PERSIST_DIR = Path(__file__).parent.parent / "chroma_db"

def test_retrieval():
    embeddings = OllamaEmbeddings(model="nomic-embed-text")
    vector_store = Chroma(
        collection_name="erp_suppliers",
        embedding_function=embeddings,
        persist_directory=str(CHROMA_PERSIST_DIR)
    )

    # A slightly mangled name to test fuzzy matching
    query = "TechnaVision SA Paris"
    
    docs = vector_store.similarity_search(query, k=2)
    
    print(f"\nQuery: '{query}'")
    print("Top matches:")
    for i, doc in enumerate(docs):
        print(f"{i+1}. {doc.metadata['name']} (VAT: {doc.metadata['vat_number']})")
        
if __name__ == "__main__":
    test_retrieval()
