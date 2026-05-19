# Databricks notebook source

# COMMAND ----------

# MAGIC %md
# MAGIC # LLM Monitoring — Error Rate + Drift Detection
# MAGIC
# MAGIC **What this notebook does:**
# MAGIC 1. Reads the Inference Table that auto-logs every request to `helix-shopstream-agent`
# MAGIC 2. Checks whether the error rate in the last 15 minutes is above 5%
# MAGIC 3. Checks whether average response length has drifted by more than 50% vs. the 7-day baseline
# MAGIC 4. Raises RuntimeError on any alert — causes the job to fail and Databricks sends an email
# MAGIC
# MAGIC **Prerequisites:**
# MAGIC - Inference Tables enabled on `helix-shopstream-agent`
# MAGIC   (Serving → helix-shopstream-agent → Edit → Inference Tables → Enable)
# MAGIC - Table exists: `helix_databricks.ml.shopstream_inference_logs`
# MAGIC
# MAGIC **Schedule:** runs every 15 minutes via `helix_llm_monitoring` Workflows job

# COMMAND ----------

import sys
import os

# Add the repo root to sys.path so we can import ai_platform modules.
# In Databricks Repos, the working directory is the repo root.
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

# COMMAND ----------

from ai_platform.monitoring import check_error_rate, check_response_length_drift

# COMMAND ----------

# MAGIC %md
# MAGIC ## Check 1: Error rate (last 15 minutes)

# COMMAND ----------

print("=== Error rate check ===")
# Raises RuntimeError if error rate > 5% — fails the job, triggers email alert.
result = check_error_rate(spark)
print(f"Total requests: {result['total']}")
print(f"Errors: {result['errors']}")
print(f"Error rate: {result['error_rate']:.1%}")
print(f"Alert: {result['alert']}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Check 2: Response length drift (last 24 hours vs. 7-day baseline)

# COMMAND ----------

print("=== Response length drift check ===")
drift = check_response_length_drift(spark)
print(f"Baseline avg length: {drift.get('baseline_avg', 'n/a')}")
print(f"Current avg length:  {drift.get('current_avg', 'n/a')}")
print(f"Drift ratio:         {drift.get('drift_ratio', 'n/a')}")
print(f"Alert:               {drift['alert']}")
if drift.get("reason"):
    print(f"Reason:              {drift['reason']}")

# Raise on drift alert so the job fails and Databricks sends an email.
if drift["alert"]:
    raise RuntimeError(drift["reason"])

print("\nAll checks passed.")
