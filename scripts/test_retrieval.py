import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import os
from dotenv import load_dotenv

# Force load .env from project root
dotenv_path = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=dotenv_path, override=True)

# Debug variable presence
required_vars = [
    "AZURE_SEARCH_ENDPOINT",
    "AZURE_SEARCH_ADMIN_KEY",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
    "AZURE_SEARCH_INDEX_NAME"
]

print("--- Environment Variables Check ---")
for var in required_vars:
    val = os.getenv(var)
    status = "SET (OK)" if val else "MISSING (None)"
    print(f"  {var}: {status}")
print("----------------------------------\n")

from src.search.retriever import ClaimsRetriever

if __name__ == "__main__":
    retriever = ClaimsRetriever(index_name=os.getenv("AZURE_SEARCH_INDEX_NAME", "claims-hybrid-index"))
    
    test_queries = [
        "What is the primary injury and physiotherapy recommendation?",
        "Police report incident description and fault assessment"
    ]

    for q in test_queries:
        print(f"\n==========================================")
        print(f"QUERY: '{q}'")
        print(f"==========================================")
        results = retriever.hybrid_search(query=q, top_k=2)

        if not results:
            print("No documents matched.")
            continue

        for i, hit in enumerate(results, 1):
            print(f"\n[{i}] Score: {hit['score']:.4f} | Claim: {hit['claim_id']} | Type: {hit['document_type']}")
            print(f"    Source: {hit['filename']} (Page {hit['page_number']})")
            print(f"    Snippet: {hit['chunk_text'][:200]}...")