# Databricks Notebook source
# MAGIC %pip install openai pandas

# COMMAND ----------
import pandas as pd
from pyspark.sql.functions import col, current_timestamp, pandas_udf
from pyspark.sql.types import ArrayType, FloatType
from openai import AzureOpenAI
from delta.tables import DeltaTable

SCOPE = "tac-claims-secrets"
STORAGE_ACCOUNT = dbutils.secrets.get(scope=SCOPE, key="storage-account-name")
STORAGE_KEY = dbutils.secrets.get(scope=SCOPE, key="storage-account-key")
AOAI_ENDPOINT = dbutils.secrets.get(scope=SCOPE, key="azure-openai-endpoint")
AOAI_KEY = dbutils.secrets.get(scope=SCOPE, key="azure-openai-key")
AOAI_DEPLOYMENT = "text-embedding-3-large"

spark.conf.set(
    f"fs.azure.account.key.{STORAGE_ACCOUNT}.dfs.core.windows.net",
    STORAGE_KEY
)

SILVER_DELTA_PATH = f"abfss://silver@{STORAGE_ACCOUNT}.dfs.core.windows.net/delta/claims_silver"
GOLD_DELTA_PATH = f"abfss://gold@{STORAGE_ACCOUNT}.dfs.core.windows.net/delta/claims_gold"

silver_df = spark.read.format("delta").load(SILVER_DELTA_PATH)

@pandas_udf(ArrayType(FloatType()))
def compute_embeddings_udf(batch_series: pd.Series) -> pd.Series:
    client = AzureOpenAI(
        azure_endpoint=AOAI_ENDPOINT,
        api_key=AOAI_KEY,
        api_version="2024-02-15-preview"
    )
    embeddings = []
    texts = batch_series.fillna("").tolist()
    batch_size = 64

    for i in range(0, len(texts), batch_size):
        chunk = texts[i:i + batch_size]
        response = client.embeddings.create(input=chunk, model=AOAI_DEPLOYMENT)
        embeddings.extend([item.embedding for item in response.data])

    return pd.Series(embeddings)

gold_df = (
    silver_df
    .withColumn("vector_embedding", compute_embeddings_udf(col("chunk_text")))
    .withColumn("indexed_at", current_timestamp())
)

if not DeltaTable.isDeltaTable(spark, GOLD_DELTA_PATH):
    gold_df.write.format("delta").partitionBy("document_type").mode("overwrite").save(GOLD_DELTA_PATH)
else:
    delta_gold = DeltaTable.forPath(spark, GOLD_DELTA_PATH)
    (
        delta_gold.alias("target")
        .merge(gold_df.alias("source"), "target.chunk_id = source.chunk_id")
        .whenMatchedUpdateAll()
        .whenNotMatchedInsertAll()
        .execute()
    )