# Databricks notebook source

# COMMAND ----------
# MAGIC %md
# MAGIC # ShopStream — Embed Documents for Vector Search
# MAGIC
# MAGIC **What this notebook does:**
# MAGIC 1. Defines ShopStream document chunks (return policy, warranty, product guides)
# MAGIC 2. Writes them to a Delta table: `helix_databricks.default.document_chunks`
# MAGIC 3. That Delta table is the source for the Vector Search index (next notebook)
# MAGIC
# MAGIC **Run this notebook once** to seed the document store. Re-run whenever documents change.
# MAGIC
# MAGIC **Prerequisites:** Unity Catalog catalog `helix_databricks` must exist (created by Terraform).

# COMMAND ----------

from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, IntegerType, StringType

# COMMAND ----------

# Constants
CATALOG = "helix_databricks"
DATABASE = "default"
TABLE = f"{CATALOG}.{DATABASE}.document_chunks"

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 1: Define ShopStream document chunks
# MAGIC
# MAGIC In production these would be extracted from PDFs or a CMS.
# MAGIC For Phase 04, we define them inline — same content, zero infrastructure dependency.

# COMMAND ----------

DOCUMENT_CHUNKS = [
    # ── Return policy ──────────────────────────────────────────────────────
    {
        "chunk_id": "return-policy-001",
        "source_file": "return-policy.pdf",
        "section": "General Returns",
        "chunk_text": (
            "ShopStream accepts returns within 30 days of delivery. "
            "Items must be in original condition with all tags attached. "
            "Electronics and software have a 14-day return window. "
            "Personalised or custom-printed items cannot be returned."
        ),
    },
    {
        "chunk_id": "return-policy-002",
        "source_file": "return-policy.pdf",
        "section": "Return Process",
        "chunk_text": (
            "To initiate a return, visit My Orders in the ShopStream app and select Return Item. "
            "You will receive a prepaid shipping label by email within 24 hours. "
            "Refunds are processed within 5 business days of receiving the returned item. "
            "Original shipping costs are non-refundable unless the item was defective."
        ),
    },
    {
        "chunk_id": "return-policy-003",
        "source_file": "return-policy.pdf",
        "section": "Exchanges",
        "chunk_text": (
            "ShopStream does not process direct exchanges. "
            "To exchange an item, return the original and place a new order. "
            "If the item you want is out of stock, use the Notify Me feature on the product page."
        ),
    },
    # ── Warranty ───────────────────────────────────────────────────────────
    {
        "chunk_id": "warranty-001",
        "source_file": "warranty-policy.pdf",
        "section": "Coverage",
        "chunk_text": (
            "All ShopStream products carry a 2-year manufacturer warranty from the date of purchase. "
            "The warranty covers manufacturing defects in materials and workmanship. "
            "It does not cover damage from misuse, accidents, unauthorised modifications, or normal wear and tear."
        ),
    },
    {
        "chunk_id": "warranty-002",
        "source_file": "warranty-policy.pdf",
        "section": "Outdoor Gear",
        "chunk_text": (
            "Outdoor gear used beyond its rated conditions voids the warranty. "
            "Example: a tent rated for 3-season use has no warranty coverage for damage sustained in winter expeditions. "
            "Always check the product rating before use."
        ),
    },
    {
        "chunk_id": "warranty-003",
        "source_file": "warranty-policy.pdf",
        "section": "How to Claim",
        "chunk_text": (
            "To make a warranty claim, contact ShopStream support with proof of purchase and photos of the defect. "
            "Claims are reviewed within 3 business days. "
            "Approved claims receive a replacement item or store credit at ShopStream's discretion."
        ),
    },
    # ── Alpine Pro Tent ────────────────────────────────────────────────────
    {
        "chunk_id": "alpine-tent-001",
        "source_file": "alpine-pro-tent-guide.pdf",
        "section": "Specifications",
        "chunk_text": (
            "The Alpine Pro Tent is a 4-season tent rated for temperatures down to -20 degrees Celsius. "
            "It accommodates up to 3 people and weighs 2.8 kg packed. "
            "Packed dimensions: 55 cm x 18 cm. "
            "Setup time is approximately 15 minutes with two people."
        ),
    },
    {
        "chunk_id": "alpine-tent-002",
        "source_file": "alpine-pro-tent-guide.pdf",
        "section": "Known Issues",
        "chunk_text": (
            "Early production batches with lot codes A100 to A340 had seam sealing defects. "
            "Tents from these batches may leak at the seams in heavy rain. "
            "Lot code is printed on the inner label near the door zipper. "
            "If your tent has a lot code in this range, contact support for a free replacement."
        ),
    },
    {
        "chunk_id": "alpine-tent-003",
        "source_file": "alpine-pro-tent-guide.pdf",
        "section": "Care",
        "chunk_text": (
            "Always dry the tent completely before storing to prevent mould. "
            "Store loosely in a breathable bag — never compressed in the stuff sack long-term. "
            "Clean with a soft cloth and mild soap. Do not use bleach or machine wash."
        ),
    },
    # ── Shipping policy ────────────────────────────────────────────────────
    {
        "chunk_id": "shipping-001",
        "source_file": "shipping-policy.pdf",
        "section": "Delivery Times",
        "chunk_text": (
            "Standard delivery takes 3 to 5 business days within the Netherlands. "
            "Express delivery takes 1 to 2 business days and costs EUR 4.95. "
            "Orders over EUR 50 qualify for free standard shipping. "
            "International shipping to EU countries takes 5 to 10 business days."
        ),
    },
    {
        "chunk_id": "shipping-002",
        "source_file": "shipping-policy.pdf",
        "section": "Tracking",
        "chunk_text": (
            "A tracking link is sent by email when your order ships. "
            "You can also track your order in the ShopStream app under My Orders. "
            "If your tracking shows delivered but you have not received the parcel, "
            "wait 24 hours before contacting support — carriers sometimes scan ahead."
        ),
    },
    # ── FAQ ────────────────────────────────────────────────────────────────
    {
        "chunk_id": "faq-001",
        "source_file": "faq.pdf",
        "section": "Orders",
        "chunk_text": (
            "Can I cancel an order? Yes, within 1 hour of placing the order via My Orders. "
            "After 1 hour the order enters fulfilment and cannot be cancelled — use the return process instead. "
            "Can I change the delivery address? Only within the same 1-hour window."
        ),
    },
    {
        "chunk_id": "faq-002",
        "source_file": "faq.pdf",
        "section": "Payments",
        "chunk_text": (
            "ShopStream accepts iDEAL, credit card (Visa, Mastercard), PayPal, and Klarna pay-later. "
            "All prices include 21% Dutch VAT. "
            "VAT invoices are available in My Orders for business customers."
        ),
    },
    {
        "chunk_id": "faq-003",
        "source_file": "faq.pdf",
        "section": "Loyalty",
        "chunk_text": (
            "ShopStream Rewards gives 1 point per EUR 1 spent. "
            "100 points = EUR 1 discount on your next order. "
            "Points expire after 12 months of account inactivity. "
            "Bonus point events run every quarter — check the app for current promotions."
        ),
    },
    {
        "chunk_id": "faq-004",
        "source_file": "faq.pdf",
        "section": "Gift Cards",
        "chunk_text": (
            "ShopStream gift cards are available in EUR 10, EUR 25, EUR 50, and EUR 100 denominations. "
            "Gift cards do not expire. "
            "They cannot be used to purchase other gift cards or exchanged for cash."
        ),
    },
]

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 2: Write chunks to Delta table
# MAGIC
# MAGIC The table uses `chunk_id` as primary key.
# MAGIC We OVERWRITE so re-running this notebook is safe — no duplicates.

# COMMAND ----------

spark.sql(f"CREATE CATALOG IF NOT EXISTS {CATALOG}")
spark.sql(f"CREATE DATABASE IF NOT EXISTS {CATALOG}.{DATABASE}")

schema = StructType([
    StructField("chunk_id", StringType(), nullable=False),
    StructField("source_file", StringType(), nullable=True),
    StructField("section", StringType(), nullable=True),
    StructField("chunk_text", StringType(), nullable=False),
])

df = spark.createDataFrame(DOCUMENT_CHUNKS, schema=schema)

(
    df.write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(TABLE)
)

count = spark.table(TABLE).count()
print(f"Wrote {count} document chunks to {TABLE}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 3: Verify
# MAGIC
# MAGIC Spot-check — print the first 5 rows.

# COMMAND ----------

display(spark.table(TABLE).limit(5))

print(f"\nTotal chunks: {spark.table(TABLE).count()}")
print(f"Unique source files: {spark.table(TABLE).select('source_file').distinct().count()}")
print("\nDone. Run create_index.py next to build the Vector Search index on this table.")
