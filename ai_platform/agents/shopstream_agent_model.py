"""ShopStreamAgent — standalone MLflow PyFunc model.

This file is committed to the repo and passed as `code_paths` to
mlflow.pyfunc.log_model so MLflow bundles it with the model artifact.
The class must NOT be defined in a Databricks notebook scope, otherwise
cloudpickle cannot serialize it.
"""

import json
import logging
import os
from typing import Any

import mlflow
import mlflow.pyfunc
import pandas as pd
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState
from openai import OpenAI

CATALOG = "helix_databricks"
DATABASE = "default"
FORECAST_MODEL_UC = f"{CATALOG}.{DATABASE}.helix-revenue-forecast"
VS_INDEX = f"{CATALOG}.{DATABASE}.document_chunks_index"
GATEKEEPER_MODEL = "databricks-meta-llama-3-1-8b-instruct"
MAIN_AGENT_MODEL = "databricks-meta-llama-3-3-70b-instruct"
MAX_TOOL_ROUNDS = 10

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Credentials helpers
# ---------------------------------------------------------------------------

def _get_databricks_token() -> str:
    try:
        from dbruntime.databricks_repl_context import get_context  # type: ignore
        return get_context().apiToken
    except Exception:
        token = os.environ.get("DATABRICKS_TOKEN", "")
        if not token:
            raise RuntimeError("No Databricks token found. Set DATABRICKS_TOKEN env var.")
        return token


def _get_databricks_host() -> str:
    try:
        from dbruntime.databricks_repl_context import get_context  # type: ignore
        return get_context().browserHostName
    except Exception:
        return os.environ.get("DATABRICKS_HOST", "").rstrip("/")


def _make_client() -> OpenAI:
    return OpenAI(
        api_key=_get_databricks_token(),
        base_url=f"https://{_get_databricks_host()}/serving-endpoints",
    )


# ---------------------------------------------------------------------------
# SQL helper
# ---------------------------------------------------------------------------

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
        return "Error: no SQL warehouse available. Set DATABRICKS_SQL_WAREHOUSE_ID."
    response = w.statement_execution.execute_statement(
        warehouse_id=warehouse_id,
        statement=sql,
        wait_timeout="30s",
    )
    if response.status.state != StatementState.SUCCEEDED:
        return f"Query failed: {response.status.error}"
    cols = [c.name for c in response.manifest.schema.columns]
    rows = response.result.data_array or []
    if not rows:
        return "Query returned no rows."
    lines = ["  ".join(cols)]
    for row in rows:
        lines.append("  ".join(str(v) if v is not None else "NULL" for v in row))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

class _QueryMetricsTool:
    name = "query_metrics"
    description = (
        "Query ShopStream business metrics from the Gold data layer. "
        "Use for revenue, order counts, customer counts, products, returns."
    )
    parameters = {
        "type": "object",
        "properties": {
            "metric": {"type": "string", "enum": ["revenue", "orders", "customers", "products", "returns"]},
            "period": {"type": "string", "description": "e.g. last 7 days, last 30 days, this month"},
            "limit": {"type": "integer", "default": 10},
        },
        "required": ["metric", "period"],
    }
    _PERIOD_MAP = {
        "today": "CURRENT_DATE",
        "yesterday": "CURRENT_DATE - INTERVAL 1 DAY",
        "last 7 days": "CURRENT_DATE - INTERVAL 7 DAYS",
        "last 30 days": "CURRENT_DATE - INTERVAL 30 DAYS",
        "this month": "DATE_TRUNC('month', CURRENT_DATE)",
        "last month": "DATE_TRUNC('month', CURRENT_DATE - INTERVAL 1 MONTH)",
    }
    _SQL = {
        "revenue": (
            "SELECT CAST(order_date AS STRING) AS day, ROUND(SUM(total_revenue),2) AS revenue_eur "
            "FROM helix_databricks.default.revenue_daily "
            "WHERE order_date >= {start} GROUP BY 1 ORDER BY 1 DESC LIMIT {limit}"
        ),
        "orders": (
            "SELECT CAST(order_date AS STRING) AS day, COUNT(*) AS orders "
            "FROM helix_databricks.default.fct_orders "
            "WHERE order_date >= {start} GROUP BY 1 ORDER BY 1 DESC LIMIT {limit}"
        ),
        "customers": (
            "SELECT churn_risk_segment, COUNT(*) AS count, ROUND(AVG(predicted_churn_prob),3) AS avg_churn "
            "FROM helix_databricks.default.customer_metrics GROUP BY 1 ORDER BY 2 DESC LIMIT {limit}"
        ),
        "products": (
            "SELECT product_name, ROUND(SUM(total_revenue),2) AS revenue "
            "FROM helix_databricks.default.product_performance "
            "WHERE snapshot_date >= {start} GROUP BY 1 ORDER BY 2 DESC LIMIT {limit}"
        ),
        "returns": (
            "SELECT CAST(return_date AS STRING) AS day, COUNT(*) AS returns "
            "FROM helix_databricks.default.fct_returns "
            "WHERE return_date >= {start} GROUP BY 1 ORDER BY 1 DESC LIMIT {limit}"
        ),
    }

    def run(self, args: dict) -> str:
        metric = args.get("metric", "revenue")
        period = args.get("period", "last 7 days").lower().strip()
        limit = int(args.get("limit", 10))
        start = self._PERIOD_MAP.get(period, "CURRENT_DATE - INTERVAL 7 DAYS")
        sql = self._SQL.get(metric, self._SQL["revenue"]).format(start=start, limit=limit)
        return _run_sql(sql)


