# Databricks notebook source

# COMMAND ----------

%pip install --quiet mlflow openai

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------
# MAGIC %md
# MAGIC # ShopStream AI Agent — MLflow PyFunc Registration
# MAGIC
# MAGIC **What this notebook does:**
# MAGIC 1. Defines `ShopStreamAgent` as an MLflow PyFunc model — wraps the full agent loop
# MAGIC 2. Runs a local smoke test to verify it works before registering
# MAGIC 3. Registers the model to Unity Catalog: `helix_databricks.default.helix-shopstream-agent`
# MAGIC 4. Sets the `@champion` alias so Model Serving can load it
# MAGIC
# MAGIC **Prerequisites:**
# MAGIC - `embed_documents.py` complete (document_chunks table exists)
# MAGIC - `create_index.py` complete (Vector Search index is ONLINE)
# MAGIC - Both ML models (`helix-churn-prediction`, `helix-revenue-forecast`) have `@champion` alias
# MAGIC
# MAGIC **Run order for Phase 04:**
# MAGIC 1. `embed_documents.py`
# MAGIC 2. `create_index.py`
# MAGIC 3. **This notebook** (`agent_pyfunc.py`)
# MAGIC 4. `golden_dataset.py`
# MAGIC 5. `evaluator.py`

# COMMAND ----------

import json
import logging
import os
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import mlflow
import pandas as pd
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState
from databricks.sdk.service.vectorsearch import VectorIndexType
from openai import OpenAI

# COMMAND ----------

# Constants
CATALOG = "helix_databricks"
DATABASE = "default"
AGENT_MODEL_NAME = f"{CATALOG}.{DATABASE}.helix-shopstream-agent"

GATEKEEPER_MODEL = "databricks-meta-llama-3-1-8b-instruct"
MAIN_AGENT_MODEL = "databricks-meta-llama-3-3-70b-instruct"
FORECAST_MODEL_UC = f"{CATALOG}.{DATABASE}.helix-revenue-forecast"

VS_ENDPOINT = "helix-vs-endpoint"
VS_INDEX = f"{CATALOG}.{DATABASE}.document_chunks_index"

MAX_TOOL_ROUNDS = 10

logger = logging.getLogger(__name__)

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 1: Define tool implementations (inlined — no relative imports)
# MAGIC
# MAGIC Each tool is a small class with `name`, `description`, `parameters`, and `run(args)`.
# MAGIC They are inlined here so the PyFunc model is fully self-contained when serialised by MLflow.

# COMMAND ----------

def _get_warehouse_id(w: WorkspaceClient) -> str:
    wh_id = os.environ.get("DATABRICKS_SQL_WAREHOUSE_ID", "")
    if not wh_id:
        warehouses = list(w.warehouses.list())
        if warehouses:
            wh_id = warehouses[0].id
    return wh_id


def _run_sql(sql: str) -> str:
    """Execute SQL via Statement Execution API, return formatted plain-text result."""
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


