"""Fraud specialist sub-agent.

Handles questions about blocked orders, fraud flags, suspicious transactions,
and chargeback risk.  Uses the same OpenAI-compatible Databricks endpoint as
the main orchestrator.

Courier analogy: this is the depot's security team. Every parcel (question)
routed here has a suspicious label. The team checks the order ledger and
reports back on what the flags mean.
"""

from __future__ import annotations

import json
import logging
import os

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState
from openai import OpenAI

logger = logging.getLogger(__name__)

CATALOG = "helix_databricks"
DATABASE = "default"
MAIN_AGENT_MODEL = "databricks-meta-llama-3-3-70b-instruct"
MAX_TOOL_ROUNDS = 5

_SYSTEM_PROMPT = """\
You are a fraud analyst for ShopStream. You investigate suspicious orders,
blocked transactions, and chargeback risk. You have access to revenue and
order data. Always cite order dates and amounts when available. Be concise
and factual.
"""

_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "check_revenue_anomalies",
            "description": (
                "Check daily revenue data for anomalies — days with unusually low revenue "
                "or order counts can indicate fraud events, payment failures, or system outages."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "description": "How far back to look, e.g. 'last 7 days', 'last 30 days'",
                    },
                    "threshold_pct": {
                        "type": "number",
                        "description": (
                            "Flag days where revenue is this percentage below the 14-day average. "
                            "Default: 30"
                        ),
                        "default": 30,
                    },
                },
                "required": ["period"],
            },
        },
    }
]


# ---------------------------------------------------------------------------
# Shared helpers (self-contained so this file can run without sibling imports)
# ---------------------------------------------------------------------------

def _get_databricks_host() -> str:
    return os.environ.get("DATABRICKS_HOST", "").rstrip("/")


def _get_databricks_token() -> str:
    return os.environ.get("DATABRICKS_TOKEN", "")


def _make_client() -> OpenAI:
    host = _get_databricks_host()
    host = host.removeprefix("https://").removeprefix("http://").rstrip("/")
    return OpenAI(
        api_key=_get_databricks_token(),
        base_url=f"https://{host}/serving-endpoints",
    )


def _get_warehouse_id(w: WorkspaceClient) -> str:
    wh_id = os.environ.get("DATABRICKS_SQL_WAREHOUSE_ID", "")
    if not wh_id:
        warehouses = list(w.warehouses.list())
        if warehouses:
            wh_id = warehouses[0].id
    return wh_id


def _run_sql(sql: str) -> str:
    w = WorkspaceClient()
    warehouse_id = _get_warehouse_id(w)
    if not warehouse_id:
        return "Error: no SQL warehouse available."
    response = w.statement_execution.execute_statement(
        warehouse_id=warehouse_id,
        statement=sql,
        wait_timeout="30s",
    )
    if not response.status or response.status.state != StatementState.SUCCEEDED:
        err = response.status.error if response.status else "unknown error"
        return f"Query failed: {err}"
    if not response.manifest or not response.result:
        return "Query returned no rows."
    cols = [c.name for c in response.manifest.schema.columns]
    rows = response.result.data_array or []
    if not rows:
        return "Query returned no rows."
    lines = ["  ".join(cols)]
    for row in rows:
        lines.append("  ".join(str(v) if v is not None else "NULL" for v in row))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool implementation
# ---------------------------------------------------------------------------

_PERIOD_MAP = {
    "last 7 days": "CURRENT_DATE - INTERVAL 7 DAYS",
    "last 14 days": "CURRENT_DATE - INTERVAL 14 DAYS",
    "last 30 days": "CURRENT_DATE - INTERVAL 30 DAYS",
    "this month": "DATE_TRUNC('month', CURRENT_DATE)",
}


def _check_revenue_anomalies(period: str, threshold_pct: float = 30.0) -> str:
    """Find days where revenue is below the 14-day rolling average by threshold_pct."""
    start = _PERIOD_MAP.get(period.lower().strip(), "CURRENT_DATE - INTERVAL 7 DAYS")
    sql = f"""
        WITH base AS (
            SELECT
                order_date,
                total_revenue,
                AVG(total_revenue) OVER (
                    ORDER BY order_date
                    ROWS BETWEEN 13 PRECEDING AND CURRENT ROW
                ) AS rolling_avg_14d
            FROM {CATALOG}.{DATABASE}.revenue_daily
        )
        SELECT
            CAST(order_date AS STRING) AS day,
            ROUND(total_revenue, 2)    AS revenue_eur,
            ROUND(rolling_avg_14d, 2)  AS rolling_avg_14d_eur,
            ROUND(
                100.0 * (rolling_avg_14d - total_revenue) / NULLIF(rolling_avg_14d, 0),
                1
            ) AS pct_below_avg
        FROM base
        WHERE order_date >= {start}
          AND total_revenue < rolling_avg_14d * (1 - {threshold_pct / 100.0})
        ORDER BY order_date DESC
    """
    return _run_sql(sql)


_TOOL_FN_MAP: dict[str, object] = {
    "check_revenue_anomalies": _check_revenue_anomalies,
}


# ---------------------------------------------------------------------------
# Agent entry point
# ---------------------------------------------------------------------------

def run(question: str, client: OpenAI | None = None) -> str:
    """
    Run the fraud specialist agent.

    Args:
        question: the user's question
        client:   OpenAI-compatible Databricks client; created automatically if None

    Returns:
        plain-text answer
    """
    if client is None:
        client = _make_client()

    messages: list[dict] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.chat.completions.create(
            model=MAIN_AGENT_MODEL,
            messages=messages,
            tools=_TOOLS,
            tool_choice="auto",
            temperature=0,
        )
        msg = response.choices[0].message

        if not msg.tool_calls:
            return msg.content or ""

        messages.append(msg.model_dump(exclude_unset=True))

        for tc in msg.tool_calls:
            try:
                tool_args = json.loads(tc.function.arguments or "{}")
            except (json.JSONDecodeError, TypeError):
                tool_args = {}

            fn = _TOOL_FN_MAP.get(tc.function.name)
            if fn is None:
                result = f"Tool '{tc.function.name}' not found."
            else:
                try:
                    result = fn(**tool_args)  # type: ignore[operator]
                except Exception as exc:
                    result = f"Tool error: {exc}"

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": str(result),
            })

    return "Reached maximum tool rounds without a final answer."
