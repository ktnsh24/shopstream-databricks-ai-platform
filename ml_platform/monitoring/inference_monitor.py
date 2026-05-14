"""
Inference Table Monitoring for Model Serving Endpoints

Queries and monitors Databricks Inference Tables for:
- Latency trends
- Model version comparisons  
- Error rates
- Data drift detection

These tables are auto-created by Databricks when you enable inference logging
on Model Serving endpoints.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class InferenceTableMonitor:
    """Monitor and analyze inference tables for production models."""

    def __init__(self, catalog: str = "helix_gold", schema: str = "ml_platform"):
        self.catalog = catalog
        self.schema = schema
        self.inference_tables = {
            "forecast": f"{catalog}.{schema}.forecast_model_predictions",
            "churn": f"{catalog}.{schema}.churn_model_predictions",
        }

    def build_latency_query(
        self, model_name: str, days_back: int = 7
    ) -> str:
        """Query latency trends over time."""
        table = self.inference_tables.get(model_name)
        if not table:
            raise ValueError(f"Unknown model: {model_name}")

        return f"""
SELECT 
    DATE(timestamp) as date,
    COUNT(*) as total_predictions,
    ROUND(AVG(latency_ms), 2) as avg_latency,
    ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms), 2) as p95_latency,
    ROUND(PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY latency_ms), 2) as p99_latency,
    COUNT(CASE WHEN error IS NOT NULL THEN 1 END) as error_count,
    COUNT(CASE WHEN error IS NOT NULL THEN 1 END) * 100.0 / COUNT(*) as error_rate_pct
FROM {table}
WHERE timestamp >= DATE_SUB(CURRENT_DATE(), {days_back})
GROUP BY DATE(timestamp)
ORDER BY date DESC
"""

    def build_model_version_comparison_query(
        self, model_name: str, hours_back: int = 24
    ) -> str:
        """Compare performance across model versions."""
        table = self.inference_tables.get(model_name)
        if not table:
            raise ValueError(f"Unknown model: {model_name}")

        return f"""
SELECT 
    model_version,
    COUNT(*) as total_calls,
    ROUND(AVG(latency_ms), 2) as avg_latency_ms,
    ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms), 2) as p95_latency_ms,
    COUNT(CASE WHEN error IS NOT NULL THEN 1 END) as errors,
    COUNT(CASE WHEN error IS NOT NULL THEN 1 END) * 100.0 / COUNT(*) as error_rate_pct
FROM {table}
WHERE timestamp >= CURRENT_TIMESTAMP() - INTERVAL {hours_back} HOUR
GROUP BY model_version
ORDER BY total_calls DESC
"""

    def build_data_drift_query(
        self, model_name: str, hours_back: int = 24
    ) -> str:
        """Detect distribution shifts in input features."""
        table = self.inference_tables.get(model_name)
        if not table:
            raise ValueError(f"Unknown model: {model_name}")

        return f"""
SELECT 
    DATE_TRUNC('hour', timestamp) as hour,
    COUNT(*) as predictions,
    ROUND(AVG(CAST(features['amount'] as DOUBLE)), 2) as avg_amount,
    ROUND(AVG(CAST(features['age'] as DOUBLE)), 2) as avg_age,
    ROUND(AVG(CAST(features['tenure'] as DOUBLE)), 2) as avg_tenure
FROM {table}
WHERE timestamp >= CURRENT_TIMESTAMP() - INTERVAL {hours_back} HOUR
GROUP BY DATE_TRUNC('hour', timestamp)
ORDER BY hour DESC
"""

    def build_errors_query(
        self, model_name: str, hours_back: int = 24
    ) -> str:
        """Find all errors in recent predictions."""
        table = self.inference_tables.get(model_name)
        if not table:
            raise ValueError(f"Unknown model: {model_name}")

        return f"""
SELECT 
    timestamp,
    model_version,
    error,
    request_id,
    DATEDIFF(MILLISECOND, timestamp, CURRENT_TIMESTAMP()) as age_ms
FROM {table}
WHERE error IS NOT NULL
  AND timestamp >= CURRENT_TIMESTAMP() - INTERVAL {hours_back} HOUR
ORDER BY timestamp DESC
LIMIT 100
"""

    def get_monitoring_summary(self, model_name: str) -> Dict[str, Any]:
        """
        One-liner summary of model health from inference table.

        Returns dict with: error_count, avg_latency, p95_latency, p99_latency, model_versions_active
        """
        # NOTE: This is a stub. In Phase 03, wire this to actual Databricks SQL query
        return {
            "model_name": model_name,
            "status": "healthy",
            "last_updated": datetime.now().isoformat(),
            "error_count_24h": 0,
            "avg_latency_ms": 150.0,
            "p95_latency_ms": 450.0,
            "p99_latency_ms": 890.0,
            "model_versions_active": 2,
            "queries_24h": 10000,
        }


# Example usage (for Phase 03 tutorial)
if __name__ == "__main__":
    monitor = InferenceTableMonitor()

    print("=== Latency Trend Query ===")
    print(monitor.build_latency_query("forecast", days_back=7))

    print("\n=== Model Version Comparison Query ===")
    print(monitor.build_model_version_comparison_query("churn", hours_back=24))

    print("\n=== Data Drift Query ===")
    print(monitor.build_data_drift_query("forecast", hours_back=24))

    print("\n=== Errors Query ===")
    print(monitor.build_errors_query("churn", hours_back=24))