class _QueryMetricsTool:
    name = "query_metrics"
    description = (
        "Query ShopStream business metrics from the Gold data layer. "
        "Use for questions about revenue, order counts, customer counts, "
        "product performance, and other KPIs over any time period."
    )
    parameters = {
        "type": "object",
        "properties": {
            "metric": {
                "type": "string",
                "enum": ["revenue", "orders", "customers", "products", "returns"],
            },
            "period": {
                "type": "string",
                "description": "Time period. Examples: 'last 7 days', 'last 30 days', 'this month'.",
            },
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
        sql_tmpl = self._SQL.get(metric, self._SQL["revenue"])
        sql = sql_tmpl.format(start=start, limit=limit)
        return _run_sql(sql)


class _SearchDocumentsTool:
    name = "search_documents"
    description = (
        "Semantic search over ShopStream product documentation, policies, and FAQs. "
        "Use for questions about return policies, warranties, shipping, or product guides."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The question to search for."},
            "num_results": {"type": "integer", "default": 4},
        },
        "required": ["query"],
    }

    def run(self, args: dict) -> str:
        query = args.get("query", "").strip()
        if not query:
            return "Error: 'query' is required."
        num_results = int(args.get("num_results", 4))
        w = WorkspaceClient()
        results = w.vector_search_indexes.query_index(
            index_name=VS_INDEX,
            columns=["chunk_id", "source_file", "section", "chunk_text"],
            query_text=query,
            num_results=num_results,
        )
        rows = results.result.data_array if results.result else []
        if not rows:
            return f"No documents found for: '{query}'."
        lines = [f"Document results for: '{query}'", "=" * 50]
        for i, row in enumerate(rows, 1):
            lines.append(f"[{i}] {row[1]} — {row[2]}")
            lines.append(str(row[3]))
            lines.append("")
        return "\n".join(lines)


class _ForecastTool:
    name = "forecast"
    description = (
        "Predict future ShopStream revenue using the trained LightGBM forecast model. "
        "Use for questions about expected revenue over a future period."
    )
    parameters = {
        "type": "object",
        "properties": {
            "horizon_days": {"type": "integer", "default": 7, "description": "Days to forecast. Max 90."},
        },
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
        feature_cols = ["day_of_week", "month", "day_of_month", "is_weekend"]
        model = self._get_model()
        preds = model.predict(df[feature_cols])
        df["predicted_revenue_eur"] = preds.round(2)
        lines = [f"Revenue forecast — next {horizon_days} days", "-" * 40]
        for _, row in df.iterrows():
            lines.append(f"{row['forecast_date']}  EUR {row['predicted_revenue_eur']:>10,.2f}")
        lines.append(f"\nTotal: EUR {df['predicted_revenue_eur'].sum():,.2f}")
        return "\n".join(lines)


class _AlertTool:
    name = "alert_tool"
    description = "List existing ShopStream KPI alerts or describe how to create a new alert."
    parameters = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["list", "create"], "default": "list"},
        },
        "required": ["action"],
    }

    def run(self, args: dict) -> str:
        if args.get("action") == "list":
            w = WorkspaceClient()
            alerts = list(w.alerts.list())
            if not alerts:
                return "No alerts configured. Create them via Databricks workspace → SQL → Alerts."
            return "\n".join(f"  {a.name} — {a.state}" for a in alerts)
        return "To create an alert: Databricks workspace → SQL → Alerts → New Alert."


# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 2: Gatekeeper + ReAct agent loop

# COMMAND ----------

_GATEKEEPER_SYSTEM = """\
You are a safety classifier for ShopStream's AI assistant.
The assistant can ONLY answer questions about: revenue, orders, products,
customers, return policies, shipping, warranties, forecasts, and alerts.
Respond with EXACTLY one of:
  ALLOWED
  BLOCKED: <one short reason>
"""

_AGENT_SYSTEM = """\
You are ShopStream's AI data assistant. Help the business team understand
their e-commerce data. Use the available tools to answer questions.
Think step by step. Call tools one at a time. Give a clear final answer.
"""


def _get_databricks_token() -> str:
    """Get Databricks token: dbutils (notebooks) first, then env var."""
    try:
        return dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()  # noqa: F821
    except Exception:
        token = os.environ.get("DATABRICKS_TOKEN", "")
        if not token:
            raise RuntimeError("No Databricks token found. Set DATABRICKS_TOKEN env var.")
        return token


def _get_databricks_host() -> str:
    """Get Databricks workspace URL: dbutils first, then env var."""
    try:
        return dbutils.notebook.entry_point.getDbutils().notebook().getContext().browserHostName().get()  # noqa: F821
    except Exception:
        return os.environ.get("DATABRICKS_HOST", "").rstrip("/")


