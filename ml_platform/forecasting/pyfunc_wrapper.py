# Databricks notebook source
# COMMAND ----------
# MAGIC %pip install "mlflow==2.13.2" "lightgbm==4.3.0" scikit-learn pandas "typing_extensions>=4.6.0" -q
# COMMAND ----------

import mlflow
import mlflow.pyfunc
from mlflow.models import infer_signature
import pandas as pd

FEATURE_COLS = [
    "day_of_week", "day_of_month", "month", "week_of_year",
    "lag_1", "lag_2", "lag_3", "lag_7", "lag_14",
    "rolling_mean_7", "rolling_mean_14", "rolling_mean_30",
]
MODEL_UC_NAME = "helix_databricks.default.helix-revenue-forecast"
PYFUNC_UC_NAME = "helix_databricks.default.helix-revenue-forecast-pyfunc"

# COMMAND ----------

class RevenueForecastModel(mlflow.pyfunc.PythonModel):
    """
    PyFunc wrapper for the LightGBM revenue forecast model.

    Input : DataFrame with columns matching FEATURE_COLS
    Output: DataFrame with column 'predicted_revenue'
    """

    def load_context(self, context):
        import lightgbm as lgb
        self.model = lgb.Booster(model_file=context.artifacts["lgbm_model"])

    def predict(self, context, model_input: pd.DataFrame) -> pd.DataFrame:
        predictions = self.model.predict(model_input[FEATURE_COLS])
        return pd.DataFrame({"predicted_revenue": predictions})

# COMMAND ----------
# Find the latest forecast training run and wrap it as a PyFunc model

client = mlflow.tracking.MlflowClient()
versions = client.search_model_versions(f"name='{MODEL_UC_NAME}'")
if not versions:
    raise RuntimeError(f"No versions found for {MODEL_UC_NAME}. Run train.py first.")

latest = sorted(versions, key=lambda v: int(v.version))[-1]
run_id = latest.run_id
print(f"Wrapping {MODEL_UC_NAME} v{latest.version} (run {run_id}) as PyFunc")

with mlflow.start_run():
    sample_input = pd.DataFrame([{col: 0.0 for col in FEATURE_COLS}])
    sample_output = pd.DataFrame({"predicted_revenue": [0.0]})
    signature = infer_signature(sample_input, sample_output)
    mlflow.pyfunc.log_model(
        artifact_path="pyfunc_model",
        python_model=RevenueForecastModel(),
        artifacts={"lgbm_model": f"runs:/{run_id}/model/model.lgb"},
        registered_model_name=PYFUNC_UC_NAME,
        signature=signature,
    )
print(f"Registered {PYFUNC_UC_NAME}")
