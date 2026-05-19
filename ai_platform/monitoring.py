"""LLM inference monitoring — drift detection and error rate alerting.

Reads from the Databricks Inference Table that auto-logs every request/response
to the helix-shopstream-agent serving endpoint.

DE parallel:
  Inference Table = CDC log — every LLM request/response is an event row in Delta.
  Drift detection = Evidently / SageMaker Model Monitor — alert when metrics drift
                    beyond a historical baseline.

Usage (in a Databricks notebook or job):
    from pyspark.sql import SparkSession
    from ai_platform.monitoring import check_error_rate, check_response_length_drift

    spark = SparkSession.builder.getOrCreate()
    check_error_rate(spark)
    result = check_response_length_drift(spark)
    if result["alert"]:
        raise RuntimeError(result["reason"])  # triggers Databricks email alert
"""

from __future__ import annotations

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

INFERENCE_TABLE = "helix_databricks.ml.shopstream_inference_logs"

# Error rate: alert if more than 5% of requests in the last 15 minutes return HTTP 4xx/5xx.
ERROR_RATE_THRESHOLD = 0.05
ERROR_RATE_WINDOW_MINUTES = 15

# Drift: alert if average response length changes by more than 50% vs. 7-day baseline.
DRIFT_ALERT_LOW = 0.5  # current < 50% of baseline → model giving much shorter answers
DRIFT_ALERT_HIGH = 2.0  # current > 2× baseline → model rambling / hallucinating long responses
DRIFT_BASELINE_DAYS = 7
DRIFT_CHECK_HOURS = 24


# ---------------------------------------------------------------------------
# Error rate check
# ---------------------------------------------------------------------------


def check_error_rate(spark: SparkSession, window_minutes: int = ERROR_RATE_WINDOW_MINUTES) -> dict:
    """Check the fraction of failed requests in the last `window_minutes`.

    Returns dict with keys: total, errors, error_rate, alert (bool), reason.
    Raises RuntimeError if error_rate > ERROR_RATE_THRESHOLD so the Databricks
    job fails and the workspace sends an email alert to the job owner.
    """
    df = spark.table(INFERENCE_TABLE)
    recent = df.filter(
        F.col("request_timestamp") >= F.now() - F.expr(f"INTERVAL {window_minutes} MINUTES")
    )

    total = recent.count()
    if total == 0:
        return {
            "total": 0,
            "errors": 0,
            "error_rate": 0.0,
            "alert": False,
            "reason": "no requests in window",
        }

    errors = recent.filter(F.col("status_code") >= 400).count()
    error_rate = errors / total
    alert = error_rate > ERROR_RATE_THRESHOLD

    result = {
        "total": total,
        "errors": errors,
        "error_rate": round(error_rate, 4),
        "alert": alert,
        "reason": (
            f"LLM error rate {error_rate:.1%} in last {window_minutes} min"
            f" ({errors}/{total} requests)"
            if alert
            else ""
        ),
    }

    if alert:
        raise RuntimeError(result["reason"])

    return result


# ---------------------------------------------------------------------------
# Response length drift detection
# ---------------------------------------------------------------------------


def check_response_length_drift(
    spark: SparkSession,
    window_hours: int = DRIFT_CHECK_HOURS,
    baseline_days: int = DRIFT_BASELINE_DAYS,
) -> dict:
    """Compare average response length in the last `window_hours` vs. the prior `baseline_days`.

    Why response length? It is a cheap quality proxy available in every inference row:
    - A sudden drop (< 50% of baseline) suggests tool failures → the agent can't fetch
      context so it gives a short fallback answer.
    - A sudden spike (> 2× baseline) suggests the model started rambling or hallucinating
      very long answers.

    Returns dict with keys: baseline_avg, current_avg, drift_ratio, alert (bool), reason.
    Returns {"alert": False, "reason": "insufficient data"} if not enough history yet.
    """
    df = spark.table(INFERENCE_TABLE)

    # Baseline: the 7 days BEFORE the current check window (not including the window itself).
    baseline_row = (
        df.filter(F.col("request_timestamp") >= F.now() - F.expr(f"INTERVAL {baseline_days} DAYS"))
        .filter(F.col("request_timestamp") < F.now() - F.expr(f"INTERVAL {window_hours} HOURS"))
        .agg(F.avg(F.length("response")).alias("avg_len"))
        .collect()
    )

    # Current window: the last `window_hours`.
    current_row = (
        df.filter(F.col("request_timestamp") >= F.now() - F.expr(f"INTERVAL {window_hours} HOURS"))
        .agg(F.avg(F.length("response")).alias("avg_len"))
        .collect()
    )

    baseline_avg = baseline_row[0]["avg_len"] if baseline_row else None
    current_avg = current_row[0]["avg_len"] if current_row else None

    if baseline_avg is None or current_avg is None or baseline_avg == 0:
        return {"alert": False, "reason": "insufficient data — no baseline yet"}

    drift_ratio = current_avg / baseline_avg
    alert = drift_ratio < DRIFT_ALERT_LOW or drift_ratio > DRIFT_ALERT_HIGH

    return {
        "baseline_avg": round(baseline_avg, 1),
        "current_avg": round(current_avg, 1),
        "drift_ratio": round(drift_ratio, 3),
        "alert": alert,
        "reason": (
            f"Response length changed by {(drift_ratio - 1):+.0%}"
            f" vs. {baseline_days}-day baseline"
            if alert
            else ""
        ),
    }


# ---------------------------------------------------------------------------
# Entry point — runs as a Databricks job task
# ---------------------------------------------------------------------------


def run_llm_monitoring() -> None:
    """Entry point for the helix_llm_monitoring Databricks job.

    Checks both error rate and response length drift.
    Raises RuntimeError on any alert — job failure triggers Databricks email.
    """
    spark = SparkSession.builder.getOrCreate()

    # Error rate check
    check_error_rate(spark)

    # Drift detection
    drift = check_response_length_drift(spark)
    if drift["alert"]:
        raise RuntimeError(drift["reason"])
