# Databricks notebook source

# COMMAND ----------
# MAGIC %md
# MAGIC # ShopStream — Create Golden Evaluation Dataset
# MAGIC
# MAGIC **What this notebook does:**
# MAGIC 1. Defines 15 ShopStream Q&A pairs (questions + expected answers + expected tool calls)
# MAGIC 2. Writes them to `helix_databricks.default.golden_dataset`
# MAGIC 3. This table is used by `evaluator.py` to score the agent
# MAGIC
# MAGIC **What a golden dataset is:**
# MAGIC A set of questions where you already know the correct answer.
# MAGIC You use it to measure how well your agent performs — like a test suite for the LLM.
# MAGIC
# MAGIC DE parallel: this is the expected output table in a data pipeline test.
# MAGIC You compare agent answers against it the same way you compare ETL output against expected rows.
# MAGIC
# MAGIC **Run once before `evaluator.py`.**

# COMMAND ----------

from pyspark.sql.types import StructType, StructField, StringType, ArrayType

# COMMAND ----------

CATALOG = "helix_databricks"
DATABASE = "default"
TABLE = f"{CATALOG}.{DATABASE}.golden_dataset"

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 1: Define the 15 golden Q&A pairs
# MAGIC
# MAGIC Each row has:
# MAGIC - `question_id` — unique ID
# MAGIC - `question` — what the user asks
# MAGIC - `expected_answer_keywords` — words that MUST appear in a correct answer
# MAGIC - `expected_tool` — which tool the agent should call to answer this
# MAGIC - `category` — type of question (metrics / documents / forecast / sql / blocked)

# COMMAND ----------

GOLDEN_QA = [
    # ── Metrics questions (agent should call query_metrics) ────────────────
    {
        "question_id": "gq-001",
        "question": "What was total revenue in the last 7 days?",
        "expected_answer_keywords": "revenue EUR",
        "expected_tool": "query_metrics",
        "category": "metrics",
    },
    {
        "question_id": "gq-002",
        "question": "How many orders did we receive yesterday?",
        "expected_answer_keywords": "orders day",
        "expected_tool": "query_metrics",
        "category": "metrics",
    },
    {
        "question_id": "gq-003",
        "question": "Show me the top 5 products by revenue this month.",
        "expected_answer_keywords": "product revenue",
        "expected_tool": "query_metrics",
        "category": "metrics",
    },
    {
        "question_id": "gq-004",
        "question": "How many customers are at high churn risk?",
        "expected_answer_keywords": "churn customer",
        "expected_tool": "query_metrics",
        "category": "metrics",
    },
    {
        "question_id": "gq-005",
        "question": "What was the return count last 30 days?",
        "expected_answer_keywords": "return",
        "expected_tool": "query_metrics",
        "category": "metrics",
    },
    # ── Document questions (agent should call search_documents) ────────────
    {
        "question_id": "gq-006",
        "question": "What is the return window for electronics?",
        "expected_answer_keywords": "14 day",
        "expected_tool": "search_documents",
        "category": "documents",
    },
    {
        "question_id": "gq-007",
        "question": "How do I initiate a return?",
        "expected_answer_keywords": "app My Orders",
        "expected_tool": "search_documents",
        "category": "documents",
    },
    {
        "question_id": "gq-008",
        "question": "Does the Alpine Pro Tent have a warranty?",
        "expected_answer_keywords": "warranty 2-year",
        "expected_tool": "search_documents",
        "category": "documents",
    },
    {
        "question_id": "gq-009",
        "question": "How long does standard shipping take?",
        "expected_answer_keywords": "3 5 business days",
        "expected_tool": "search_documents",
        "category": "documents",
    },
    {
        "question_id": "gq-010",
        "question": "What is the ShopStream Rewards loyalty programme?",
        "expected_answer_keywords": "points EUR discount",
        "expected_tool": "search_documents",
        "category": "documents",
    },
    # ── Forecast questions (agent should call forecast) ────────────────────
    {
        "question_id": "gq-011",
        "question": "What is the revenue forecast for the next 7 days?",
        "expected_answer_keywords": "EUR forecast",
        "expected_tool": "forecast",
        "category": "forecast",
    },
    {
        "question_id": "gq-012",
        "question": "How much revenue do we expect next month?",
        "expected_answer_keywords": "EUR Total",
        "expected_tool": "forecast",
        "category": "forecast",
    },
    # ── Text-to-SQL questions (agent may call text_to_sql) ─────────────────
    {
        "question_id": "gq-013",
        "question": "Which customers ordered more than 3 times in the last 30 days?",
        "expected_answer_keywords": "customer_id",
        "expected_tool": "text_to_sql",
        "category": "sql",
    },
    # ── Blocked questions (gatekeeper should block these) ─────────────────
    {
        "question_id": "gq-014",
        "question": "Write a poem about online shopping.",
        "expected_answer_keywords": "only answer questions ShopStream",
        "expected_tool": "none",
        "category": "blocked",
    },
    {
        "question_id": "gq-015",
        "question": "What is the capital of the Netherlands?",
        "expected_answer_keywords": "only answer questions ShopStream",
        "expected_tool": "none",
        "category": "blocked",
    },
]

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 2: Write to Unity Catalog

# COMMAND ----------

spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
spark.sql(f"CREATE DATABASE IF NOT EXISTS {CATALOG}.{DATABASE}")

schema = StructType([
    StructField("question_id", StringType(), nullable=False),
    StructField("question", StringType(), nullable=False),
    StructField("expected_answer_keywords", StringType(), nullable=True),
    StructField("expected_tool", StringType(), nullable=True),
    StructField("category", StringType(), nullable=True),
])

df = spark.createDataFrame(GOLDEN_QA, schema=schema)
df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(TABLE)

count = spark.table(TABLE).count()
print(f"Wrote {count} golden Q&A pairs to {TABLE}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 3: Verify

# COMMAND ----------

display(spark.table(TABLE))
print(f"\nCategory breakdown:")
spark.table(TABLE).groupBy("category").count().show()
print("\nDone. Run evaluator.py next to score the agent against this dataset.")
