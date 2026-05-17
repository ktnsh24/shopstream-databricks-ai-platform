"""Pricing and margin specialist sub-agent.

Handles questions about revenue, product margins, pricing trends, and discounts.
Uses the revenue_daily and product_performance Gold tables.

Courier analogy: this is the depot's billing desk. It knows the cost of every
route, the margin on every delivery tier, and which parcels are running at a loss.
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
You are a pricing analyst for ShopStream. You answer questions about revenue,
product margins, pricing performance, and discount impact. Use exact numbers
from the data. Show currency as EUR. Be concise and use tables when helpful.
"""

_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "query_revenue",
            "description": "Query daily revenue totals and order counts from the Gold layer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "description": (
                            "Time window, e.g. 'last 7 days', 'last 30 days', 'this month'"
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max rows to return. Default: 14",
                        "default": 14,
                    },
                },
                "required": ["period"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_products",
            "description": (
                "Query product-level revenue and units sold. "
                "Use for top/bottom products, margin by product, and category breakdown."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "description": "Time window, e.g. 'last 7 days', 'last 30 days'",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max rows to return. Default: 10",
                        "default": 10,
                    },
                },
                "required": ["period"],
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
# Tool implementations
# ---------------------------------------------------------------------------

_PERIOD_MAP = {
    "today": "CURRENT_DATE",
    "yesterday": "CURRENT_DATE - INTERVAL 1 DAY",
    "last 7 days": "CURRENT_DATE - INTERVAL 7 DAYS",
    "last 14 days": "CURRENT_DATE - INTERVAL 14 DAYS",
    "last 30 days": "CURRENT_DATE - INTERVAL 30 DAYS",
    "this month": "DATE_TRUNC('month', CURRENT_DATE)",
    "last month": "DATE_TRUNC('month', CURRENT_DATE - INTERVAL 1 MONTH)",
}


def _query_revenue(period: str, limit: int = 14) -> str:
    start = _PERIOD_MAP.get(period.lower().strip(), "CURRENT_DATE - INTERVAL 7 DAYS")
    sql = (
        f"SELECT CAST(order_date AS STRING) AS day, "
        f"ROUND(total_revenue, 2) AS revenue_eur, order_count "
        f"FROM {CATALOG}.{DATABASE}.revenue_daily "
        f"WHERE order_date >= {start} "
        f"ORDER BY order_date DESC "
        f"LIMIT {int(limit)}"
    )
    return _run_sql(sql)


def _query_products(period: str, limit: int = 10) -> str:
    start = _PERIOD_MAP.get(period.lower().strip(), "CURRENT_DATE - INTERVAL 7 DAYS")
    sql = (
        f"SELECT product_name, "
        f"SUM(units_sold) AS total_units, "
        f"ROUND(SUM(total_revenue), 2) AS revenue_eur "
        f"FROM {CATALOG}.{DATABASE}.product_performance "
        f"WHERE snapshot_date >= {start} "
        f"GROUP BY product_name "
        f"ORDER BY revenue_eur DESC "
        f"LIMIT {int(limit)}"
    )
    return _run_sql(sql)


_TOOL_FN_MAP: dict[str, object] = {
    "query_revenue": _query_revenue,
    "query_products": _query_products,
}


# ---------------------------------------------------------------------------
# Agent entry point
# ---------------------------------------------------------------------------

def run(question: str, client: OpenAI | None = None) -> str:
    """
    Run the pricing specialist agent.

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
