"""
Inference Table Configuration

Inference Tables are auto-created by Databricks when you enable logging on Model Serving endpoints.
This config maps models to their inference table locations and monitoring thresholds.
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class InferenceTableConfig:
    """Configuration for a single model's inference table."""

    model_name: str
    catalog: str = "helix_gold"
    schema: str = "ml_platform"
    table_name: str = None  # Auto-generated if None
    enabled: bool = True

    # Monitoring thresholds (alerts if exceeded)
    latency_p95_threshold_ms: float = 500.0
    latency_p99_threshold_ms: float = 1000.0
    error_rate_threshold_pct: float = 1.0
    drift_threshold_pct: float = 10.0

    def __post_init__(self):
        if self.table_name is None:
            self.table_name = f"{self.model_name}_predictions"

    @property
    def full_table_name(self) -> str:
        return f"{self.catalog}.{self.schema}.{self.table_name}"


# Define inference tables for each model
INFERENCE_TABLE_CONFIGS = {
    "forecast_model": InferenceTableConfig(
        model_name="forecast_model",
        table_name="forecast_model_predictions",
        latency_p95_threshold_ms=500.0,
        error_rate_threshold_pct=1.0,
        drift_threshold_pct=10.0,
    ),
    "churn_model": InferenceTableConfig(
        model_name="churn_model",
        table_name="churn_model_predictions",
        latency_p95_threshold_ms=400.0,
        error_rate_threshold_pct=0.5,
        drift_threshold_pct=8.0,
    ),
}


def get_inference_table_config(model_name: str) -> Optional[InferenceTableConfig]:
    """Get config for a specific model, or None if not found."""
    return INFERENCE_TABLE_CONFIGS.get(model_name)


def get_all_enabled_inference_tables() -> Dict[str, str]:
    """Get mapping of model_name -> full_table_name for all enabled tables."""
    return {
        name: config.full_table_name
        for name, config in INFERENCE_TABLE_CONFIGS.items()
        if config.enabled
    }


# Example: How to enable a new model's inference table
# INFERENCE_TABLE_CONFIGS["new_model"] = InferenceTableConfig(
#     model_name="new_model",
#     table_name="new_model_predictions",
#     latency_p95_threshold_ms=300.0,  # Tighter SLO
#     error_rate_threshold_pct=0.1,    # Strict error tolerance
# )
