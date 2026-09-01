import io
import os
import pandas as pd
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.storage.blob import BlobServiceClient


def sync_gold_parquet_to_search(index_name: str = "claims-hybrid-index", batch_size: int = 200) -> int:
    storage_account = os.getenv("AZURE_STORAGE_ACCOUNT_NAME", "stclaimsinsight2026")
    storage_key = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")
    search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    search_key = os.getenv("AZURE_SEARCH_ADMIN_KEY")

    if not all([storage_key, search_endpoint, search_key]):
        raise ValueError("Missing required Azure Storage or Azure Search credentials.")

    # 1. Read Gold Parquet from ADLS Gen2
    blob_service = BlobServiceClient(
        account_url=f"https://{storage_account}.blob.core.windows.net",
        credential=storage_key
    )
    gold_client = blob_service.get_blob_client(container="gold", blob="delta/claims_gold/data.parquet")
    
    stream = io.BytesIO(gold_client.download_blob().readall())
    df = pd.read_parquet(stream)

    # 2. Upload to Search Index
    search_client = SearchClient(
        endpoint=search_endpoint,
        index_name=index_name,
        credential=AzureKeyCredential(search_key)
    )

    docs_to_upload = []
    for _, row in df.iterrows():
        # Ensure vector is a plain Python list of floats
        vector = list(row["vector_embedding"]) if hasattr(row["vector_embedding"], "__iter__") else []
        
        docs_to_upload.append({
            "chunk_id": str(row["chunk_id"]),
            "claim_id": str(row["claim_id"]),
            "document_type": str(row["document_type"]),
            "filename": str(row["filename"]),
            "source_uri": str(row["source_uri"]),
            "page_number": int(row["page_number"]),
            "chunk_index": int(row["chunk_index"]),
            "chunk_text": str(row["chunk_text"]),
            "vector_embedding": vector,
            "indexed_at": str(row.get("indexed_at", ""))
        })

    # Batch push
    total_uploaded = 0
    for i in range(0, len(docs_to_upload), batch_size):
        batch = docs_to_upload[i:i + batch_size]
        result = search_client.upload_documents(documents=batch)
        succeeded = sum(1 for r in result if r.succeeded)
        total_uploaded += succeeded

    print(f"Azure AI Search: Successfully indexed {total_uploaded}/{len(docs_to_upload)} chunks.")
    return total_uploaded