import os
from src.search.index_manager import get_search_index_client, create_or_update_claims_index
from src.search.indexer import sync_gold_parquet_to_search

if __name__ == "__main__":
    index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "claims-hybrid-index")
    
    print("--- Initializing Azure AI Search Schema ---")
    index_client = get_search_index_client()
    create_or_update_claims_index(index_client, index_name=index_name)

    print("\n--- Ingesting Gold Parquet into Index ---")
    sync_gold_parquet_to_search(index_name=index_name)
    print("\n--- Azure AI Search Sync Complete ---")