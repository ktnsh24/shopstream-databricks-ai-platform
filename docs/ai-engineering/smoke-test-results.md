# Smoke Test Results — Phase 05 & Phase 06

Recorded live against the `helix-shopstream-agent` model serving endpoint on Databricks.
All calls go through the FastAPI gateway on Azure Container Apps.

---

## Table of Contents

1. [Phase 05 — Single Agent (version 2)](#phase-05--single-agent-version-2)
2. [Phase 06 — Multi-Agent Supervisor (version 3)](#phase-06--multi-agent-supervisor-version-3)
3. [What the agent field means](#what-the-agent-field-means)
4. [Known routing edge case](#known-routing-edge-case)

---

## Phase 05 — Single Agent (version 2)

**Model serving entity:** `helix-shopstream-agent-1`  
**Date tested:** 2026-05-17  
**Transport:** API Gateway (`/ask`) → Databricks Model Serving → PyFunc agent

| Question | Answer (truncated) |
|---|---|
| `What was total revenue last 7 days?` | The total revenue for the last 7 days is: 11638.05 + 18796.05 + 12044.2 + 22540.28 + 23531.0 + 8975.31 + 20803.15 = **109428.04 euros**. |

**How the call flows (Phase 05):**

```
User → /ask (FastAPI) → invoke_agent() → Databricks invocations API
     → ShopStreamAgent.predict()
     → _run_gatekeeper() [8B Llama — ALLOWED/BLOCKED]
     → _run_agent()      [70B Llama — tool loop]
     → _QueryMetricsTool.run() → SQL Warehouse → revenue_daily table
     → answer returned as predictions[0]["answer"]
```

---

## Phase 06 — Multi-Agent Supervisor (version 3)

**Model serving entity:** `helix-shopstream-agent-2`  
**Date tested:** 2026-05-17  
**Transport:** Direct Databricks invocations API (bypassing gateway for testing)

The `predict()` method now returns two fields: `answer` (plain text) and `agent` (which specialist handled it).

| Question | Routed to | Answer (truncated) |
|---|---|---|
| `Are there any revenue anomalies this week?` | `pricing` | Based on the data, the revenue on 2026-05-14 (EUR 12044.2) and 2026-05-11 (EUR 8975.31) appears to be lower compared to the other days. Additionally, the order count on 2026-05-14 (45) is significantly lower. |
| `What was total revenue last 7 days?` | `pricing` | The total revenue for the last 7 days is **EUR 109427.99**. This is calculated by summing the revenue_eur for each day: 11638.05 + 18796.05 + 12044.2 + 22540.28 + 23531.0 + 8975.31 + 20803.15. |
| `How many customers are in the high churn segment?` | `customer` | There are **1996 customers** in the high churn segment, with an average churn probability of **0.762**. This means customers in this segment have approximately 76% risk of churning. |

**How the call flows (Phase 06):**

```
User → /ask (FastAPI) → invoke_agent() → Databricks invocations API
     → ShopStreamAgent.predict()
     → _run_gatekeeper() [8B Llama — ALLOWED/BLOCKED]
     → supervisor.run()
         → supervisor.route()  [keyword match — no LLM call]
             "anomaly"/"revenue" → pricing_agent
             "revenue" → pricing_agent
             "churn"/"segment" → customer_agent
         → specialist_agent.run()  [70B Llama — tool loop]
     → answer + agent name returned as predictions[0]
```

**Routing rules (checked in order — first match wins):**

| Priority | Agent | Trigger keywords |
|---|---|---|
| 1 | `fraud` | fraud, blocked, chargeback, suspicious, decline, flagged, anomaly |
| 2 | `pricing` | price, margin, revenue, pricing, profit, discount, product, billing |
| 3 | `customer` | customer, profile, lifetime, ltv, churn, loyalty, segment, retention |
| — | `customer` (default) | no match |

---

## What the `agent` field means

In Phase 06, `predict()` returns:

```json
{
  "answer": "The total revenue for the last 7 days is EUR 109427.99...",
  "agent": "pricing"
}
```

The `agent` field tells you which specialist handled the question. The API gateway's `invoke_agent()` only reads `answer` — the `agent` field is available at the Databricks layer for debugging but is not surfaced to the end user yet.

---

## Known routing edge case

The question `"Are there any revenue anomalies this week?"` routed to `pricing` (not `fraud`) because `"revenue"` is a pricing keyword and `"anomaly"` was not in the fraud keyword list at the time of this test.

**Why this is acceptable:** the pricing agent has access to the same `revenue_daily` table and correctly identified the low-revenue days. The fraud agent's `check_revenue_anomalies` tool runs the same query. Both give the right answer; only the system prompt differs.

To route anomaly questions to the fraud agent, add `"anomaly"` to the fraud keyword list in [supervisor.py](../../ai_platform/agents/supervisor.py).