class _SearchDocumentsTool:
    name = "search_documents"
    description = (
        "Semantic search over ShopStream policies and FAQs. "
        "Use for return policies, warranties, shipping, product guides."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "num_results": {"type": "integer", "default": 4},
        },
        "required": ["query"],
    }

    def run(self, args: dict) -> str:
        query = args.get("query", "").strip()
        if not query:
            return "Error: query is required."
        w = WorkspaceClient()
        results = w.vector_search_indexes.query_index(
            index_name=VS_INDEX,
            columns=["chunk_id", "source_file", "section", "chunk_text"],
            query_text=query,
            num_results=int(args.get("num_results", 4)),
        )
        rows = results.result.data_array if results.result else []
        if not rows:
            return f"No documents found for: '{query}'."
        lines = [f"Results for: '{query}'", "=" * 50]
        for i, row in enumerate(rows, 1):
            lines.append(f"[{i}] {row[1]} — {row[2]}")
            lines.append(str(row[3]))
            lines.append("")
        return "\n".join(lines)


class _ForecastTool:
    name = "forecast"
    description = "Predict future revenue using the @champion LightGBM forecast model."
    parameters = {
        "type": "object",
        "properties": {"horizon_days": {"type": "integer", "default": 7}},
        "required": [],
    }
    _model = None

    def _get_model(self):
        if self.__class__._model is None:
            self.__class__._model = mlflow.pyfunc.load_model(f"models:/{FORECAST_MODEL_UC}@champion")
        return self.__class__._model

    def run(self, args: dict) -> str:
        from datetime import date, timedelta
        horizon_days = min(int(args.get("horizon_days", 7)), 90)
        today = date.today()
        records = [
            {
                "day_of_week": (today + timedelta(days=i)).weekday(),
                "month": (today + timedelta(days=i)).month,
                "day_of_month": (today + timedelta(days=i)).day,
                "is_weekend": int((today + timedelta(days=i)).weekday() >= 5),
                "forecast_date": (today + timedelta(days=i)).isoformat(),
            }
            for i in range(1, horizon_days + 1)
        ]
        df = pd.DataFrame(records)
        preds = self._get_model().predict(df[["day_of_week", "month", "day_of_month", "is_weekend"]])
        df["predicted_revenue_eur"] = preds.round(2)
        lines = [f"Revenue forecast — next {horizon_days} days", "-" * 40]
        for _, row in df.iterrows():
            d = str(row["forecast_date"])
            r = float(row["predicted_revenue_eur"])
            lines.append(f"{d}  EUR {r:>10,.2f}")
        total_rev = float(df["predicted_revenue_eur"].sum())
        lines.append(f"\nTotal: EUR {total_rev:,.2f}")
        return "\n".join(lines)


