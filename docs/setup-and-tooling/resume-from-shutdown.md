# Resume From Shutdown — Recreate Vector Search + Model Serving

You deleted two always-on resources to save money:

1. **Vector Search endpoint** — `helix-vs-endpoint`
2. **Model Serving endpoint** — `helix-shopstream-agent`

This document tells you exactly what to do to get both back, in order.
Everything else (Azure resources, Unity Catalog tables, gold data tables) is still intact.

---

## Table of Contents

1. [Before you start — check what is already there](#1-before-you-start--check-what-is-already-there)
2. [Step 1 — Recreate the Vector Search endpoint and index](#2-step-1--recreate-the-vector-search-endpoint-and-index)
3. [Step 2 — Recreate the Model Serving endpoint](#3-step-2--recreate-the-model-serving-endpoint)
4. [Step 3 — Verify end-to-end](#4-step-3--verify-end-to-end)

---

## 1. Before you start — check what is already there

Some things survive the shutdown and do **not** need to be recreated.

Open Databricks → **Data** and confirm these tables exist in `helix_databricks.default`:

| Table | Must exist before you start |
|---|---|
| `document_chunks` | Required for Vector Search index |
| `revenue_daily` | Required for pricing agent SQL tool |
| `product_performance` | Required for pricing agent SQL tool |
| `customer_metrics` | Required for customer agent SQL tool |

If any table is **missing**, see the [Known gotchas](#known-gotchas) section at the bottom.

---

## 2. Step 1 — Recreate the Vector Search endpoint and index

### What you are recreating

- A Vector Search **endpoint** named `helix-vs-endpoint` (shared infrastructure, takes ~5 min to spin up)
- A delta-sync **index** on `document_chunks` named `document_chunks_index`

### How to do it

**Option A — Run the notebook (recommended)**

1. Databricks → **Workspace** → navigate to your repo → `ai_platform/vector_search/`
2. Open `create_index.py`
3. Click **Run All**
4. Wait until you see: `Index helix_databricks.default.document_chunks_index is ONLINE`

This takes **5–10 minutes** on a fresh endpoint. The notebook waits and polls automatically — you do not need to do anything.

**Option B — Manual UI steps (if the notebook fails)**

1. Databricks → **Compute** → **Vector Search** → **Create endpoint**
   - Name: `helix-vs-endpoint`
   - Click **Create**
   - Wait for status `ONLINE` (~5 min)

2. Databricks → **Catalog** → `helix_databricks` → `default` → `document_chunks` → **Create index**
   - Index name: `document_chunks_index`
   - Index type: **Delta Sync Index**
   - Primary key: `chunk_id`
   - Embedding source column: `chunk_text`
   - Embedding model: `databricks-gte-large-en`
   - Endpoint: `helix-vs-endpoint`
   - Click **Create**
   - Wait for status `ONLINE`

### How to confirm it worked

Databricks → **Compute** → **Vector Search** → click `helix-vs-endpoint` → the index `document_chunks_index` should show status **Online** with a row count > 0.

---

## 3. Step 2 — Recreate the Model Serving endpoint

The agent model is already registered in Unity Catalog with the `@champion` alias from before. You only need to recreate the serving endpoint that points to it.

> **Do NOT re-run `agent_pyfunc.py`** unless the Unity Catalog model is also gone. Re-running it creates a new model version. The existing version is fine.

### How to check the model is still registered

Databricks → **Catalog** → `helix_databricks` → `default` → `helix-shopstream-agent` → you should see at least version 1 with the `champion` alias.

If the model is missing, you will need to re-run `ai_platform/agents/agent_pyfunc.py` first — **but only if it is missing**.

### Recreate the serving endpoint

1. Databricks → **Serving** → **Create serving endpoint**
2. Fill in:

| Field | Value |
|---|---|
| Name | `helix-shopstream-agent` |
| Model | `helix_databricks.default.helix-shopstream-agent` |
| Version | Latest (or `champion` alias) |
| Compute scale-out | **Scale to zero: enabled** |

3. Click **Create** — wait for status `Ready` (~5–10 min)

### Set environment variables on the endpoint

Without these the agent cannot call the LLM. After the endpoint reaches `Ready`:

1. Click **Edit serving endpoint** (pencil icon, top right)
2. Scroll to **Environment variables** → **Add environment variable** for each:

| Key | Value | Important note |
|---|---|---|
| `DATABRICKS_HOST` | `adb-7405604860980699.19.azuredatabricks.net` | **No `https://` prefix** |
| `DATABRICKS_TOKEN` | your PAT token | From Settings → Developer → Access Tokens |

3. Click **Update serving endpoint**
4. Wait for status `Ready` again (~2–3 min)

> **Why no `https://` prefix on `DATABRICKS_HOST`:** The agent code builds the URL as `f"https://{host}/serving-endpoints/..."`. If you include `https://` in the variable, the final URL becomes `https://https://...` and every LLM call fails with a connection error.

---

## 4. Step 3 — Verify end-to-end

Once the serving endpoint is `Ready`, open Swagger UI in your browser:

```
https://helix-api.niceriver-123f976f.northeurope.azurecontainerapps.io/docs
```

This is the fixed URL for the `helix-api` Container App — it does not change between shutdowns.

**Test 1 — Health check**

1. **GET /health** → **Try it out** → **Execute**
2. Expected: `{"status": "ok"}`

**Test 2 — Pricing agent (uses SQL tool)**

1. **POST /ask** → **Try it out**
2. Request body: `{"question": "What was total revenue last 7 days?"}`
3. Expected: `200` response, `agent: "pricing"`, answer contains euro amounts

**Test 3 — Fraud agent**

1. **POST /ask** → **Try it out**
2. Request body: `{"question": "Are there any revenue anomalies this week?"}`
3. Expected: `agent: "fraud"` in response

**Test 4 — Gatekeeper blocks off-topic**

1. **POST /ask** → **Try it out**
2. Request body: `{"question": "Write me a poem about shipping"}`
3. Expected: `blocked: true` — no token spent on the 70B model

---

## Known gotchas

| Problem | Fix |
|---|---|
| `document_chunks` table missing | Run `ai_platform/vector_search/embed_documents.py` first, then redo Step 1 |
| Gold tables missing (`revenue_daily`, etc.) | Run the seed script from [getting-started.md § Step 10](getting-started.md#10-phase-05--seed-gold-tables) |
| Vector Search index stuck in `Provisioning` for >15 min | Delete the endpoint and recreate it — sometimes the first provision fails silently |
| Serving endpoint `Not Ready` after env vars update | Wait another 2 min and refresh — env var updates force a small restart |
| `helix-shopstream-agent` model not found in Catalog | Re-run `ai_platform/agents/agent_pyfunc.py` with **Run All**, then redo Step 2 |
| Container App URL returns 502 | The Container App scaled to zero. Hit it once and wait 30 sec — it cold-starts automatically |
