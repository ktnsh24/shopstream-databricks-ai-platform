# Databricks notebook source
# COMMAND ----------
# MAGIC %pip install mlflow lightgbm scikit-learn pandas
# COMMAND ----------
# MAGIC %md
# MAGIC # Churn Prediction — Training
# MAGIC Trains a LightGBM binary classifier to predict whether a customer will stop
# MAGIC buying in the next 90 days. Reads from `helix_gold.customers.fct_customer_metrics`.

# COMMAND ----------

# MAGIC %pip install lightgbm==3.3.5 --quiet

# COMMAND ----------

import mlflow
import mlflow.lightgbm
from mlflow.models import infer_signature
import lightgbm as lgb
import pandas as pd
import numpy as np
from pyspark.sql import SparkSession
from sklearn.metrics import roc_auc_score, precision_score, recall_score
from sklearn.model_selection import train_test_split

FEATURE_COLS = [
    "total_orders",
    "total_spend",
    "avg_order_value",
    "days_since_last_order",
    "total_returns",
]
TARGET_COL = "is_churned"

# COMMAND ----------

def create_churn_labels(df: pd.DataFrame, churn_days: int = 90) -> pd.DataFrame:
    """Label customers as churned if they have not ordered in churn_days days."""
    df = df.copy()
    df["is_churned"] = (df["days_since_last_order"] > churn_days).astype(int)
    return df

# COMMAND ----------

def train(spark: SparkSession) -> str:
    df = spark.read.table("helix_gold.customers.fct_customer_metrics").toPandas()
    df = create_churn_labels(df)

    df_model = df[FEATURE_COLS + [TARGET_COL]].dropna()
    print(f"Rows after dropna: {len(df_model)}, churned: {df_model[TARGET_COL].sum()}, not churned: {(df_model[TARGET_COL]==0).sum()}")
    X = df_model[FEATURE_COLS]
    y = df_model[TARGET_COL]

    # stratify only if both classes exist
    stratify = y if y.nunique() > 1 else None
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=stratify
    )

    # scale_pos_weight corrects for class imbalance (churned = minority class)
    pos_weight = (y_train == 0).sum() / max((y_train == 1).sum(), 1)

    params = {
        "objective":         "binary",
        "metric":            "auc",
        "n_estimators":      200,
        "learning_rate":     0.05,
        "max_depth":         5,
        "num_leaves":        20,
        "min_child_samples": 5,
        "scale_pos_weight":  pos_weight,
        "verbose":           -1,
    }

    username = spark.sql("SELECT current_user()").collect()[0][0]
    mlflow.set_experiment(f"/Users/{username}/helix-churn-prediction")

    with mlflow.start_run() as run:
        mlflow.log_params(params)

        model = lgb.LGBMClassifier(**params)
        model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            callbacks=[lgb.early_stopping(30), lgb.log_evaluation(50)],
        )

        preds_proba = model.predict_proba(X_test)[:, 1]
        preds_class = (preds_proba > 0.5).astype(int)

        # roc_auc_score requires both classes in test set
        auc = roc_auc_score(y_test, preds_proba) if y_test.nunique() > 1 else 0.0
        precision = precision_score(y_test, preds_class, zero_division=0)
        recall    = recall_score(y_test, preds_class, zero_division=0)

        mlflow.log_metric("auc",       round(auc, 4))
        mlflow.log_metric("precision", round(precision, 4))
        mlflow.log_metric("recall",    round(recall, 4))

        signature = infer_signature(X_train, model.predict(X_train))
        mlflow.lightgbm.log_model(
            model,
            artifact_path="model",
            registered_model_name="helix-churn-prediction",
            signature=signature,
            input_example=X_train.iloc[:5],
        )

        print(f"AUC={auc:.4f}  precision={precision:.4f}  recall={recall:.4f}")
        return run.info.run_id

# COMMAND ----------

spark = SparkSession.builder.getOrCreate()
run_id = train(spark)
print(f"MLflow run ID: {run_id}")