class _AlertTool:
    name = "alert_tool"
    description = "List ShopStream KPI alerts or explain how to create one."
    parameters = {
        "type": "object",
        "properties": {"action": {"type": "string", "enum": ["list", "create"], "default": "list"}},
        "required": ["action"],
    }

    def run(self, args: dict) -> str:
        if args.get("action") == "list":
            w = WorkspaceClient()
            alerts = list(w.alerts.list())
            if not alerts:
                return "No alerts configured. Create via Databricks workspace → SQL → Alerts."
            return "\n".join(f"  {a.name} — {a.state}" for a in alerts)
        return "To create an alert: Databricks workspace → SQL → Alerts → New Alert."


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

_GATEKEEPER_SYSTEM = """\
You are a safety classifier for ShopStream's AI assistant.
Only allow questions about: revenue, orders, products, customers,
return policies, shipping, warranties, forecasts, and alerts.
Respond with EXACTLY one of:
  ALLOWED
  BLOCKED: <one short reason>
"""

_AGENT_SYSTEM = """\
You are ShopStream's AI data assistant. Help the business team understand
their e-commerce data. Use the available tools to answer questions.
Think step by step. Call tools one at a time. Give a clear final answer.
"""

_TOOLS_REGISTRY: dict[str, Any] = {
    t.name: t for t in [_QueryMetricsTool(), _SearchDocumentsTool(), _ForecastTool(), _AlertTool()]
}


def _tool_specs() -> list:
    return [
        {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}
        for t in _TOOLS_REGISTRY.values()
    ]


def _run_gatekeeper(question: str, client: OpenAI) -> tuple:
    try:
        resp = client.chat.completions.create(
            model=GATEKEEPER_MODEL,
            messages=[{"role": "system", "content": _GATEKEEPER_SYSTEM}, {"role": "user", "content": question}],
            max_tokens=32,
            temperature=0,
        )
        text = (resp.choices[0].message.content or "").strip().upper()
        if text.startswith("ALLOWED"):
            return True, ""
        parts = text.split(":", 1)
        return False, parts[1].strip() if len(parts) > 1 else "blocked"
    except Exception:
        return False, "gatekeeper unavailable"


def _run_agent(question: str, client: OpenAI) -> str:
    messages = [
        {"role": "system", "content": _AGENT_SYSTEM},
        {"role": "user", "content": question},
    ]
    for _ in range(MAX_TOOL_ROUNDS):
        response = client.chat.completions.create(
            model=MAIN_AGENT_MODEL,
            messages=messages,
            tools=_tool_specs(),
            tool_choice="auto",
            temperature=0,
        )
        msg = response.choices[0].message
        messages.append(msg.model_dump(exclude_unset=True))
        if not msg.tool_calls:
            return msg.content or ""
        for tc in msg.tool_calls:
            tool = _TOOLS_REGISTRY.get(tc.function.name)
            try:
                tool_args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                tool_args = {}
            result = tool.run(tool_args) if tool else f"Tool '{tc.function.name}' not found."
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
    return "Reached maximum tool rounds without a final answer."


# ---------------------------------------------------------------------------
# MLflow PyFunc wrapper
# ---------------------------------------------------------------------------

class ShopStreamAgent(mlflow.pyfunc.PythonModel):
    """MLflow PyFunc wrapper for the ShopStream AI agent."""

    def predict(self, context, model_input: pd.DataFrame) -> pd.DataFrame:
        client = _make_client()
        if "question" in model_input.columns:
            questions = model_input["question"].tolist()
        elif "messages" in model_input.columns:
            questions = []
            for msgs in model_input["messages"].tolist():
                user_msgs = [m["content"] for m in msgs if m.get("role") == "user"]
                questions.append(user_msgs[-1] if user_msgs else "")
        else:
            return pd.DataFrame({"answer": ["Error: input must have 'question' or 'messages' column."]})
        answers = []
        for q in questions:
            allowed, reason = _run_gatekeeper(q, client)
            if not allowed:
                answers.append(f"I can only answer ShopStream data questions. ({reason})")
            else:
                answers.append(_run_agent(q, client))
        return pd.DataFrame({"answer": answers})
