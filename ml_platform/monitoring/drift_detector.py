# Databricks notebook source
# MAGIC %md
# MAGIC # Drift Detector
# MAGIC Compares the statistical distribution of customer features today against the
# MAGIC distribution at training time using Population Stability Index (PSI).
# MAGIC
# MAGIC PSI thresholds:
# MAGIC   < 0.1  = no drift (normal day-to-day noise)
# MAGIC   0.1-0.2 = moderate drift — worth investigating
# MAGIC   > 0.2  = significant drift — trigger retraining

import pandas as pd
import numpy as np
from pyspark.sql import SparkSession
from ml_platform.churn.train import FEATURE_COLS

# Training data cutoff: rows loaded before this date are the baseline
TRAINING_CUTOFF = "2026-02-01"


def compute_psi(expected: np.ndarray, actual: np.ndarray, buckets: int = 10) -> float:
    """
    Compute Population Stability Index between two distributions.

    Returns a float. Higher = more drift.
    Bucket edges are derived from the expected (training) distribution so that
    a shifted actual distribution is not artificially re-bucketed.
    """
    def bucket_pct(data: np.ndarray, edges: np.ndarray) -> np.ndarray:
        counts, _ = np.histogram(data, bins=edges)
        pct = counts / len(data)
        # Replace zeros with small epsilon to avoid log(0) = undefined
        return np.where(pct == 0, 0.0001, pct)

    combined = np.concatenate([expected, actual])
    edges = np.percentile(expected, np.linspace(0, 100, buckets + 1))
    # Extend edges to cover any out-of-range values in current data
    edges[0]  = combined.min() - 1
    edges[-1] = combined.max() + 1

    exp_pct = bucket_pct(expected, edges)
    act_pct = bucket_pct(actual, edges)

    psi = float(np.sum((act_pct - exp_pct) * np.log(act_pct / exp_pct)))
    return round(psi, 4)


def detect_drift(spark: SparkSession) -> dict:
    """
    Compute PSI per feature and return a dict of {feature: {psi, drift}}.
    """
    training_df = (
        spark.read.table("helix_gold.customers.fct_customer_metrics")
        .filter(f"_loaded_at < '{TRAINING_CUTOFF}'")
        .toPandas()
    )
    current_df = (
        spark.read.table("helix_gold.customers.fct_customer_metrics")
        .filter("_loaded_at >= current_date() - interval 30 days")
        .toPandas()
    )

    results = {}
    for feature in FEATURE_COLS:
        expected = training_df[feature].dropna().values
        actual   = current_df[feature].dropna().values

        if len(expected) < 10 or len(actual) < 10:
            # Not enough data to compute a meaningful PSI
            results[feature] = {"psi": None, "drift": "insufficient_data"}
            continue

        psi  = compute_psi(expected, actual)
        drift = "high" if psi > 0.2 else ("moderate" if psi > 0.1 else "none")
        results[feature] = {"psi": psi, "drift": drift}

    print("Drift detection results:")
    for feat, r in results.items():
        print(f"  {feat}: PSI={r['psi']} ({r['drift']})")

    return results


if __name__ == "__main__":
    spark = SparkSession.builder.getOrCreate()
    detect_drift(spark)
