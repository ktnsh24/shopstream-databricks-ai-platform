# Databricks notebook source
# COMMAND ----------
# MAGIC %pip install "lightgbm==4.3.0" scikit-learn -q
# COMMAND ----------
# MAGIC %md
# MAGIC # Model Registry — Promote to Champion (Unity Catalog)
# MAGIC
# MAGIC Promotes the latest version of a registered model to the `@champion` alias.
# MAGIC Unity Catalog uses aliases instead of Staging/Production stages.
# MAGIC
# MAGIC For regression models (forecasting), pass --min-auc 0.0 to skip the AUC check.
# MAGIC For classification models (churn), set --min-auc to your quality threshold.
# MAGIC
# MAGIC Run manually after reviewing a training run in the MLflow UI.
# MAGIC
# MAGIC Usage (in a Databricks notebook cell):
# MAGIC   promote_to_champion("helix_databricks.default.helix-churn-prediction", min_auc=0.75)
# MAGIC   promote_to_champion("helix_databricks.default.helix-revenue-forecast", min_auc=0.0)

# COMMAND ----------

import mlflow
from mlflow.tracking import MlflowClient


def promote_to_champion(model_name: str, min_auc: float = 0.0) -> None:
    """
    Set the @champion alias on the latest version of model_name in Unity Catalog.

    Args:
        model_name: 3-level UC name, e.g. helix_databricks.default.helix-churn-prediction
        min_auc:    Minimum AUC (or R2 for regression) required. Use 0.0 to skip check.
    """
    client = MlflowClient()

    # Get all versions, pick the most recently created one
    versions = client.search_model_versions(f"name='{model_name}'")
    if not versions:
        print(f"No versions found for {model_name}. Train the model first.")
        return

    latest = sorted(versions, key=lambda v: int(v.version))[-1]
    run = client.get_run(latest.run_id)
    metrics = run.data.metrics

    print(f"Latest version: {latest.version}  metrics: {metrics}")

    # Quality gate — check AUC for classifiers, R2 for regressors, skip if min_auc=0
    if min_auc > 0:
        auc_key = next((k for k in metrics if "auc" in k.lower()), None)
        if auc_key is None:
            print("No AUC metric found — skipping quality gate.")
        elif metrics[auc_key] < min_auc:
            print(
                f"{model_name} v{latest.version} AUC={metrics[auc_key]:.4f} "
                f"is below threshold {min_auc}. Not promoting."
            )
            return

    # Set @champion alias — replaces any previous @champion automatically
    client.set_registered_model_alias(
        name=model_name,
        alias="champion",
        version=latest.version,
    )
    print(f"Set @champion alias → {model_name} v{latest.version}")


# COMMAND ----------
# Run both promotions directly when executed as a notebook

promote_to_champion("helix_databricks.default.helix-churn-prediction", min_auc=0.75)
promote_to_champion("helix_databricks.default.helix-revenue-forecast",  min_auc=0.0)
