"""TextToSqlTool — convert a natural language question to SQL and execute it.

Used by the agent when the user asks complex data questions that don't fit
pre-built metric queries, for example:
  - 'Show me customers who ordered more than 5 times but have a high churn risk'
  - 'Which products were returned more than 20% of the time last quarter?'
  - 'List orders over EUR 200 from Germany in the past 30 days'

Flow: question -> LLM generates SQL -> execute via SQL Warehouse -> return results.
"""

from __future__ import annotations

import os
from typing import Any

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState
from openai import OpenAI


CATALOG = "helix_databricks"
DATABASE = "default"
SQLGEN_MODEL = "databricks-meta-llama-3-3-70b-instruct"

_SCHEMA_CONTEXT = """
Available tables in helix_databricks.default:

revenue_daily(order_date DATE, total_revenue DOUBLE, order_count INT)
fct_orders(order_id STRING, customer_id STRING, product_id STRING, order_date DATE,
           order_value DOUBLE, country STRING, status STRING)
fct_returns(return_id STRING, order_id STRING, product_id STRING, return_date DATE,
            refund_amount DOUBLE, reason STRING)
customer_metrics(customer_id STRING, total_orders INT, total_revenue_90d DOUBLE,
                 predicted_churn_prob DOUBLE, churn_risk_segment STRING,
                 days_since_last_order INT)
product_performance(product_id STRING, product_name STRING, category STRING,
                    snapshot_date DATE, units_sold INT, total_revenue DOUBLE,
                    return_rate DOUBLE)

Rules:
- Always use fully qualified table names: helix_databricks.default.<table>
- Only use SELECT statements — never INSERT, UPDATE, DELETE, DROP, or CREATE
- Always add LIMIT 50 unless the user explicitly asks for all rows
- Use CURRENT_DATE for today, CURRENT_DATE - INTERVAL N DAYS for relative dates
"""


class TextToSqlTool:
    name = "text_to_sql"
    description = (
        "Convert a natural language data question to SQL and execute it against ShopStream's Gold tables. "
        "Use this tool for custom, complex queries that the query_metrics tool cannot handle. "
        "Returns the SQL that was generated and the query results."
    )
    parameters = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The data question in plain English.",
            },
        },
        "required": ["question"],
    }

    def run(self, args: dict[str, Any]) -> str:
        question = args.get("question", "").strip()
        if not question:
            return "Error: 'question' argument is required."

        sql = self._generate_sql(question)
        if sql.startswith("Error:"):
            return sql

        results = self._execute_sql(sql)
        return f"Generated SQL:\n{sql}\n\nResults:\n{results}"

    def _generate_sql(self, question: str) -> str:
        client = OpenAI(
            api_key=os.environ.get("DATABRICKS_TOKEN", ""),
            base_url=f"{os.environ.get('DATABRICKS_HOST', '').rstrip('/')}/serving-endpoints",
        )
        prompt = (
            f"Given this database schema:\n{_SCHEMA_CONTEXT}\n\n"
            f"Write a single SQL SELECT query to answer this question:\n{question}\n\n"
            "Return ONLY the SQL query. No explanation, no markdown, no code block markers."
        )
        try:
            response = client.chat.completions.create(
                model=SQLGEN_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=512,
            )
            sql = response.choices[0].message.content.strip()
            # Strip markdown code block if the model added one anyway
            sql = sql.removeprefix("```sql").removeprefix("```").removesuffix("```").strip()
            return sql
        except Exception as exc:
            return f"Error generating SQL: {exc}"

    def _execute_sql(self, sql: str) -> str:
        w = WorkspaceClient()
        warehouse_id = os.environ.get("DATABRICKS_SQL_WAREHOUSE_ID", "")
        if not warehouse_id:
            warehouses = list(w.warehouses.list())
            if not warehouses:
                return "Error: no SQL warehouse available."
            warehouse_id = warehouses[0].id

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
