# Databricks notebook source
# COMMAND ----------
# MAGIC %md
# MAGIC # Churn Prediction — PyFunc Wrapper
# MAGIC Wraps the trained LightGBM churn classifier in the MLflow PyFunc interface.
# MAGIC Returns both a probability score and a binary churn label.

# COMMAND ----------

import mlflow
import mlflow.pyfunc
from mlflow.models import infer_signature
import pandas as pd

FEATURE_COLS = [
    "days_since_last_order", "total_orders", "total_spent",
    "avg_order_value", "return_rate", "days_since_signup",
]
MODEL_UC_NAME = "helix_databricks.default.helix-churn-prediction"
PYFUNC_UC_NAME = "helix_databricks.default.helix-churn-prediction-pyfunc"

# COMMAND ----------

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
        proba = self.model.predict(model_input[FEATURE_COLS])
        return pd.DataFrame({
            "churn_probability":  proba,
            "is_predicted_churn": (proba > 0.5).astype(int),
        })

# COMMAND ----------
# Find the latest churn training run and wrap it as a PyFunc model

client = mlflow.tracking.MlflowClient()
versions = client.search_model_versions(f"name='{MODEL_UC_NAME}'")
if not versions:
    raise RuntimeError(f"No versions found for {MODEL_UC_NAME}. Run train.py first.")

latest = sorted(versions, key=lambda v: int(v.version))[-1]
run_id = latest.run_id
print(f"Wrapping {MODEL_UC_NAME} v{latest.version} (run {run_id}) as PyFunc")

with mlflow.start_run():
    sample_input = pd.DataFrame([{col: 0.0 for col in FEATURE_COLS}])
    sample_output = pd.DataFrame({"churn_probability": [0.0], "is_predicted_churn": [0]})
    signature = infer_signature(sample_input, sample_output)
    mlflow.pyfunc.log_model(
        artifact_path="pyfunc_model",
        python_model=ChurnPredictionModel(),
        artifacts={"lgbm_model": f"runs:/{run_id}/model/model.lgb"},
        registered_model_name=PYFUNC_UC_NAME,
        signature=signature,
    )
print(f"Registered {PYFUNC_UC_NAME}")
