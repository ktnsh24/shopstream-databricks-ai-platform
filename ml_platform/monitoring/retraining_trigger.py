# Databricks notebook source
# MAGIC %md
# MAGIC # Retraining Trigger
# MAGIC Runs daily as a Databricks Job. On most days it does nothing.
# MAGIC When drift_detector reports PSI > 0.2 on any feature, it retrains both models
# MAGIC and logs the new runs to MLflow for review.
# MAGIC
# MAGIC Promotion is NOT automated — a human must run promote_model.py after reviewing
# MAGIC the new runs in the MLflow UI.

from pyspark.sql import SparkSession
from ml_platform.monitoring.drift_detector import detect_drift
from ml_platform.churn.train import train as train_churn
from ml_platform.forecasting.train import train as train_forecast

DRIFT_THRESHOLD = 0.2


def maybe_retrain(spark: SparkSession) -> None:
    """
    Check drift. If any feature has PSI > DRIFT_THRESHOLD, retrain both models.
    Never promotes automatically — leaves that decision to the human.
    """
    drift_results = detect_drift(spark)

    high_drift_features = [
        feat for feat, r in drift_results.items()
        if r.get("drift") == "high"
    ]

    if not high_drift_features:
        print("No significant drift detected. Skipping retraining.")
        return

    print(f"High drift detected in: {high_drift_features}")
    print("Triggering retraining of churn and forecast models...")

    churn_run_id    = train_churn(spark)
    forecast_run_id = train_forecast(spark)

    print(f"Churn training run   : {churn_run_id}")
    print(f"Forecast training run: {forecast_run_id}")
    print(
        "\nRetraining complete. Review both runs in the MLflow UI before promoting:\n"
        "  python ml_platform/registry/promote_model.py "
        "--model-name helix-churn-prediction --min-auc 0.75\n"
        "  python ml_platform/registry/promote_model.py "
        "--model-name helix-revenue-forecast  --min-auc 0.0"
    )


if __name__ == "__main__":
    spark = SparkSession.builder.getOrCreate()
    maybe_retrain(spark)
