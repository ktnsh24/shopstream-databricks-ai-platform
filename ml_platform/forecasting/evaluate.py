# Databricks notebook source
# COMMAND ----------
# MAGIC %pip install "lightgbm==4.3.0" scikit-learn -q
# COMMAND ----------

import mlflow
import pandas as pd
import numpy as np
from pyspark.sql import SparkSession
from sklearn.metrics import mean_absolute_error, mean_squared_error

FEATURE_COLS = [
    "day_of_week", "day_of_month", "month", "week_of_year",
    "lag_1", "lag_2", "lag_3", "lag_7", "lag_14",
    "rolling_mean_7", "rolling_mean_14", "rolling_mean_30",
]
TARGET_COL = "net_revenue"
MODEL_UC_NAME = "helix_databricks.default.helix-revenue-forecast"

# COMMAND ----------

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("order_date").copy()
    df["order_date"] = pd.to_datetime(df["order_date"])
    df["day_of_week"]  = df["order_date"].dt.dayofweek
    df["day_of_month"] = df["order_date"].dt.day
    df["month"]        = df["order_date"].dt.month
    df["week_of_year"] = df["order_date"].dt.isocalendar().week.astype(int)
    for lag in [1, 2, 3, 7, 14]:
        df[f"lag_{lag}"] = df[TARGET_COL].shift(lag)
    for window in [7, 14, 30]:
        df[f"rolling_mean_{window}"] = df[TARGET_COL].shift(1).rolling(window).mean()
    return df.dropna()


def evaluate_latest_model(spark: SparkSession) -> dict:
    """Load @champion forecast model from UC, evaluate on last 30 days, return MAE + RMSE."""
    model = mlflow.pyfunc.load_model(f"models:/{MODEL_UC_NAME}@champion")

    df = spark.read.table("helix_gold.revenue.fct_revenue_daily").toPandas()
    df_features = engineer_features(df)
    recent = df_features.tail(30)

    preds  = model.predict(recent[FEATURE_COLS])
    actual = recent[TARGET_COL].values
    if hasattr(preds, "predicted_revenue"):
        pred_values = preds["predicted_revenue"].values
    else:
        pred_values = preds

    mae  = mean_absolute_error(actual, pred_values)
    rmse = np.sqrt(mean_squared_error(actual, pred_values))

    metrics = {"mae": round(mae, 2), "rmse": round(rmse, 2)}
    print(f"@champion forecast model — last 30 days: MAE={metrics['mae']} RMSE={metrics['rmse']}")
    return metrics

# COMMAND ----------

spark = SparkSession.builder.getOrCreate()

    metrics = {"mae": round(mae, 2), "rmse": round(rmse, 2)}
    print(f"@champion forecast model — last 30 days: MAE={metrics['mae']} RMSE={metrics['rmse']}")
    return metrics

# COMMAND ----------

spark = SparkSession.builder.getOrCreate()
evaluate_latest_model(spark)
