# Databricks notebook source
# MAGIC %md
# MAGIC # Revenue Forecast — PyFunc Wrapper
# MAGIC Wraps the raw LightGBM booster in the MLflow PyFunc interface so Databricks
# MAGIC Model Serving can deploy it as a REST endpoint.
# MAGIC
# MAGIC Usage:
# MAGIC   python pyfunc_wrapper.py <run_id>

import mlflow
import mlflow.pyfunc
import pandas as pd
from ml_platform.forecasting.train import FEATURE_COLS


class RevenueForecastModel(mlflow.pyfunc.PythonModel):
    """
    PyFunc wrapper for the LightGBM revenue forecast model.

    Input : DataFrame with columns matching FEATURE_COLS
    Output: DataFrame with column 'predicted_revenue'
    """

    def load_context(self, context):
        # Called once at endpoint startup — loads model into memory
        import lightgbm as lgb
        self.model = lgb.Booster(model_file=context.artifacts["lgbm_model"])

    def predict(self, context, model_input: pd.DataFrame) -> pd.DataFrame:
        predictions = self.model.predict(model_input[FEATURE_COLS])
        return pd.DataFrame({"predicted_revenue": predictions})


def log_pyfunc_model(run_id: str) -> None:
    """Re-log the trained LightGBM model as a PyFunc artefact and register it."""
    with mlflow.start_run(run_id=run_id):
        mlflow.pyfunc.log_model(
            artifact_path="pyfunc_model",
            python_model=RevenueForecastModel(),
            artifacts={"lgbm_model": f"runs:/{run_id}/model/model.lgb"},
            registered_model_name="helix-revenue-forecast-pyfunc",
        )
    print(f"Registered helix-revenue-forecast-pyfunc from run {run_id}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python pyfunc_wrapper.py <mlflow_run_id>")
    log_pyfunc_model(sys.argv[1])
