import os
import re
import hashlib
from datetime import datetime
from typing import List, Dict, Any

import fitz  # PyMuPDF
import tiktoken
import pandas as pd
from azure.storage.blob import BlobServiceClient
from openai import AzureOpenAI

# ---------------------------------------------------------
# Environment & Client Setup
# ---------------------------------------------------------
STORAGE_ACCOUNT = os.getenv("AZURE_STORAGE_ACCOUNT_NAME", "stclaimsinsight2026")
STORAGE_KEY = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")
AOAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AOAI_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AOAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large")

if not STORAGE_KEY:
    raise ValueError("AZURE_STORAGE_ACCOUNT_KEY environment variable is missing.")

blob_service = BlobServiceClient(
    account_url=f"https://{STORAGE_ACCOUNT}.blob.core.windows.net",
    credential=STORAGE_KEY
)

# ---------------------------------------------------------
# Step 1: BRONZE LAYER (Raw Extraction & Ingestion)
# ---------------------------------------------------------
print("--- Step 1: Processing Bronze Ingestion ---")
raw_container = blob_service.get_container_client("raw")
bronze_container = blob_service.get_container_client("bronze")

bronze_records = []
for blob in raw_container.list_blobs(name_starts_with="incoming_claims/"):
    if blob.name.endswith(".pdf"):
        data = raw_container.get_blob_client(blob.name).download_blob().readall()
        doc_hash = hashlib.sha256(data).hexdigest()
        
        path_parts = blob.name.split("/")
        category_folder = path_parts[1] if len(path_parts) > 2 else "general"
        filename = path_parts[-1]
        
        bronze_records.append({
            "document_hash": doc_hash,
            "source_uri": f"abfss://raw@{STORAGE_ACCOUNT}.dfs.core.windows.net/{blob.name}",
            "category_folder": category_folder,
            "filename": filename,
            "file_size_bytes": len(data),
            "source_modified_at": blob.last_modified.isoformat() if blob.last_modified else datetime.utcnow().isoformat(),
            "raw_pdf_binary": data,
            "ingested_at": datetime.utcnow().isoformat()
        })

print(f"Bronze: Successfully loaded {len(bronze_records)} PDF binaries.")

# ---------------------------------------------------------
# Step 2: SILVER LAYER (Parsing, Tokenizing & Chunking)
# ---------------------------------------------------------
print("\n--- Step 2: Processing Silver Transformation ---")
silver_container = blob_service.get_container_client("silver")

def parse_synthetic_claim(binary_bytes: bytes, filename: str, category: str) -> List[Dict[str, Any]]:
    if not binary_bytes:
        return []

    doc = fitz.open(stream=binary_bytes, filetype="pdf")
    enc = tiktoken.get_encoding("cl100k_base")

    claim_match = re.search(r"CLM-\d{4}-\d{4}", filename)
    claim_id = claim_match.group(0) if claim_match else "UNKNOWN_CLAIM"

    doc_type_mapping = {
        "medical_discharge": "MEDICAL_DISCHARGE",
        "physio_notes": "PHYSIO_PROGRESS_NOTE",
        "police_reports": "POLICE_REPORT",
        "policy_schedules": "POLICY_SCHEDULE"
    }
    doc_type = doc_type_mapping.get(category, "GENERAL_DOC")

    chunks, chunk_index, target_size, overlap = [], 0, 350, 40

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        page_num = page_idx + 1
        text = page.get_text("text").strip()
        clean_text = re.sub(r"\n\s*\n", "\n\n", text)
        sections = [s.strip() for s in clean_text.split("\n\n") if len(s.strip()) > 20]

        for sec in sections:
            tokens = enc.encode(sec)
            if len(tokens) <= target_size:
                chunks.append({
                    "chunk_id": f"{claim_id}_{doc_type}_p{page_num}_c{chunk_index}",
                    "claim_id": claim_id,
                    "document_type": doc_type,
                    "page_number": page_num,
                    "chunk_index": chunk_index,
                    "chunk_text": sec,
                    "token_count": len(tokens)
                })
                chunk_index += 1
            else:
                start = 0
                while start < len(tokens):
                    end = min(start + target_size, len(tokens))
                    chunks.append({
                        "chunk_id": f"{claim_id}_{doc_type}_p{page_num}_c{chunk_index}",
                        "claim_id": claim_id,
                        "document_type": doc_type,
                        "page_number": page_num,
                        "chunk_index": chunk_index,
                        "chunk_text": enc.decode(tokens[start:end]),
                        "token_count": len(tokens[start:end])
                    })
                    chunk_index += 1
                    if end == len(tokens):
                        break
                    start += (target_size - overlap)

    doc.close()
    return chunks

silver_rows = []
for item in bronze_records:
    parsed_chunks = parse_synthetic_claim(
        binary_bytes=item["raw_pdf_binary"],
        filename=item["filename"],
        category=item["category_folder"]
    )
    for c in parsed_chunks:
        silver_rows.append({
            "chunk_id": c["chunk_id"],
            "document_hash": item["document_hash"],
            "claim_id": c["claim_id"],
            "document_type": c["document_type"],
            "filename": item["filename"],
            "source_uri": item["source_uri"],
            "page_number": c["page_number"],
            "chunk_index": c["chunk_index"],
            "chunk_text": c["chunk_text"],
            "token_count": c["token_count"],
            "processed_at": datetime.utcnow().isoformat()
        })

silver_df = pd.DataFrame(silver_rows)
if not silver_df.empty:
    silver_parquet = silver_df.to_parquet(index=False)
    silver_container.upload_blob(name="delta/claims_silver/data.parquet", data=silver_parquet, overwrite=True)
    print(f"Silver: Extracted and uploaded {len(silver_rows)} text chunks across partitions.")
else:
    print("Silver: No records generated.")

# ---------------------------------------------------------
# Step 3: GOLD LAYER (Batched Vector Embeddings)
# ---------------------------------------------------------
print("\n--- Step 3: Processing Gold Embeddings ---")
gold_container = blob_service.get_container_client("gold")

if AOAI_KEY and AOAI_ENDPOINT and not silver_df.empty:
    client = AzureOpenAI(
        azure_endpoint=AOAI_ENDPOINT,
        api_key=AOAI_KEY,
        api_version="2024-02-15-preview"
    )

    texts = silver_df["chunk_text"].fillna("").tolist()
    embeddings = []
    batch_size = 64

    for i in range(0, len(texts), batch_size):
        chunk = texts[i:i + batch_size]
        response = client.embeddings.create(input=chunk, model=AOAI_DEPLOYMENT)
        embeddings.extend([item.embedding for item in response.data])

    gold_df = silver_df.copy()
    gold_df["vector_embedding"] = embeddings
    gold_df["indexed_at"] = datetime.utcnow().isoformat()

    gold_parquet = gold_df.to_parquet(index=False)
    gold_container.upload_blob(name="delta/claims_gold/data.parquet", data=gold_parquet, overwrite=True)
    print(f"Gold: Successfully computed and stored vector embeddings for {len(gold_df)} chunks.")
else:
    print("Gold: Azure OpenAI configuration not provided or empty silver dataset; skipped embeddings.")

print("\n--- Pipeline Completed Successfully ---")