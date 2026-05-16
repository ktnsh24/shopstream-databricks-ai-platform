# Databricks notebook source
# MAGIC %md
# MAGIC # Revenue Forecast — Production Model Evaluation
# MAGIC Loads the current Production model from MLflow and measures its accuracy
# MAGIC against the last 30 days of actual revenue data.
# MAGIC Run on a schedule (daily or weekly) to detect accuracy degradation early.

import mlflow
import pandas as pd
import numpy as np
from pyspark.sql import SparkSession
from sklearn.metrics import mean_absolute_error, mean_squared_error
from ml_platform.forecasting.train import engineer_features, FEATURE_COLS, TARGET_COL


def evaluate_latest_model(spark: SparkSession) -> dict:
    """Load Production model, evaluate on last 30 days, return MAE + RMSE."""
    client = mlflow.tracking.MlflowClient()

    versions = client.get_latest_versions("helix-revenue-forecast", stages=["Production"])
    if not versions:
        raise RuntimeError("No Production version found for helix-revenue-forecast")

    model_version = versions[0]
    model = mlflow.pyfunc.load_model(
        f"models:/helix-revenue-forecast/{model_version.version}"
    )

    df = spark.read.table("helix_gold.revenue.fct_revenue_daily").toPandas()
    df_features = engineer_features(df)
    recent = df_features.tail(30)  # Most recent 30 days — not seen during training

    preds  = model.predict(recent[FEATURE_COLS])
    actual = recent[TARGET_COL].values

    mae  = mean_absolute_error(actual, preds["predicted_revenue"])
    rmse = np.sqrt(mean_squared_error(actual, preds["predicted_revenue"]))

    metrics = {
        "model_version": model_version.version,
        "mae":  round(mae, 2),
        "rmse": round(rmse, 2),
    }
    print(f"Production model v{model_version.version} — last 30 days: {metrics}")
    return metrics


if __name__ == "__main__":
    spark = SparkSession.builder.getOrCreate()
    evaluate_latest_model(spark)