def _make_client() -> OpenAI:
    return OpenAI(
        api_key=_get_databricks_token(),
        base_url=f"https://{_get_databricks_host()}/serving-endpoints",
    )


def _run_gatekeeper(question: str, client: OpenAI) -> tuple[bool, str]:
    """Returns (allowed: bool, reason: str)."""
    try:
        resp = client.chat.completions.create(
            model=GATEKEEPER_MODEL,
            messages=[
                {"role": "system", "content": _GATEKEEPER_SYSTEM},
                {"role": "user", "content": question},
            ],
            max_tokens=32,
            temperature=0,
        )
        text = (resp.choices[0].message.content or "").strip().upper()
        if text.startswith("ALLOWED"):
            return True, ""
        parts = text.split(":", 1)
        reason = parts[1].strip() if len(parts) > 1 else "blocked by safety filter"
        return False, reason
    except Exception:
        return False, "gatekeeper unavailable"


_TOOLS_REGISTRY: dict[str, Any] = {}


def _build_registry() -> None:
    for tool in [_QueryMetricsTool(), _SearchDocumentsTool(), _ForecastTool(), _AlertTool()]:
        _TOOLS_REGISTRY[tool.name] = tool


_build_registry()


def _tool_specs() -> list[dict]:
    return [
        {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}
        for t in _TOOLS_REGISTRY.values()
    ]


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
        choice = response.choices[0]
        msg = choice.message
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
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })
    return "Reached maximum tool rounds without a final answer."


# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 3: MLflow PyFunc wrapper

# COMMAND ----------

class ShopStreamAgent(mlflow.pyfunc.PythonModel):
    """MLflow PyFunc wrapper for the ShopStream AI agent.

    Input: pandas DataFrame with a single column `messages` containing
           a list of dicts [{role, content}] OR a column `question` with a string.
    Output: pandas DataFrame with a column `answer`.
    """

    def predict(self, context, model_input: pd.DataFrame) -> pd.DataFrame:
        client = _make_client()

        if "question" in model_input.columns:
            questions = model_input["question"].tolist()
        elif "messages" in model_input.columns:
            # Extract last user message from conversation
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
                answers.append(f"I can only answer questions about ShopStream data. ({reason})")
            else:
                answers.append(_run_agent(q, client))

        return pd.DataFrame({"answer": answers})


# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 4: Smoke test — run the agent locally before registering

# COMMAND ----------

test_client = _make_client()

test_questions = [
    "What was total revenue last 7 days?",
    "What is the return policy for electronics?",
]

print("=== Smoke test ===")
for q in test_questions:
    allowed, reason = _run_gatekeeper(q, test_client)
    print(f"\nQ: {q}")
    print(f"Gatekeeper: {'ALLOWED' if allowed else f'BLOCKED ({reason})'}")
    if allowed:
        answer = _run_agent(q, test_client)
        print(f"Answer: {answer[:300]}...")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 5: Register to Unity Catalog and set @champion alias

# COMMAND ----------

mlflow.set_registry_uri("databricks-uc")

with mlflow.start_run(run_name="shopstream-agent-registration"):
    model_info = mlflow.pyfunc.log_model(
        artifact_path="agent",
        python_model=ShopStreamAgent(),
        registered_model_name=AGENT_MODEL_NAME,
        input_example=pd.DataFrame({"question": ["What was total revenue last 7 days?"]}),
    )

print(f"Model registered: {model_info.model_uri}")

# Set @champion alias on the latest version
client_mlflow = mlflow.tracking.MlflowClient()
versions = client_mlflow.search_model_versions(f"name='{AGENT_MODEL_NAME}'")
latest = max(versions, key=lambda v: int(v.version))
client_mlflow.set_registered_model_alias(AGENT_MODEL_NAME, alias="champion", version=latest.version)

print(f"@champion alias set on version {latest.version}")
print(f"\nDone. Run golden_dataset.py next to create the evaluation dataset.")
