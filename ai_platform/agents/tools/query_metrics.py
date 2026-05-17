"""QueryMetricsTool — query ShopStream Gold tables for revenue, orders, and customer KPIs.

Used by the agent when the user asks questions like:
  - 'What was total revenue last week?'
  - 'How many orders did we get yesterday?'
  - 'Show me top 5 products by revenue this month'

Uses the Databricks SQL Statement Execution API so this tool works both
inside a Databricks notebook AND inside a Model Serving endpoint (no Spark needed).
"""

from __future__ import annotations

import json
import os
from typing import Any

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState


CATALOG = "helix_databricks"
DATABASE = "default"


class QueryMetricsTool:
    name = "query_metrics"
    description = (
        "Query ShopStream business metrics from the Gold data layer. "
        "Use this tool for questions about revenue, order counts, customer counts, "
        "product performance, and other KPIs over any time period. "
        "Returns a plain-text summary of the results."
    )
    parameters = {
        "type": "object",
        "properties": {
            "metric": {
                "type": "string",
                "enum": ["revenue", "orders", "customers", "products", "returns"],
                "description": "Which metric to query.",
            },
            "period": {
                "type": "string",
                "description": (
                    "Time period to aggregate over. Examples: 'last 7 days', 'last 30 days', "
                    "'this month', 'last month', 'yesterday', 'today'."
                ),
            },
            "limit": {
                "type": "integer",
                "default": 10,
                "description": "Maximum number of rows to return. Default 10.",
            },
        },
        "required": ["metric", "period"],
    }

    # SQL templates — one per metric
    _SQL = {
        "revenue": """
            SELECT
                DATE_TRUNC('day', order_date) AS day,
                ROUND(SUM(total_revenue), 2)  AS total_revenue_eur,
                COUNT(*)                       AS order_count
            FROM {catalog}.{db}.revenue_daily
            WHERE order_date >= {start_expr}
            GROUP BY 1
            ORDER BY 1 DESC
            LIMIT {limit}
        """,
        "orders": """
            SELECT
                DATE_TRUNC('day', order_date) AS day,
                COUNT(*)                       AS order_count,
                COUNT(DISTINCT customer_id)    AS unique_customers
            FROM {catalog}.{db}.fct_orders
            WHERE order_date >= {start_expr}
            GROUP BY 1
            ORDER BY 1 DESC
            LIMIT {limit}
        """,
        "customers": """
            SELECT
                churn_risk_segment,
                COUNT(*)                             AS customer_count,
                ROUND(AVG(predicted_churn_prob), 3)  AS avg_churn_prob,
                ROUND(AVG(total_revenue_90d), 2)     AS avg_revenue_90d
            FROM {catalog}.{db}.customer_metrics
            GROUP BY 1
            ORDER BY avg_churn_prob DESC
            LIMIT {limit}
        """,
        "products": """
            SELECT
                product_name,
                ROUND(SUM(total_revenue), 2) AS total_revenue_eur,
                SUM(units_sold)              AS units_sold,
                ROUND(AVG(return_rate), 3)   AS avg_return_rate
            FROM {catalog}.{db}.product_performance
            WHERE snapshot_date >= {start_expr}
            GROUP BY 1
            ORDER BY total_revenue_eur DESC
            LIMIT {limit}
        """,
        "returns": """
            SELECT
                DATE_TRUNC('day', return_date) AS day,
                COUNT(*)                        AS return_count,
                ROUND(SUM(refund_amount), 2)    AS refund_total_eur
            FROM {catalog}.{db}.fct_returns
            WHERE return_date >= {start_expr}
            GROUP BY 1
            ORDER BY 1 DESC
            LIMIT {limit}
        """,
    }

    _PERIOD_MAP = {
        "today":       "CURRENT_DATE",
        "yesterday":   "CURRENT_DATE - INTERVAL 1 DAY",
        "last 7 days": "CURRENT_DATE - INTERVAL 7 DAYS",
        "last 30 days":"CURRENT_DATE - INTERVAL 30 DAYS",
        "this month":  "DATE_TRUNC('month', CURRENT_DATE)",
        "last month":  "DATE_TRUNC('month', CURRENT_DATE - INTERVAL 1 MONTH)",
    }

    def run(self, args: dict[str, Any]) -> str:
        metric = args.get("metric", "revenue")
        period = args.get("period", "last 7 days").lower().strip()
        limit = int(args.get("limit", 10))

        start_expr = self._PERIOD_MAP.get(period, "CURRENT_DATE - INTERVAL 7 DAYS")

        sql_template = self._SQL.get(metric)
        if not sql_template:
            return f"Unknown metric '{metric}'. Choose from: {list(self._SQL.keys())}"

        sql = sql_template.format(
            catalog=CATALOG,
            db=DATABASE,
            start_expr=start_expr,
            limit=limit,
        )

        return self._execute_sql(sql, metric, period)

    def _execute_sql(self, sql: str, metric: str, period: str) -> str:
        """Execute SQL via Statement Execution API and format result as plain text."""
        w = WorkspaceClient()
        warehouse_id = os.environ.get("DATABRICKS_SQL_WAREHOUSE_ID", "")
        if not warehouse_id:
            # Try to find the first available warehouse
            warehouses = list(w.warehouses.list())
            if not warehouses:
                return "Error: no SQL warehouse available. Set DATABRICKS_SQL_WAREHOUSE_ID."
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
            return f"No {metric} data found for period '{period}'."

        lines = [f"{metric.upper()} — {period}", "-" * 40]
        lines.append("  ".join(cols))
        for row in rows:
            lines.append("  ".join(str(v) if v is not None else "NULL" for v in row))
        return "\n".join(lines)
