"""ForecastTool — load the @champion revenue forecast model and predict future revenue.

Used by the agent when the user asks questions like:
  - 'What is the revenue forecast for next month?'
  - 'How much revenue do we expect in the next 7 days?'
  - 'Give me the 30-day revenue forecast'

Loads the LightGBM model registered as @champion in Unity Catalog.
"""

from __future__ import annotations

import json
import os
from datetime import date, timedelta
from typing import Any

import mlflow


MODEL_UC_NAME = "helix_databricks.default.helix-revenue-forecast"


class ForecastTool:
    name = "forecast"
    description = (
        "Predict future ShopStream revenue using the trained LightGBM forecast model. "
        "Use this tool for questions about expected revenue over a future period. "
        "Returns a daily revenue forecast as a plain-text table."
    )
    parameters = {
        "type": "object",
        "properties": {
            "horizon_days": {
                "type": "integer",
                "default": 7,
                "description": "Number of days to forecast into the future. Default 7. Max 90.",
            },
        },
        "required": [],
    }

    _model = None  # lazy-loaded once, reused across calls

    def _get_model(self):
        if self._model is None:
            self.__class__._model = mlflow.pyfunc.load_model(
                f"models:/{MODEL_UC_NAME}@champion"
            )
        return self._model

    def run(self, args: dict[str, Any]) -> str:
        horizon_days = min(int(args.get("horizon_days", 7)), 90)

        import pandas as pd

        # Build a feature DataFrame for the forecast horizon
        # Features match what train.py used: day_of_week, month, day_of_month, is_weekend
        today = date.today()
        records = []
        for i in range(1, horizon_days + 1):
            d = today + timedelta(days=i)
            records.append({
                "forecast_date": d.isoformat(),
                "day_of_week": d.weekday(),      # 0=Monday, 6=Sunday
                "month": d.month,
                "day_of_month": d.day,
                "is_weekend": int(d.weekday() >= 5),
            })
        df = pd.DataFrame(records)
        feature_cols = ["day_of_week", "month", "day_of_month", "is_weekend"]

        model = self._get_model()
        predictions = model.predict(df[feature_cols])
        df["predicted_revenue_eur"] = predictions.round(2)

        lines = [f"Revenue forecast — next {horizon_days} days", "-" * 40]
        lines.append(f"{'Date':<14} {'Predicted Revenue (EUR)':>22}")
        for _, row in df.iterrows():
            lines.append(f"{row['forecast_date']:<14} {row['predicted_revenue_eur']:>22,.2f}")
        total = df["predicted_revenue_eur"].sum()
        lines.append("-" * 40)
        lines.append(f"{'Total':.<14} {total:>22,.2f}")
        return "\n".join(lines)
