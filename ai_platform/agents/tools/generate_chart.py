"""GenerateChartTool — produce a Vega-Lite chart specification for ShopStream data.

Used by the agent when the user asks for a visualisation:
  - 'Show me a bar chart of revenue by day this week'
  - 'Plot the return rate trend over the last 30 days'
  - 'Give me a pie chart of orders by country'

The tool queries the data, then returns a Vega-Lite JSON spec.
The frontend (api_gateway) renders the spec as an image or interactive chart.
"""

from __future__ import annotations

import json
import os
from typing import Any

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState


CATALOG = "helix_databricks"
DATABASE = "default"


class GenerateChartTool:
    name = "generate_chart"
    description = (
        "Generate a chart visualisation of ShopStream data. "
        "Returns a Vega-Lite JSON specification that can be rendered by the frontend. "
        "Use this tool when the user asks for a chart, graph, plot, or visualisation."
    )
    parameters = {
        "type": "object",
        "properties": {
            "chart_type": {
                "type": "string",
                "enum": ["bar", "line", "pie"],
                "description": "Type of chart to generate.",
            },
            "metric": {
                "type": "string",
                "enum": ["revenue", "orders", "returns", "return_rate"],
                "description": "Which metric to visualise.",
            },
            "period": {
                "type": "string",
                "default": "last 7 days",
                "description": "Time period. Examples: 'last 7 days', 'last 30 days', 'this month'.",
            },
        },
        "required": ["chart_type", "metric"],
    }

    _PERIOD_MAP = {
        "today":        "CURRENT_DATE",
        "yesterday":    "CURRENT_DATE - INTERVAL 1 DAY",
        "last 7 days":  "CURRENT_DATE - INTERVAL 7 DAYS",
        "last 30 days": "CURRENT_DATE - INTERVAL 30 DAYS",
        "this month":   "DATE_TRUNC('month', CURRENT_DATE)",
        "last month":   "DATE_TRUNC('month', CURRENT_DATE - INTERVAL 1 MONTH)",
    }

    _SQL_MAP = {
        "revenue": (
            "SELECT CAST(order_date AS STRING) AS x, ROUND(SUM(total_revenue), 2) AS y "
            "FROM {catalog}.{db}.revenue_daily "
            "WHERE order_date >= {start} GROUP BY 1 ORDER BY 1"
        ),
        "orders": (
            "SELECT CAST(order_date AS STRING) AS x, COUNT(*) AS y "
            "FROM {catalog}.{db}.fct_orders "
            "WHERE order_date >= {start} GROUP BY 1 ORDER BY 1"
        ),
        "returns": (
            "SELECT CAST(return_date AS STRING) AS x, COUNT(*) AS y "
            "FROM {catalog}.{db}.fct_returns "
            "WHERE return_date >= {start} GROUP BY 1 ORDER BY 1"
        ),
        "return_rate": (
            "SELECT CAST(snapshot_date AS STRING) AS x, ROUND(AVG(return_rate) * 100, 2) AS y "
            "FROM {catalog}.{db}.product_performance "
            "WHERE snapshot_date >= {start} GROUP BY 1 ORDER BY 1"
        ),
    }

    _MARK_MAP = {"bar": "bar", "line": "line", "pie": "arc"}
    _TITLE_MAP = {
        "revenue": "Revenue (EUR)", "orders": "Order Count",
        "returns": "Return Count", "return_rate": "Avg Return Rate (%)",
    }

    def run(self, args: dict[str, Any]) -> str:
        chart_type = args.get("chart_type", "bar")
        metric = args.get("metric", "revenue")
        period = args.get("period", "last 7 days").lower().strip()

        start = self._PERIOD_MAP.get(period, "CURRENT_DATE - INTERVAL 7 DAYS")
        sql = self._SQL_MAP.get(metric, self._SQL_MAP["revenue"]).format(
            catalog=CATALOG, db=DATABASE, start=start
        )

        data = self._fetch_data(sql)
        if isinstance(data, str):  # error message
            return data

        mark = self._MARK_MAP.get(chart_type, "bar")
        y_title = self._TITLE_MAP.get(metric, metric)

        spec = {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "title": f"{y_title} — {period}",
            "mark": mark,
            "data": {"values": data},
            "encoding": {
                "x": {"field": "x", "type": "ordinal", "title": "Date"},
                "y": {"field": "y", "type": "quantitative", "title": y_title},
            },
            "width": 600,
            "height": 300,
        }
        return json.dumps(spec, indent=2)

    def _fetch_data(self, sql: str) -> list | str:
        w = WorkspaceClient()
        warehouse_id = os.environ.get("DATABRICKS_SQL_WAREHOUSE_ID", "")
        if not warehouse_id:
            warehouses = list(w.warehouses.list())
            if not warehouses:
                return "Error: no SQL warehouse available."
            warehouse_id = warehouses[0].id

        response = w.statement_execution.execute_statement(
            warehouse_id=warehouse_id, statement=sql, wait_timeout="30s"
        )
        if response.status.state != StatementState.SUCCEEDED:
            return f"Query failed: {response.status.error}"

        rows = response.result.data_array or []
        return [{"x": row[0], "y": float(row[1]) if row[1] is not None else 0} for row in rows]
