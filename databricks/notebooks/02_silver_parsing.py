# Databricks Notebook source
# MAGIC %pip install pymupdf tiktoken

# COMMAND ----------
import re
import fitz
import tiktoken
from typing import List, Dict, Any
from pyspark.sql.functions import col, udf, explode, current_timestamp
from pyspark.sql.types import ArrayType, StructType, StructField, StringType, IntegerType
from delta.tables import DeltaTable

SCOPE = "tac-claims-secrets"
STORAGE_ACCOUNT = dbutils.secrets.get(scope=SCOPE, key="storage-account-name")
STORAGE_KEY = dbutils.secrets.get(scope=SCOPE, key="storage-account-key")

spark.conf.set(
    f"fs.azure.account.key.{STORAGE_ACCOUNT}.dfs.core.windows.net",
    STORAGE_KEY
)

BRONZE_DELTA_PATH = f"abfss://bronze@{STORAGE_ACCOUNT}.dfs.core.windows.net/delta/claims_bronze"
SILVER_DELTA_PATH = f"abfss://silver@{STORAGE_ACCOUNT}.dfs.core.windows.net/delta/claims_silver"

bronze_df = spark.read.format("delta").load(BRONZE_DELTA_PATH)

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

chunk_schema = ArrayType(
    StructType([
        StructField("chunk_id", StringType(), False),
        StructField("claim_id", StringType(), True),
        StructField("document_type", StringType(), True),
        StructField("page_number", IntegerType(), True),
        StructField("chunk_index", IntegerType(), True),
        StructField("chunk_text", StringType(), True),
        StructField("token_count", IntegerType(), True),
    ])
)

parse_udf = udf(parse_synthetic_claim, chunk_schema)

silver_df = (
    bronze_df.select(
        col("document_hash"),
        col("filename"),
        col("source_uri"),
        explode(parse_udf(col("raw_pdf_binary"), col("filename"), col("category_folder"))).alias("chunk")
    )
    .select(
        col("chunk.chunk_id").alias("chunk_id"),
        col("document_hash"),
        col("chunk.claim_id").alias("claim_id"),
        col("chunk.document_type").alias("document_type"),
        col("filename"),
        col("source_uri"),
        col("chunk.page_number").alias("page_number"),
        col("chunk.chunk_index").alias("chunk_index"),
        col("chunk.chunk_text").alias("chunk_text"),
        col("chunk.token_count").alias("token_count")
    )
    .withColumn("processed_at", current_timestamp())
)

if not DeltaTable.isDeltaTable(spark, SILVER_DELTA_PATH):
    silver_df.write.format("delta").partitionBy("document_type").mode("overwrite").save(SILVER_DELTA_PATH)
else:
    delta_silver = DeltaTable.forPath(spark, SILVER_DELTA_PATH)
    (
        delta_silver.alias("target")
        .merge(silver_df.alias("source"), "target.chunk_id = source.chunk_id")
        .whenMatchedUpdateAll()
        .whenNotMatchedInsertAll()
        .execute()
    )