# Databricks notebook source
# MAGIC %md
# MAGIC # Revenue Forecasting — Training
# MAGIC Trains a LightGBM model to predict ShopStream's daily net revenue for the next 7 days.
# MAGIC Reads from `helix_gold.revenue.fct_revenue_daily`, engineers time-series features,
# MAGIC trains the model, and registers it in the MLflow Model Registry.

# COMMAND ----------

# MAGIC %pip install lightgbm==3.3.5 --quiet

# COMMAND ----------

import mlflow
import mlflow.lightgbm
import lightgbm as lgb
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

# COMMAND ----------

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add calendar and lag features. Drop rows with NaN (first N rows after lagging)."""
    df = df.sort_values("order_date").copy()
    df["order_date"] = pd.to_datetime(df["order_date"])

    # Calendar features — tell the model what day/week/month it is
    df["day_of_week"]  = df["order_date"].dt.dayofweek          # Mon=0, Sun=6
    df["day_of_month"] = df["order_date"].dt.day
    df["month"]        = df["order_date"].dt.month
    df["week_of_year"] = df["order_date"].dt.isocalendar().week.astype(int)

    # Lag features — yesterday, 3 days ago, same day last week, same day 2 weeks ago
    for lag in [1, 2, 3, 7, 14]:
        df[f"lag_{lag}"] = df[TARGET_COL].shift(lag)

    # Rolling means — always shift(1) first to exclude today (prevents data leakage)
    for window in [7, 14, 30]:
        df[f"rolling_mean_{window}"] = df[TARGET_COL].shift(1).rolling(window).mean()

    df = df.dropna()
    return df


# COMMAND ----------

def split_data(df: pd.DataFrame, test_pct: float = 0.2):
    """Time-based split: last 20% of rows are the test set."""
    test_days = max(1, int(len(df) * test_pct))
    train = df.iloc[:-test_days]
    test  = df.iloc[-test_days:]
    return (
        train[FEATURE_COLS], train[TARGET_COL],
        test[FEATURE_COLS],  test[TARGET_COL],
    )


# COMMAND ----------

def train(spark: SparkSession) -> str:
    df_spark = spark.read.table("helix_gold.revenue.fct_revenue_daily")
    df = df_spark.toPandas()

    df_features = engineer_features(df)
    print(f"Rows after feature engineering: {len(df_features)}")
    if len(df_features) < 5:
        raise ValueError(f"Not enough data after feature engineering: {len(df_features)} rows. Need at least 5.")
    X_train, y_train, X_test, y_test = split_data(df_features)

    params = {
        "objective":         "regression",
        "metric":            "rmse",
        "n_estimators":      300,
        "learning_rate":     0.05,
        "max_depth":         6,
        "num_leaves":        31,
        "min_child_samples": 5,
        "subsample":         0.8,
        "colsample_bytree":  0.8,
        "verbose":           -1,
    }

    username = spark.sql("SELECT current_user()").collect()[0][0]
    mlflow.set_experiment(f"/Users/{username}/helix-revenue-forecasting")

    with mlflow.start_run() as run:
        mlflow.log_params(params)

        model = lgb.LGBMRegressor(**params)
        model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            callbacks=[lgb.early_stopping(50), lgb.log_evaluation(50)],
        )

        preds = model.predict(X_test)
        mae   = mean_absolute_error(y_test, preds)
        rmse  = np.sqrt(mean_squared_error(y_test, preds))
        r2    = model.score(X_test, y_test)

        mlflow.log_metric("mae",  round(mae, 2))
        mlflow.log_metric("rmse", round(rmse, 2))
        mlflow.log_metric("r2",   round(r2, 4))

        mlflow.lightgbm.log_model(
            model,
            artifact_path="model",
            registered_model_name="helix-revenue-forecast",
        )

        print(f"MAE={mae:.2f}  RMSE={rmse:.2f}  R2={r2:.4f}")
        return run.info.run_id


# COMMAND ----------

spark = SparkSession.builder.getOrCreate()
run_id = train(spark)
print(f"MLflow run ID: {run_id}")
