# Databricks Notebook source
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp, sha2, regexp_extract
from delta.tables import DeltaTable

spark = SparkSession.builder.getOrCreate()

# Retrieve parameters dynamically from Databricks Secret Scope / Widgets
SCOPE = "tac-claims-secrets"
STORAGE_ACCOUNT = dbutils.secrets.get(scope=SCOPE, key="storage-account-name")
STORAGE_KEY = dbutils.secrets.get(scope=SCOPE, key="storage-account-key")

# Set up secure ADLS Gen2 authentication in Spark context
spark.conf.set(
    f"fs.azure.account.key.{STORAGE_ACCOUNT}.dfs.core.windows.net",
    STORAGE_KEY
)

RAW_PATH = f"abfss://raw@{STORAGE_ACCOUNT}.dfs.core.windows.net/incoming_claims/"
BRONZE_DELTA_PATH = f"abfss://bronze@{STORAGE_ACCOUNT}.dfs.core.windows.net/delta/claims_bronze"

raw_df = (
    spark.read.format("binaryFile")
    .option("recursiveFileLookup", "true")
    .option("pathGlobFilter", "*.pdf")
    .load(RAW_PATH)
)

bronze_staged = (
    raw_df.select(
        sha2(col("content"), 256).alias("document_hash"),
        col("path").alias("source_uri"),
        regexp_extract(col("path"), r"incoming_claims/([^/]+)/", 1).alias("category_folder"),
        regexp_extract(col("path"), r"([^/]+$)", 1).alias("filename"),
        col("length").alias("file_size_bytes"),
        col("modificationTime").alias("source_modified_at"),
        col("content").alias("raw_pdf_binary")
    )
    .withColumn("ingested_at", current_timestamp())
)

if not DeltaTable.isDeltaTable(spark, BRONZE_DELTA_PATH):
    bronze_staged.write.format("delta").partitionBy("category_folder").mode("overwrite").save(BRONZE_DELTA_PATH)
else:
    delta_bronze = DeltaTable.forPath(spark, BRONZE_DELTA_PATH)
    (
        delta_bronze.alias("target")
        .merge(bronze_staged.alias("source"), "target.document_hash = source.document_hash")
        .whenNotMatchedInsertAll()
        .execute()
    )