# Databricks notebook source

# COMMAND ----------
# MAGIC %md
# MAGIC # ShopStream — Create Vector Search Index
# MAGIC
# MAGIC **What this notebook does:**
# MAGIC 1. Creates a Mosaic AI Vector Search endpoint (`helix-vs-endpoint`) if it does not exist
# MAGIC 2. Creates a delta-sync index on `helix_databricks.default.document_chunks`
# MAGIC 3. Waits until the index is ONLINE and ready to query
# MAGIC
# MAGIC **Prerequisites:**
# MAGIC - `embed_documents.py` must have been run first (the source Delta table must exist)
# MAGIC - The table must have Change Data Feed enabled (this notebook enables it automatically)
# MAGIC
# MAGIC **Run once.** After that, the index syncs automatically whenever `document_chunks` changes.

# COMMAND ----------

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.vectorsearch import (
    EndpointType,
    VectorIndexType,
)
import time

# COMMAND ----------

# Constants
CATALOG = "helix_databricks"
DATABASE = "default"
SOURCE_TABLE = f"{CATALOG}.{DATABASE}.document_chunks"
VS_ENDPOINT = "helix-vs-endpoint"
VS_INDEX = f"{CATALOG}.{DATABASE}.document_chunks_index"
EMBEDDING_MODEL = "databricks-gte-large-en"  # Databricks-hosted embedding model — no API key needed
PRIMARY_KEY = "chunk_id"
EMBEDDING_SOURCE_COLUMN = "chunk_text"

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 1: Enable Change Data Feed on the source table
# MAGIC
# MAGIC Vector Search delta-sync mode requires CDF so it can track which rows changed.
# MAGIC This is a one-time ALTER TABLE — safe to re-run.

# COMMAND ----------

spark.sql(f"ALTER TABLE {SOURCE_TABLE} SET TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')")
print(f"Change Data Feed enabled on {SOURCE_TABLE}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 2: Create Vector Search endpoint
# MAGIC
# MAGIC The endpoint is shared infrastructure — one endpoint can host multiple indexes.
# MAGIC Creation takes ~5 minutes the first time.

# COMMAND ----------

w = WorkspaceClient()

# Check if endpoint already exists
existing_endpoints = [e.name for e in w.vector_search_endpoints.list_endpoints()]

if VS_ENDPOINT in existing_endpoints:
    print(f"Endpoint '{VS_ENDPOINT}' already exists — skipping creation")
else:
    print(f"Creating endpoint '{VS_ENDPOINT}'...")
    w.vector_search_endpoints.create_endpoint_and_wait(
        name=VS_ENDPOINT,
        endpoint_type=EndpointType.STANDARD,
    )
    print(f"Endpoint '{VS_ENDPOINT}' is ready")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 3: Create the delta-sync index
# MAGIC
# MAGIC - Index type: `DELTA_SYNC` — Databricks keeps it in sync with the source table automatically
# MAGIC - Embedding model: `databricks-gte-large-en` — Databricks computes embeddings, no key needed
# MAGIC - `pipeline_type=TRIGGERED` — syncs when you call `sync()` or on a schedule

# COMMAND ----------

# Check if index already exists
existing_indexes = [idx.name for idx in w.vector_search_indexes.list_indexes(endpoint_name=VS_ENDPOINT)]

if VS_INDEX in existing_indexes:
    print(f"Index '{VS_INDEX}' already exists — skipping creation")
else:
    print(f"Creating index '{VS_INDEX}'...")
    # Use the underlying REST API directly to avoid EmbeddingSourceColumn
    # dataclass parameter name differences across Databricks SDK versions.
    w.api_client.do(
        "POST",
        "/api/2.0/vector-search/indexes",
        body={
            "name": VS_INDEX,
            "endpoint_name": VS_ENDPOINT,
            "primary_key": PRIMARY_KEY,
            "index_type": VectorIndexType.DELTA_SYNC.value,
            "delta_sync_index_spec": {
                "source_table": SOURCE_TABLE,
                "pipeline_type": "TRIGGERED",
                "embedding_source_columns": [
                    {
                        "name": EMBEDDING_SOURCE_COLUMN,
                        "embedding_model_endpoint_name": EMBEDDING_MODEL,
                    }
                ],
            },
        },
    )
    print(f"Index '{VS_INDEX}' created — waiting for it to come online...")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 4: Wait for index to be ONLINE
# MAGIC
# MAGIC First sync takes 2-10 minutes depending on the number of chunks.
# MAGIC This cell polls every 30 seconds until the index is ready.

# COMMAND ----------

max_wait_seconds = 600  # 10 minutes
poll_interval = 30
elapsed = 0

while elapsed < max_wait_seconds:
    idx = w.vector_search_indexes.get_index(index_name=VS_INDEX)
    status = idx.status.ready_for_query if idx.status else False
    state = idx.status.index_url if idx.status else "unknown"
    print(f"[{elapsed}s] Index status — ready_for_query: {status}")
    if status:
        print(f"\nIndex '{VS_INDEX}' is ONLINE and ready to query.")
        break
    time.sleep(poll_interval)
    elapsed += poll_interval
else:
    print(f"\nWARNING: Index did not come online within {max_wait_seconds}s.")
    print("Check Catalog Explorer → helix_databricks → default → document_chunks_index for status.")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 5: Verify with a test query
# MAGIC
# MAGIC Query the index with a sample question to confirm it works end-to-end.

# COMMAND ----------

results = w.vector_search_indexes.query_index(
    index_name=VS_INDEX,
    columns=[PRIMARY_KEY, "source_file", "section", EMBEDDING_SOURCE_COLUMN],
    query_text="What is the return policy for electronics?",
    num_results=3,
)

print("Test query: 'What is the return policy for electronics?'")
print(f"Top {len(results.result.data_array)} results:")
for row in results.result.data_array:
    print(f"  chunk_id={row[0]} | source={row[1]} | section={row[2]}")
    print(f"  text: {row[3][:120]}...")
    print()

print("Vector Search index is ready. You can now run agent_pyfunc.py.")
