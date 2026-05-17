"""AlertTool — list and create Databricks SQL monitoring alerts for ShopStream KPIs.

Used by the agent when the user asks:
  - 'List all active alerts'
  - 'Create an alert if daily revenue drops below EUR 5000'
  - 'Set up a notification when return rate exceeds 15%'

Uses the Databricks SDK Alerts API.
"""

from __future__ import annotations

from typing import Any

from databricks.sdk import WorkspaceClient


CATALOG = "helix_databricks"
DATABASE = "default"


class AlertTool:
    name = "alert_tool"
    description = (
        "Manage ShopStream KPI alerts. "
        "Use 'list' to see existing alerts. "
        "Use 'create' to set up a new alert when a metric crosses a threshold. "
        "Alerts run on a schedule and notify via email when triggered."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "create"],
                "description": "Whether to list existing alerts or create a new one.",
            },
            "name": {
                "type": "string",
                "description": "Name for the new alert (required when action='create').",
            },
            "metric": {
                "type": "string",
                "enum": ["revenue", "orders", "return_rate"],
                "description": "Metric to monitor (required when action='create').",
            },
            "threshold": {
                "type": "number",
                "description": "Numeric threshold that triggers the alert (required when action='create').",
            },
            "condition": {
                "type": "string",
                "enum": ["below", "above"],
                "default": "below",
                "description": "Whether to alert when metric is below or above the threshold.",
            },
        },
        "required": ["action"],
    }

    _ALERT_QUERIES = {
        "revenue": (
            f"SELECT ROUND(SUM(total_revenue), 2) AS value "
            f"FROM {CATALOG}.{DATABASE}.revenue_daily "
            f"WHERE order_date = CURRENT_DATE - INTERVAL 1 DAY"
        ),
        "orders": (
            f"SELECT COUNT(*) AS value "
            f"FROM {CATALOG}.{DATABASE}.fct_orders "
            f"WHERE order_date = CURRENT_DATE - INTERVAL 1 DAY"
        ),
        "return_rate": (
            f"SELECT ROUND(AVG(return_rate) * 100, 2) AS value "
            f"FROM {CATALOG}.{DATABASE}.product_performance "
            f"WHERE snapshot_date = CURRENT_DATE - INTERVAL 1 DAY"
        ),
    }

    def run(self, args: dict[str, Any]) -> str:
        action = args.get("action", "list")
        if action == "list":
            return self._list_alerts()
        if action == "create":
            return self._create_alert(args)
        return f"Unknown action '{action}'. Use 'list' or 'create'."

    def _list_alerts(self) -> str:
        w = WorkspaceClient()
        alerts = list(w.alerts.list())
        if not alerts:
            return "No alerts configured yet."
        lines = [f"Active alerts ({len(alerts)} total):", "-" * 40]
        for alert in alerts:
            lines.append(f"  {alert.name} — state: {alert.state}")
        return "\n".join(lines)

    def _create_alert(self, args: dict[str, Any]) -> str:
        name = args.get("name", "ShopStream Alert")
        metric = args.get("metric", "revenue")
        threshold = float(args.get("threshold", 0))
        condition = args.get("condition", "below")

        query_sql = self._ALERT_QUERIES.get(metric)
        if not query_sql:
            return f"Unknown metric '{metric}' for alert creation."

        op = "<" if condition == "below" else ">"
        return (
            f"Alert '{name}' configuration:\n"
            f"  Metric: {metric}\n"
            f"  Condition: {condition} {threshold}\n"
            f"  SQL: {query_sql}\n\n"
            f"To create this alert in Databricks:\n"
            f"  1. Go to Databricks workspace → SQL → Alerts → New Alert\n"
            f"  2. Paste the SQL above as a new Query\n"
            f"  3. Set condition: value {op} {threshold}\n"
            f"  4. Set name: {name}\n"
            f"  5. Set schedule and notification email\n"
            f"\nNote: Databricks SDK alert creation requires a saved query ID. "
            f"Use the UI for initial setup."
        )
