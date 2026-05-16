# Databricks notebook source
# MAGIC %md
# MAGIC # Churn Prediction — Production Model Evaluation
# MAGIC Loads the current Production churn model from MLflow and computes AUC
# MAGIC against all current customers. Run on a schedule to detect accuracy degradation.

import mlflow
import pandas as pd
from pyspark.sql import SparkSession
from sklearn.metrics import roc_auc_score
from ml_platform.churn.train import FEATURE_COLS, TARGET_COL, create_churn_labels


def evaluate_latest_model(spark: SparkSession) -> dict:
    """Load Production churn model, evaluate on current customers, return AUC."""
    client = mlflow.tracking.MlflowClient()

    versions = client.get_latest_versions("helix-churn-prediction", stages=["Production"])
    if not versions:
        raise RuntimeError("No Production version found for helix-churn-prediction")

    version = versions[0]
    model = mlflow.pyfunc.load_model(f"models:/helix-churn-prediction/{version.version}")

    df = spark.read.table("helix_gold.customers.fct_customer_metrics").toPandas()
    df = create_churn_labels(df)
    df_model = df[FEATURE_COLS + [TARGET_COL]].dropna()

    preds = model.predict(df_model[FEATURE_COLS])
    auc   = roc_auc_score(df_model[TARGET_COL], preds["churn_probability"])

    metrics = {"model_version": version.version, "auc": round(auc, 4)}
    print(f"Production churn model v{version.version} — AUC: {metrics['auc']}")
    return metrics


if __name__ == "__main__":
    spark = SparkSession.builder.getOrCreate()
    evaluate_latest_model(spark)
