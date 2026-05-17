"""Customer profile specialist sub-agent.

Handles questions about customer segments, churn risk, lifetime value, and
loyalty status.  Also acts as the default fallback agent — if the supervisor
cannot match a question to fraud or pricing, it routes here.

Courier analogy: this is the VIP desk at the depot. They know every regular
customer, their delivery history, and which ones are at risk of switching to
a rival courier.
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
You are a customer success analyst for ShopStream. You answer questions about
customer segments, churn risk, lifetime value, and retention. Use specific
numbers from the data. Explain what the risk levels mean in plain English.
Be empathetic and action-oriented in your answers.
"""

_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "query_customer_segments",
            "description": (
                "Query the customer_metrics table for churn risk segment breakdown. "
                "Returns segment name, customer count, and average churn probability."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Max segments to return. Default: 10",
                        "default": 10,
                    },
                },
                "required": [],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Shared helpers (self-contained)
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

def _query_customer_segments(limit: int = 10) -> str:
    sql = (
        f"SELECT churn_risk_segment, customer_count, "
        f"ROUND(predicted_churn_prob, 3) AS avg_churn_prob "
        f"FROM {CATALOG}.{DATABASE}.customer_metrics "
        f"ORDER BY avg_churn_prob DESC "
        f"LIMIT {int(limit)}"
    )
    return _run_sql(sql)


_TOOL_FN_MAP: dict[str, object] = {
    "query_customer_segments": _query_customer_segments,
}


# ---------------------------------------------------------------------------
# Agent entry point
# ---------------------------------------------------------------------------

def run(question: str, client: OpenAI | None = None) -> str:
    """
    Run the customer specialist agent.

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
