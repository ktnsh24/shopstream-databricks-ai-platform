# Databricks notebook source
# MAGIC %md
# MAGIC # Churn Prediction — PyFunc Wrapper
# MAGIC Wraps the trained LightGBM churn classifier in the MLflow PyFunc interface.
# MAGIC Returns both a probability score and a binary churn label.

import mlflow
import mlflow.pyfunc
import pandas as pd
from ml_platform.churn.train import FEATURE_COLS


class ChurnPredictionModel(mlflow.pyfunc.PythonModel):
    """
    PyFunc wrapper for the LightGBM churn classifier.

    Input : DataFrame with columns matching FEATURE_COLS
    Output: DataFrame with columns 'churn_probability' (0.0-1.0) and
            'is_predicted_churn' (0 or 1)
    """

    def load_context(self, context):
        import lightgbm as lgb
        self.model = lgb.Booster(model_file=context.artifacts["lgbm_model"])

    def predict(self, context, model_input: pd.DataFrame) -> pd.DataFrame:
        # lgb.Booster.predict returns probabilities directly for binary classifiers
        proba = self.model.predict(model_input[FEATURE_COLS])
        return pd.DataFrame({
            "churn_probability":  proba,
            "is_predicted_churn": (proba > 0.5).astype(int),
        })


def log_pyfunc_model(run_id: str) -> None:
    """Re-log the trained churn model as a PyFunc artefact and register it."""
    with mlflow.start_run(run_id=run_id):
        mlflow.pyfunc.log_model(
            artifact_path="pyfunc_model",
            python_model=ChurnPredictionModel(),
            artifacts={"lgbm_model": f"runs:/{run_id}/model/model.lgb"},
            registered_model_name="helix-churn-prediction-pyfunc",
        )
    print(f"Registered helix-churn-prediction-pyfunc from run {run_id}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python pyfunc_wrapper.py <mlflow_run_id>")
    log_pyfunc_model(sys.argv[1])
