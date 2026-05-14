# ShopStream Databricks AI Platform — Repository Structure

## Table of Contents

- [Overview](#overview)
- [Top-Level Files](#top-level-files)
- [Top-Level Folders](#top-level-folders)
- [data\_platform/](#data_platform)
  - [ingest/](#data_platformingest)
  - [pipelines/](#data_platformpipelines)
  - [jobs/](#data_platformjobs)
  - [delta\_sharing/](#data_platformdelta_sharing)
- [ml\_platform/](#ml_platform)
  - [features/](#ml_platformfeatures)
  - [models/](#ml_platformmodels)
  - [serving/](#ml_platformserving)
  - [monitoring/](#ml_platformmonitoring)
- [ai\_platform/](#ai_platform)
  - [rag/](#ai_platformrag)
  - [agents/](#ai_platformagents)
  - [gateway/](#ai_platformgateway)
  - [evaluation/](#ai_platformevaluation)
- [api\_gateway/](#api_gateway)
  - [src/](#api_gatewaysrc)
  - [tests/ (api\_gateway)](#api_gatewaytests)
- [terraform/](#terraform)
  - [azure/](#terraformazure)
  - [databricks/](#terraformdatabricks)
- [databricks\_apps/](#databricks_apps)
- [data\_generators/](#data_generators)
- [docs/](#docs)
- [scripts/](#scripts)
- [tests/](#tests-root)
- [How the Folders Connect](#how-the-folders-connect)
- [Ownership Map](#ownership-map)

---

## Overview

Helix follows a **monorepo** layout. Everything that makes Helix work lives in one repository — data pipelines, ML models, AI agents, the API, and infrastructure. This makes it easier to trace how a change in a Bronze schema ripples through to a Gold table and into an API response.

> **DE parallel:** Think of this repo as a single ETL project where each folder is a different layer of the pipeline — ingest → transform → serve — but for both data *and* AI.

> **🚚 Courier analogy:** The repo is the full courier operation. Each top-level folder is a department: the sorting depot (`data_platform`), the parcels tracking system (`ml_platform`), the smart routing engine (`ai_platform`), the customer-facing counter (`api_gateway`), and the depot infrastructure (`terraform`).

---

## Top-Level Files

| File | Purpose |
|---|---|
| `pyproject.toml` | Python project config: Python 3.12, Poetry, ruff, pytest settings |
| `poetry.lock` | Locked dependency tree — reproducible installs |
| `.env.example` | All env vars the project needs — copy to `.env`, fill in real values |
| `.gitignore` | What never goes into git: secrets, `.env`, `__pycache__`, lab outputs, Terraform state |
| `databricks.bundle.yml` | Databricks Asset Bundle root — declares all Lakeflow jobs and pipelines as versioned IaC |
| `.pre-commit-config.yaml` | Local pre-commit hooks: detect-private-key, ruff lint, ruff format |
| `README.md` | Quick-start guide for new contributors |
| `.github/copilot-instructions.md` | VS Code Copilot rules for the whole team (auto-loaded) |
| `.github/workflows/ci.yml` | GitHub Actions: run on every push — ruff lint + pytest |
| `.github/workflows/deploy.yml` | GitHub Actions: run on push to main — Docker build + DAB deploy + Container Apps deploy |

---

## Top-Level Folders

| Folder | One-line purpose | Layer |
|---|---|---|
| `data_platform/` | Ingest raw data, clean it, aggregate it into Delta tables | Data Engineering |
| `ml_platform/` | Train ML models, store features, serve predictions | Machine Learning |
| `ai_platform/` | RAG, AI agents, LLM evaluation | AI / LLM |
| `api_gateway/` | FastAPI app that business teams call | API Layer |
| `terraform/` | Azure + Databricks infrastructure as code | Infrastructure |
| `databricks_apps/` | Streamlit app hosted inside Databricks (Product team) | Business Surface |
| `data_generators/` | Generate fake ShopStream data for local dev and labs | Developer Tooling |
| `docs/` | All documentation — architecture, guides, hands-on labs | Documentation |
| `scripts/` | Utility shell scripts: setup, teardown, schema refresh | Developer Tooling |
| `tests/` | Shared test utilities + integration test suite | Testing |

---

## data\_platform/

**Purpose:** Everything needed to move raw data from sources (Event Hubs, ADLS Gen2) through the Medallion layers (Bronze → Silver → Gold) into business-ready Delta tables.

> **DE parallel:** This is your ETL codebase. `ingest/` = extract, `pipelines/` = transform, `jobs/` = orchestrate.

### data\_platform/ingest/

Reads from external sources and lands data in Bronze Delta tables.

| File | What it does |
|---|---|
| `ingest_orders_streaming.py` | Reads Order events from Event Hubs (Kafka) via Structured Streaming → writes to `helix_bronze.orders.raw`. Includes 10-min watermark for late events. |
| `ingest_customers_batch.py` | Reads `customers_*.csv` from ADLS Gen2 via Auto Loader → writes to `helix_bronze.customers.raw`. Schema hints enforced at read time. |
| `ingest_products_batch.py` | Reads `products_*.parquet` from ADLS Gen2 via Auto Loader → writes to `helix_bronze.products.raw`. |

**Key patterns used here:**
- Auto Loader (`cloudFiles`) — handles schema inference, schema evolution, new-file detection automatically
- Structured Streaming with watermarks — handles late-arriving events gracefully
- Append-only writes — Bronze never updates rows, only appends new ones

### data\_platform/pipelines/

Spark Declarative Pipelines (Lakeflow SDP). Bronze → Silver → Gold transformations as Python `@dlt.table` and `@dlt.expect_or_drop` declarations.

| File | What it does |
|---|---|
| `orders_pipeline.py` | Bronze orders → Silver (dedup by order_id, validate amount > 0) → Gold `revenue_daily` (daily aggregation by region + category) |
| `customers_pipeline.py` | Bronze customers → Silver (type casting, null handling) → Gold `customer_metrics` (RFM scores, CLV) |
| `products_pipeline.py` | Bronze products → Silver (standardise category names) → Gold `product_performance` (GMV, trend scores) |

**Key patterns used here:**
- `@dlt.table` — declares a materialized Delta table as the output of this function
- `@dlt.expect_or_drop` — rows failing the check are dropped and logged; pipeline keeps running
- `@dlt.read_stream` — reads from an upstream table as a stream (incremental, not full reload)
- Pipelines are deployed via `databricks.bundle.yml` — not run as standalone scripts

### data\_platform/jobs/

Lakeflow Job YAML definitions and the Python code they call.

| File | What it does |
|---|---|
| `nightly_batch_job.yml` | DAB job definition: schedule (01:00 UTC), task order (ingest → pipelines → Feature Store refresh → monitoring), email alert on failure |
| `maintenance_job.yml` | DAB job definition: weekly (Sunday 03:00 UTC), runs OPTIMIZE + VACUUM on all Gold tables |
| `optimize_tables.py` | Python: runs `OPTIMIZE` + `Z-ORDER` on Gold tables (improves query speed by co-locating related data on disk) |
| `vacuum_tables.py` | Python: runs `VACUUM RETAIN 720 HOURS` on all Delta tables (cleans up files older than 30 days) |

> **DE parallel:** `nightly_batch_job.yml` is your Airflow DAG definition. `optimize_tables.py` is your post-load stats refresh. `vacuum_tables.py` is your partition pruning.

### data\_platform/delta\_sharing/

Configuration for sharing Gold tables with external consumers without copying data.

| File | What it does |
|---|---|
| `shares_config.py` | Defines which Gold tables are shared, with which recipients, with which column filters applied. Uses Databricks Delta Sharing protocol. |

---

## ml\_platform/

**Purpose:** Train and deploy ML models that predict revenue forecasts and customer churn. The Feature Store keeps training features and serving features in sync.

> **DE parallel:** `features/` is your feature engineering job. `models/` is your model training job. `serving/` is your Lambda + API that runs the model in production.

### ml\_platform/features/

Feature engineering code and Feature Store registration.

| File | What it does |
|---|---|
| `customer_features.py` | Reads `helix_gold.customers.customer_metrics` → registers a Feature Store feature function. Features: days_since_order, order_frequency_30d, avg_order_value, clv_estimate |
| `product_features.py` | Reads `helix_gold.products.product_performance` → registers product features: trend_score, gmv_30d, units_sold_30d, category_rank |

**Key pattern:** Feature Store functions are registered once; both training jobs and Model Serving endpoints call them at runtime. No copy-paste of feature logic.

### ml\_platform/models/

MLflow experiment code for training both ML models.

| File | What it does |
|---|---|
| `train_forecast.py` | Trains a LightGBM revenue forecasting model. Reads Gold + feature functions. Logs params, metrics (RMSE, MAE), and the trained model to MLflow registry. |
| `train_churn.py` | Trains a LightGBM customer churn model. Binary classification (churn in next 30 days). Logs AUC, F1, confusion matrix to MLflow. |

**Key pattern:** Both training scripts use `mlflow.autolog()` (automatic param + metric logging) plus explicit `mlflow.log_artifact()` for feature importance plots.

### ml\_platform/serving/

MLflow PyFunc wrappers that package models for deployment.

| File | What it does |
|---|---|
| `forecast_model.py` | `mlflow.pyfunc.PythonModel` subclass for the forecasting model. `predict()` method: accepts a DataFrame of features, returns a forecast DataFrame. Business logic (e.g. cap negative forecasts at 0) is inside the wrapper, not in the raw model. |
| `churn_model.py` | Same pattern for churn model. Returns `churn_probability` and `churn_risk_label` (Low/Medium/High). |

> **DE parallel:** PyFunc wrappers = the ETL transformation layer around a raw model. The model is the engine; the wrapper is the job that calls it with the right inputs and returns the right outputs.

### ml\_platform/monitoring/

Model serving performance monitoring and inference table analysis.

| File | What it does |
|---|---|
| `inference_monitor.py` | Queries Inference Tables (auto-created by Databricks on Model Serving endpoints). Tracks: latency trends, error rates, model version comparison. Returns SQL query templates for latency, drift, and errors. |
| `model_monitor.py` | Uses Databricks Lakehouse Monitoring API to create monitors on Gold inference tables. Alerts if prediction drift > 10% week-over-week. |
| `config/inference_tables.py` | Configuration for each model's inference table location + monitoring thresholds (p95 latency, error rate, drift tolerance). |

> **What are Inference Tables?** Auto-created Delta tables in Unity Catalog that log every prediction request/response. Databricks auto-populates them when you enable inference logging on a Model Serving endpoint. Use them for: debugging prod issues, latency monitoring, model version comparison, and compliance audits.

---

## ai\_platform/

**Purpose:** RAG pipeline, multi-tool AI agent, LLM evaluation. This is where unstructured business questions become structured, data-grounded answers.

> **🚚 Courier analogy:** `rag/` builds the parcel index (vector search index). `agents/` is the dispatcher who decides which route to take for each delivery request. `gateway/` is the rate-limit desk at the depot entrance. `evaluation/` is the quality-control station at the end of the line.

### ai\_platform/rag/

RAG (Retrieval Augmented Generation) pipeline: index Gold tables and business PDFs so the agent can retrieve relevant context.

| File | What it does |
|---|---|
| `ingest_documents.py` | Reads business PDFs from ADLS Gen2, chunks them, creates embeddings via Foundation Model API (Llama embed model), writes to `helix_gold.documents.chunks` Delta table |
| `vector_search_index.py` | Creates / refreshes Mosaic AI Vector Search serverless index on `helix_gold.documents.chunks`. Index syncs automatically on Delta table update. |

**Key pattern:** The vector index is backed by a Delta table (not a separate database). Syncing happens automatically — no separate index rebuild job.

### ai\_platform/agents/

Multi-tool AI agent: the orchestrator plus all tool implementations.

| File | What it does |
|---|---|
| `orchestrator.py` | The main agent. Calls `agent.run(question)` → produces a structured `AgentResponse` Pydantic model. Manages tool selection, step limits (`AGENT_MAX_STEPS`), and error handling. |
| `tools/query_metrics.py` | Tool: converts a natural language question to SQL via the LLM, validates the SQL against Unity Catalog schema, executes on SQL Serverless Warehouse, returns a DataFrame. |
| `tools/search_documents.py` | Tool: embeds the query, calls Vector Search, returns top-N relevant document chunks with similarity scores. |
| `tools/forecast.py` | Tool: calls the Model Serving forecast endpoint, returns a 7-day revenue forecast as a list of `{date, predicted_revenue}` dicts. |
| `tools/generate_chart.py` | Tool: takes a DataFrame (from `query_metrics`) and a chart type, returns a Vega-Lite JSON spec + the data to render it. |
| `tools/text_to_sql.py` | Standalone text-to-SQL utility used by `query_metrics`. Builds a schema-aware prompt from Unity Catalog metadata, calls the Foundation Model API, returns validated SQL. |
| `tools/alert_tool.py` | Tool: queries Lakehouse Monitoring results for data quality alerts on Gold tables. Returns alerts if any thresholds breached. |

### ai\_platform/gateway/

Unity AI Gateway configuration (deployed via Terraform, config declared here).

| File | What it does |
|---|---|
| `gateway_config.py` | Python dataclass representation of the Unity AI Gateway config: endpoints registered, rate limits per team, guardrail patterns (blocks harmful/off-topic queries), audit log config |

### ai\_platform/evaluation/

LLM answer quality evaluation. Tracks whether the agent's answers are correct and grounded.

| File | What it does |
|---|---|
| `evaluator.py` | Runs MLflow Evaluate against a golden dataset. Two modes: `rule_based` (cosine similarity + keyword overlap) and `llm_judge` (Llama 3.3 judges faithfulness + relevance). |
| `golden_dataset.py` | 30 curated question/expected-answer pairs covering all 3 business teams. Source of truth for evaluating agent quality. |

---

## api\_gateway/

**Purpose:** FastAPI application that business teams and external systems call. Translates HTTP requests into Databricks and Mosaic AI calls, returns structured responses.

### api\_gateway/src/

| Path | What it does |
|---|---|
| `src/main.py` | FastAPI app entrypoint. Registers all routers, Sentry middleware, lifespan (startup health check). |
| `src/config.py` | `pydantic_settings.BaseSettings` — loads all config from environment variables. One source of truth for every secret and setting. |
| `src/routes/ask.py` | `POST /v1/ask` — validates request, calls agent orchestrator, streams response back (SSE) |
| `src/routes/metrics.py` | `GET /v1/metrics` — calls SQL Warehouse for live Gold table data, returns typed Pydantic model |
| `src/routes/forecast.py` | `POST /v1/forecast` — calls Model Serving forecast endpoint, validates and returns prediction |
| `src/routes/visualize.py` | `POST /v1/visualize` — NL → chart spec + data, returns `VisualizationResponse` Pydantic model |
| `src/routes/report.py` | `POST /v1/report` — assembles context from metrics + documents + agent, calls LLM to generate structured report |
| `src/routes/alerts.py` | `GET /v1/alerts` — reads Lakehouse Monitoring results, returns list of active data quality alerts |
| `src/routes/health.py` | `GET /health` — checks Databricks connectivity + Vector Search status; returns real status, not hardcoded `"healthy"` |
| `src/models/` | Pydantic v2 request/response models for every endpoint |
| `src/clients/` | Async httpx clients for Databricks REST API, Model Serving, Vector Search |
| `src/middleware/` | Logging middleware (log every request: route, latency, status), auth middleware (verify Azure Managed Identity token) |

### api\_gateway/tests/

FastAPI unit tests. Every route has: happy path, validation error path, Databricks failure path.

---

## terraform/

**Purpose:** All Azure and Databricks infrastructure declared as code. Nothing created manually in the Azure portal or Databricks UI.

### terraform/azure/

| File | What it provisions |
|---|---|
| `providers.tf` | `azurerm` + `databricks` provider config |
| `variables.tf` | All input variables with descriptions and types |
| `outputs.tf` | Key outputs: storage account URL, Event Hubs endpoint, Key Vault URI |
| `storage.tf` | ADLS Gen2 storage account + containers (`/raw/`, `/checkpoints/`, `/delta/`) |
| `event_hubs.tf` | Event Hubs namespace + hub (`helix-orders`) + consumer group |
| `key_vault.tf` | Key Vault + access policies for Container Apps managed identity |
| `container_apps.tf` | Container Apps environment + app (API gateway deployment) |
| `acr.tf` | Azure Container Registry (stores the API gateway Docker image) |
| `network.tf` | VNet + Private Endpoints for ADLS and Event Hubs |
| `monitoring.tf` | Log Analytics workspace + Azure Monitor alerts |

### terraform/databricks/

| File | What it provisions |
|---|---|
| `workspace.tf` | Databricks workspace (VNet-injected) |
| `unity_catalog.tf` | Unity Catalog metastore + 3 catalogs (bronze, silver, gold) |
| `compute.tf` | Cluster policies (autotermination, instance type restrictions) |
| `secret_scopes.tf` | Databricks secret scope backed by Azure Key Vault |
| `sql_warehouse.tf` | Serverless SQL Warehouse for queries + AI/BI Genie |
| `ai_gateway.tf` | Unity AI Gateway endpoint config + rate limits |

---

## databricks\_apps/

**Purpose:** Streamlit application hosted inside Databricks workspace, giving the Product team an interactive product performance explorer.

| Folder | What it contains |
|---|---|
| `shopstream_dashboard/app.py` | Streamlit app: reads from Gold tables via Databricks SQL connector, renders charts with Plotly, exposes product performance filters |
| `shopstream_dashboard/requirements.txt` | Streamlit-specific Python deps (separate from the main pyproject.toml) |

> **Note:** Databricks Apps deploy from the workspace, not from Container Apps. The app is registered via `databricks.bundle.yml`.

---

## data\_generators/

**Purpose:** Generate realistic fake ShopStream data for local development, unit tests, and lab exercises. Nothing here touches production data.

| File | What it generates |
|---|---|
| `generate_orders.py` | Fake Order events as JSON (uses Faker). Configurable: number of orders, date range, product/customer pool. Can publish to Event Hubs or write to local files. |
| `generate_customers.py` | Fake customer records as CSV. Configurable: size, churn rate distribution. |
| `generate_products.py` | Fake product catalog as Parquet. Configurable: categories, price ranges. |
| `seed_delta_tables.py` | Orchestrates all three generators and writes directly to local Delta tables (for integration tests that need pre-seeded tables). |

---

## docs/

**Purpose:** All documentation. Written for two audiences: new team members learning the system, and developers running hands-on labs.

| Path | What it contains |
|---|---|
| `docs/reading-order.md` | Start here — map of what to read and in what order |
| `docs/architecture-and-design/system-design.md` | Full system architecture, data flows, technology choices |
| `docs/architecture-and-design/repo-structure.md` | This file — folder and subfolder descriptions |
| `docs/architecture-and-design/data-model.md` | All Delta table schemas: Bronze, Silver, Gold — column names, types, business meaning |
| `docs/architecture-and-design/api-reference.md` | Every API endpoint: request/response schema, worked examples, error codes |
| `docs/setup-and-tooling/getting-started.md` | How to set up local dev: poetry install, pre-commit, `.env` setup, first run |
| `docs/setup-and-tooling/azure-setup.md` | Azure-specific setup: Terraform init, Key Vault config, Managed Identity |
| `docs/setup-and-tooling/databricks-setup.md` | Databricks workspace setup: Unity Catalog, secret scopes, cluster policies |
| `docs/ai-engineering/rag-pipeline.md` | How the RAG pipeline works: chunking, embedding, vector indexing, retrieval |
| `docs/ai-engineering/agent-framework.md` | How the multi-tool agent works: tool selection, step limits, structured output |
| `docs/ai-engineering/evaluation.md` | How LLM answer quality is measured: rule-based vs LLM-as-judge |
| `docs/ai-engineering/mlflow-tracking.md` | How MLflow experiment tracking and model registry work in Helix |
| `docs/hands-on-labs/hands-on-labs-overview.md` | All 24 labs across 4 tracks — what you do, what you learn, estimated cost |
| `docs/hands-on-labs/hands-on-labs-data-platform.md` | 10 data engineering labs (Bronze through Gold, streaming, Delta features) |
| `docs/hands-on-labs/hands-on-labs-ml-platform.md` | 5 ML labs (Feature Store, MLflow training, PyFunc, Model Serving) |
| `docs/hands-on-labs/hands-on-labs-ai-platform.md` | 5 AI labs (RAG, agent, LLM evaluation, tuning) |
| `docs/hands-on-labs/hands-on-labs-api-gateway.md` | 4 API labs (deploy FastAPI, call each endpoint, streaming response) |

---

## scripts/

**Purpose:** Shell scripts for developer workflows. Run from the repo root.

| Script | What it does |
|---|---|
| `setup.sh` | One-time setup: `poetry install`, `pre-commit install`, copy `.env.example` → `.env` |
| `teardown.sh` | Destroy all Azure + Databricks resources (run after every lab to avoid idle costs) |
| `refresh_schema.sh` | Fetch latest Unity Catalog schemas and write to `docs/architecture-and-design/data-model.md` |
| `run_labs.sh` | Wrapper for running all hands-on labs sequentially with cost monitoring |

---

## tests/ (root)

**Purpose:** Shared test utilities and integration tests that span multiple platform layers.

| Path | What it contains |
|---|---|
| `tests/conftest.py` | Shared pytest fixtures: mock Databricks client, mock LLM responses, sample DataFrames, fake config |
| `tests/integration/test_full_pipeline.py` | End-to-end test: seed fake data → run pipeline → verify Gold table output |
| `tests/integration/test_agent_flow.py` | End-to-end test: POST `/v1/ask` with a question → verify agent returns structured answer |

Unit tests for each platform layer live alongside the code they test (in `data_platform/tests/`, `ml_platform/tests/`, etc.).

---

## How the Folders Connect

```text
data_generators/    →  data_platform/ingest/   (feeds test data to Bronze)
data_platform/      →  ml_platform/features/   (Gold tables → Feature Store)
data_platform/      →  ai_platform/rag/        (Gold tables → Vector Search index)
ml_platform/        →  ai_platform/agents/     (Model Serving endpoints → forecast tool)
ai_platform/        →  api_gateway/            (agent orchestrator called from /v1/ask)
terraform/          →  all folders             (provisions the infra everything runs on)
databricks.bundle   →  data_platform/jobs/ + pipelines/  (declares jobs as IaC)
databricks_apps/    →  data_platform/          (reads Gold tables directly)
```

---

## Ownership Map

| Folder / Repo | Primary owner | Wife's scope (DE role) | Ketan's scope (AI/ML role) |
|---|---|---|---|
| `shopstream-databricks-data-platform` | Wife | ✅ Full ownership | ✅ Review + pipeline input |
| `shopstream-databricks-mcp-server` | Ketan | Read-only | ✅ Full ownership |
| `data_platform/` | Both | ✅ Full ownership | ✅ Review + pipeline input |
| `ml_platform/features/` | Both | ✅ Feature engineering | ✅ Feature design |
| `ml_platform/models/` | Ketan | Read-only | ✅ Full ownership |
| `ml_platform/serving/` | Ketan | Read-only | ✅ Full ownership |
| `ai_platform/` | Ketan | Read-only | ✅ Full ownership |
| `api_gateway/` | Ketan | Read-only | ✅ Full ownership |
| `terraform/azure/` | Both | ✅ Full ownership | ✅ Review |
| `terraform/databricks/` | Ketan | Read setup docs | ✅ Full ownership |
| `databricks_apps/` | Both | ✅ Streamlit UI | ✅ Backend data connection |
| `data_generators/` | Both | ✅ For DE labs | ✅ For AI labs |
| `docs/` | Both | ✅ DE sections | ✅ AI/ML sections |
