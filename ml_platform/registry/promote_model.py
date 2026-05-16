# Databricks notebook source
# MAGIC %md
# MAGIC # Model Registry — Promote to Production
# MAGIC Checks the Staging model's AUC against a minimum threshold, archives the
# MAGIC current Production version, and promotes the Staging version.
# MAGIC
# MAGIC Run manually after reviewing a new training run in the MLflow UI.
# MAGIC Never run automatically — a human must approve promotion.
# MAGIC
# MAGIC Usage:
# MAGIC   python promote_model.py --model-name helix-churn-prediction --min-auc 0.75

import argparse
import mlflow
from mlflow.tracking import MlflowClient


def promote_to_production(model_name: str, min_auc: float = 0.75) -> None:
    """
    Promote the Staging version of model_name to Production if AUC >= min_auc.
    Archives the current Production version first.
    """
    client = MlflowClient()

    staging_versions = client.get_latest_versions(model_name, stages=["Staging"])
    if not staging_versions:
        print(f"No Staging version found for {model_name}. Nothing to promote.")
        return

    staging = staging_versions[0]
    run = client.get_run(staging.run_id)
    metrics = run.data.metrics

    # Find any AUC-related metric key (handles: 'auc', 'test_auc', 'eval_auc')
    auc_key = next((k for k in metrics if "auc" in k.lower()), None)
    if auc_key and metrics[auc_key] < min_auc:
        print(
            f"{model_name} v{staging.version} AUC={metrics[auc_key]:.4f} "
            f"is below threshold {min_auc}. Not promoting."
        )
        return

    # Archive the current Production version so the slot is free
    current_production = client.get_latest_versions(model_name, stages=["Production"])
    if current_production:
        client.transition_model_version_stage(
            name=model_name,
            version=current_production[0].version,
            stage="Archived",
        )
        print(f"Archived {model_name} v{current_production[0].version}")

    client.transition_model_version_stage(
        name=model_name,
        version=staging.version,
        stage="Production",
    )
    print(f"Promoted {model_name} v{staging.version} to Production")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Promote MLflow model to Production")
    parser.add_argument("--model-name", required=True, help="Registered model name")
    parser.add_argument("--min-auc",    type=float, default=0.75,
                        help="Minimum AUC required to promote (default: 0.75)")
    args = parser.parse_args()
    promote_to_production(args.model_name, args.min_auc)
