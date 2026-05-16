# Databricks notebook source
# COMMAND ----------
# MAGIC %md
# MAGIC # Churn Prediction — Production Model Evaluation
# MAGIC Loads the current Production churn model from MLflow and computes AUC
# MAGIC against all current customers. Run on a schedule to detect accuracy degradation.

# COMMAND ----------

import mlflow
import pandas as pd
from pyspark.sql import SparkSession
from sklearn.metrics import roc_auc_score

FEATURE_COLS = [
    "days_since_last_order", "total_orders", "total_spent",
    "avg_order_value", "return_rate", "days_since_signup",
]
TARGET_COL = "is_churned"
MODEL_UC_NAME = "helix_databricks.default.helix-churn-prediction"

# COMMAND ----------

def create_churn_labels(df: pd.DataFrame) -> pd.DataFrame:
    """Add is_churned label: 1 if days_since_last_order > 90."""
    df = df.copy()
    df["is_churned"] = (df["days_since_last_order"] > 90).astype(int)
    return df


def evaluate_latest_model(spark: SparkSession) -> dict:
    """Load @champion churn model from UC, evaluate on current customers, return AUC."""
    model = mlflow.pyfunc.load_model(f"models:/{MODEL_UC_NAME}@champion")

    df = spark.read.table("helix_gold.customers.fct_customer_metrics").toPandas()
    df = create_churn_labels(df)
    df_model = df[FEATURE_COLS + [TARGET_COL]].dropna()

    preds = model.predict(df_model[FEATURE_COLS])
    # preds may be array or DataFrame depending on pyfunc wrapper
    if hasattr(preds, "churn_probability"):
        scores = preds["churn_probability"]
    else:
        scores = preds

    auc = roc_auc_score(df_model[TARGET_COL], scores)
    metrics = {"auc": round(auc, 4)}
    print(f"@champion churn model — AUC: {metrics['auc']}")
    return metrics

# COMMAND ----------

spark = SparkSession.builder.getOrCreate()
evaluate_latest_model(spark)
