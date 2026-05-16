# Databricks notebook source
# COMMAND ----------
# MAGIC %pip install "lightgbm==4.3.0" scikit-learn -q
# COMMAND ----------
# Retraining Trigger
# Runs daily as a Databricks Job. Checks for drift and retrains if needed.
# Promotion is NOT automated — run promote_model.py after reviewing new runs.

import mlflow
import pandas as pd
import numpy as np
from pyspark.sql import SparkSession

DRIFT_THRESHOLD = 0.2
FEATURE_COLS = [
    "days_since_last_order", "total_orders", "total_spent",
    "avg_order_value", "return_rate", "days_since_signup",
]
TRAINING_CUTOFF = "2026-02-01"

# COMMAND ----------

def compute_psi(expected: np.ndarray, actual: np.ndarray, buckets: int = 10) -> float:
    def bucket_pct(data, edges):
        counts, _ = np.histogram(data, bins=edges)
        pct = counts / len(data)
        return np.where(pct == 0, 0.0001, pct)
    combined = np.concatenate([expected, actual])
    edges = np.percentile(expected, np.linspace(0, 100, buckets + 1))
    edges[0] = combined.min() - 1
    edges[-1] = combined.max() + 1
    exp_pct = bucket_pct(expected, edges)
    act_pct = bucket_pct(actual, edges)
    return round(float(np.sum((act_pct - exp_pct) * np.log(act_pct / exp_pct))), 4)


def detect_drift(spark: SparkSession) -> dict:
    training_df = spark.read.table("helix_gold.customers.fct_customer_metrics").filter(f"_loaded_at < '{TRAINING_CUTOFF}'").toPandas()
    current_df  = spark.read.table("helix_gold.customers.fct_customer_metrics").filter("_loaded_at >= current_date() - interval 30 days").toPandas()
    results = {}
    for feature in FEATURE_COLS:
        exp = training_df[feature].dropna().values
        act = current_df[feature].dropna().values
        if len(exp) < 10 or len(act) < 10:
            results[feature] = {"psi": None, "drift": "insufficient_data"}
            continue
        psi = compute_psi(exp, act)
        results[feature] = {"psi": psi, "drift": "high" if psi > 0.2 else ("moderate" if psi > 0.1 else "none")}
    return results

# COMMAND ----------

def maybe_retrain(spark: SparkSession) -> None:
    """Check drift. Retrain both models if any feature PSI > threshold."""
    drift_results = detect_drift(spark)
    high_drift = [f for f, r in drift_results.items() if r.get("drift") == "high"]

    if not high_drift:
        print("No significant drift detected. Skipping retraining.")
        return

    print(f"High drift detected in: {high_drift}")
    print("Triggering retraining of churn and forecast models...")

    # Import training functions inline (avoids relative import issues in notebooks)
    import importlib
    churn_train   = importlib.import_module("ml_platform.churn.train")
    forecast_train = importlib.import_module("ml_platform.forecasting.train")

    churn_run_id    = churn_train.train(spark)
    forecast_run_id = forecast_train.train(spark)

    print(f"Churn training run   : {churn_run_id}")
    print(f"Forecast training run: {forecast_run_id}")
    print("\nRetraining complete. Run promote_model.py after reviewing runs in MLflow UI.")

# COMMAND ----------

spark = SparkSession.builder.getOrCreate()
maybe_retrain(spark)
