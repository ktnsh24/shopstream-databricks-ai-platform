---
description: "ShopStream Databricks AI Platform — team-wide rules for all contributors. Applies to all file types."
applyTo: "**"
---

# ShopStream Databricks AI Platform — Copilot Instructions

> These instructions apply to ALL sessions in this workspace, for ALL file types.
> Last updated: 2026-05-03

---

## Table of Contents

- [What This Project Is](#what-this-project-is)
- [How We Work](#how-we-work)
- [Architecture Overview](#architecture-overview)
- [Naming Conventions](#naming-conventions)
- [Python Standards](#python-standards)
- [PySpark + Databricks Standards](#pyspark--databricks-standards)
- [SQL Standards](#sql-standards)
- [Testing Standards](#testing-standards)
- [Pre-Commit Review Process](#pre-commit-review-process)
- [Documentation Standards](#documentation-standards)
- [Hands-on Lab Format](#hands-on-lab-format)
- [Definition of Done](#definition-of-done)
- [Universal No-Loss Change Guardrails](#universal-no-loss-change-guardrails)
- [Security Rules](#security-rules)

---

## What This Project Is

**ShopStream Databricks AI Platform** — a production-grade AI data platform built on Azure Databricks.

- **Business domain:** ShopStream (fictional e-commerce — orders, customers, products)
- **Goal:** Business teams ask natural-language questions about business metrics; the platform answers using real-time + batch data processed through a Databricks Medallion architecture and answered by a multi-tool AI agent
- **Stack:** Azure Databricks, Lakeflow, Unity Catalog, Mosaic AI, FastAPI (Azure Container Apps), Terraform
- **Repo:** mono-repo, single environment (`prod`), `main` branch

> **DE parallel:** Helix is like a recommendation engine on top of a data warehouse, but instead of recommending products, it answers business questions. The batch layer (ADLS Gen2 + Delta Lake) is the warehouse. The real-time layer (Event Hubs + Structured Streaming) is the CDC feed. The AI agent is the query engine.

---

## How We Work

- Be direct, no fluff. Use markdown tables and checklists.
- Always include a Table of Contents in every newly created or heavily updated document.
- **Always use DE parallels.** Every AI or Databricks concept must be mapped to a data engineering concept the reader already knows.
- Challenge ideas — push back when an approach has flaws, before implementing.
- **NEVER assume old code is correct** — verify every pattern, annotation, API usage.
- **When uncertain, ask** — don't silently assume and ship.

### Team roles

| Role | Areas of ownership |
|---|---|
| Data Platform | Bronze/Silver/Gold pipelines, Lakeflow jobs, Unity Catalog, Feature Store, ML models (MLflow), API gateway |
| AI + BI | SQL queries on Gold tables, Databricks SQL dashboards, Power BI, data quality rules, documentation, hands-on labs |

### Git workflow

- `main` is the only long-lived branch — it reflects production state
- Feature branches: `feature/`, `fix/`, `data/`, `ai/`, `docs/`
- All changes via PR — at least 1 review before merge
- Commit messages: `type(scope): description` — e.g. `feat(pipelines): add revenue_daily gold table`
- Never commit `.env`, secrets, `terraform.tfvars`, or `*.tfstate`

---

## Architecture Overview

```
Azure Event Hubs (streaming)    ADLS Gen2 (batch)
         │                            │
         ▼                            ▼
   ┌─────────────────────────────────────────┐
   │         Databricks Lakehouse            │
   │  Bronze → Silver → Gold (Delta Lake)    │
   │  Unity Catalog (governance + lineage)   │
   │  Lakeflow (pipelines + orchestration)   │
   │  Mosaic AI (ML + agents + RAG)          │
   └──────────────────┬──────────────────────┘
                      │ REST API
                      ▼
           FastAPI (Azure Container Apps)
           /v1/ask  /v1/metrics  /v1/forecast
           /v1/visualize  /v1/alerts  /health
                      │
                      ▼
             Business teams (SQL, API, Power BI)
```

### Layer ownership

| Folder | Layer | Key features |
|---|---|---|
| `data_platform/` | Bronze/Silver/Gold | Auto Loader, Structured Streaming, Lakeflow SDP, Delta optimizations, Feature Store, Databricks SQL |
| `ml_platform/` | ML | MLflow tracking + registry, PyFunc, Model Serving, drift monitoring |
| `ai_platform/` | AI | Mosaic AI Vector Search, Agent Framework, Unity AI Gateway, AI/BI Genie |
| `api_gateway/` | API | FastAPI, Pydantic v2, async httpx, Azure Container Apps |
| `terraform/` | Infrastructure | Azure resources + Databricks workspace as code (Terraform + DAB) |
| `databricks_apps/` | Internal BI | Streamlit app hosted natively in Databricks |
| `data_generators/` | Test data | Synthetic ShopStream data → ADLS Gen2 + Event Hubs |
| `docs/` | Documentation | Architecture, setup, AI engineering, reference, hands-on labs |

---

## Naming Conventions

### Azure resources
Pattern: `helix-prod-{resource-type}-{name}`

| Resource | Example |
|---|---|
| Resource group | `helix-prod-rg` |
| ADLS account | `helixprodadls` (no hyphens — storage account constraint) |
| Event Hubs namespace | `helix-prod-eventhubs` |
| Key Vault | `helix-prod-kv` |
| Container App | `helix-prod-api` |
| Container Registry | `helixprodacr` |
| Log Analytics | `helix-prod-logs` |

### Databricks / Unity Catalog
| Resource | Convention | Example |
|---|---|---|
| Catalogs | `helix_{layer}` | `helix_bronze`, `helix_silver`, `helix_gold` |
| Schemas | `{domain}` | `orders`, `customers`, `products` |
| Tables | `snake_case` | `revenue_daily`, `customer_metrics` |
| Clusters | `helix-{purpose}-{initials}` | `helix-dev-ks`, `helix-pipeline` |
| Jobs | `helix_{schedule}_{name}` | `helix_nightly_batch`, `helix_streaming_orders` |
| MLflow experiments | `/helix/{model}` | `/helix/forecasting`, `/helix/churn` |
| Model Serving endpoints | `helix-{model}-endpoint` | `helix-churn-endpoint` |
| Vector Search index | `helix_gold.{schema}.{table}_index` | `helix_gold.default.customer_metrics_index` |

### Python
- Modules: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private functions: `_leading_underscore`
- Pydantic models: `PascalCase` with `Model` suffix where ambiguous — e.g. `OrderModel`, `ChartSpec`

---

## Python Standards

### Language & tools
- **Version:** Python 3.12
- **Package manager:** Poetry (`pyproject.toml`, never `requirements.txt`)
- **Linting:** Ruff ONLY — `ruff format . && ruff check . --fix` (never black, isort, pylint)
- **Type hints:** Always on function signatures. Use `X | None` not `Optional[X]`
- **Imports:** Absolute imports, grouped: stdlib → third-party → local

### Core libraries
| Purpose | Library | Notes |
|---|---|---|
| Data models | `pydantic` v2 | `BaseModel` for data, `BaseSettings` for config |
| HTTP client | `httpx` | async everywhere — never `requests` in new code |
| Async framework | `asyncio` + `async/await` | all I/O in FastAPI routes must be async |
| Data processing | `polars` | primary; `pandas` only for Databricks SDK compatibility |
| Logging | `loguru` | never stdlib `logging` |
| Databricks SDK | `databricks-sdk` | for workspace API calls from local/CI |

### Pydantic Settings pattern
```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)
    databricks_host: str
    databricks_token: str
    api_env: str = "prod"
```

### Logging rules (loguru)
- Use `%s` format in log calls, NOT f-strings — prevents PII leaks, cheaper when filtered
- `logger.exception()` ONLY inside `except` blocks — outside it logs `NoneType: None`
- `logger.error()` for error conditions outside exception handlers
- Always include context: `logger.bind(order_id=order_id).info("processing order")`

### Common pitfalls
- `datetime.utcnow()` is deprecated → use `datetime.now(timezone.utc)`
- Return type annotations must match actual return values
- `if result:` is truthy for `(None, event)` tuples → use explicit `is not None`
- `2 ^ n` is XOR in Python, not exponentiation → use `2 ** n`
- Never mix `aiohttp` + `httpx` in the same service

### After any rename (MANDATORY)
```bash
grep -rn "OLD_NAME" .   # must return zero hits before committing
```
Covers: source, tests, docs, config, env files. Mocked tests will NOT catch stale names.

---

## PySpark + Databricks Standards

### Lakeflow Spark Declarative Pipelines (SDP)
```python
import dlt
from pyspark.sql import functions as F

@dlt.table(
    name="silver_orders",
    comment="Cleaned and validated orders",
    table_properties={"quality": "silver"}
)
@dlt.expect("valid_order_id", "order_id IS NOT NULL")
@dlt.expect_or_drop("positive_amount", "amount > 0")
def silver_orders():
    return (
        dlt.read_stream("bronze_orders")
        .withColumn("ingested_at", F.current_timestamp())
    )
```

- Always add `@dlt.expect` / `@dlt.expect_or_drop` on Silver tables — no silent bad data
- Use `dlt.read_stream()` for streaming sources, `dlt.read()` for batch
- Table properties: always set `quality` tag (`bronze`, `silver`, `gold`)

### Auto Loader (batch ingestion)
```python
df = (spark.readStream
    .format("cloudFiles")
    .option("cloudFiles.format", "parquet")
    .option("cloudFiles.schemaLocation", f"{checkpoint_path}/schema")
    .load(source_path))
```

### Structured Streaming (Event Hubs)
- Always set watermarks: `.withWatermark("event_time", "10 minutes")`
- Always set checkpoints: `.option("checkpointLocation", checkpoint_path)`
- Output mode: `append` for fact tables, `complete` for aggregations (with care)

### Delta Lake standards
- All tables in Delta format — never Parquet-only
- Register all tables in Unity Catalog — never `spark.sql("CREATE TABLE ..."`) without catalog prefix
- Full table reference: `helix_{layer}.{schema}.{table_name}`
- Run `OPTIMIZE` + `Z-ORDER BY (order_date, customer_id)` weekly on high-query tables
- `VACUUM` with minimum 7-day retention
- Use `Change Data Feed` for incremental Gold consumption: `.option("readChangeFeed", "true")`

### Broadcast joins
```python
from pyspark.sql.functions import broadcast

# Always use broadcast() for tables < autoBroadcastJoinThreshold (default 10MB)
result = large_orders_df.join(broadcast(small_products_df), "product_id")
```

- Never let Spark guess — use explicit `broadcast()` for known-small tables
- Enable AQE: `spark.conf.set("spark.sql.adaptive.enabled", "true")`

### Cluster rules
- Single-user clusters for dev (never shared for security isolation)
- `autotermination_minutes = 30` enforced via cluster policy — no exceptions
- Use serverless compute for Lakeflow Jobs — no cluster management
- Tag all clusters: `{"project": "helix", "env": "prod", "owner": "<user>"}`

---

## SQL Standards

### Databricks SQL style
- All keywords uppercase: `SELECT`, `FROM`, `WHERE`, `GROUP BY`
- Table references always fully qualified: `helix_gold.orders.revenue_daily`
- Add comments on complex CTEs explaining business logic
- Use `TIMESTAMP AS OF` / `VERSION AS OF` for time travel queries in labs
- Column aliases: `snake_case`, no spaces

### Data quality checks (before promoting to Gold)
```sql
-- Always validate row counts between layers
SELECT COUNT(*) FROM helix_silver.orders.clean_orders
WHERE DATE(ingested_at) = CURRENT_DATE()
```

---

## Testing Standards

### Framework
- **pytest** + **pytest-asyncio** for all Python tests
- `asyncio_mode = "auto"` in `pyproject.toml` — no `loop_scope` kwarg (deprecated)
- PySpark tests: use `pytest` with a local Spark session fixture

### Structure
```
tests/
├── conftest.py          # shared fixtures, settings mocks
├── unit/                # fast, no external services
├── integration/         # with mocked Azure/Databricks services
└── test_*_integration.py  # full end-to-end (run manually)
```

### Mocking strategy
| Target | Tool |
|---|---|
| Azure SDK calls | `unittest.mock.patch` or `pytest-mock` |
| Databricks SDK calls | `pytest-mock` |
| Environment variables | `monkeypatch.setenv()` |
| HTTP calls (httpx) | `respx` (httpx mock library) |

### Test quality rules
- Tests MUST assert behavior, not just "doesn't crash"
- Cover: happy path + error path + at least one edge case per function
- Fixture env var names must exactly match `.env.example` — mocked tests won't catch stale names
- Use `is not None` over bare `if result:` for complex return types

### Running tests
```bash
pytest --tb=short -q
```

---

## Pre-Commit Review Process

> Review as a REVIEWER, not as the author. Never assume old code is correct.

### Step 1: Read the diff
```bash
git diff --cached
```
Read EVERY changed line. Ask: "Is this correct in isolation?"

### Step 2: Mechanical grep checks (every changed `.py` file)
```bash
grep -n 'logger\.exception' <file>        # only inside except blocks?
grep -n '-> str:' <file>                   # return type matches actual value?
grep -n 'if result:\|if response:' <file>  # bare truthiness on complex types?
grep -n 'datetime\.utcnow' <file>          # deprecated — use datetime.now(timezone.utc)
grep -n 'logger\.\w*(f"' <file>            # f-strings in log calls → use %s
```
Fix every hit before committing.

### Step 3: Ruff format + lint
```bash
ruff format . && ruff check . --fix
```

### Step 4: Run tests
```bash
pytest --tb=short -q
```

### Step 5: Semantic review
Trace one happy-path and one error-path for every function changed.

### Step 6: Commit + push

### Step 7: Fetch Copilot PR comments and fix immediately
```bash
gh api repos/{owner}/shopstream-databricks-ai-platform/pulls/{pr}/comments \
  --jq '.[] | select(.user.login | test("copilot|bot"; "i")) | {path: .path, line: .line, body: .body}'
```

---

## Documentation Standards

### Every document must have
1. **Table of Contents** (right after the title, for any doc longer than ~3 screens or with 4+ `##` sections)
2. **DE parallel** for every major concept — `> **DE parallel:** ...` blockquote
3. **🚚 Courier analogy** column in every table (see vocabulary below)
4. **Honest health check** in every endpoint/component deep-dive (real bugs, not aspirational)

### Markdown formatting rules
1. Multi-line blockquotes (`>`) MUST have a blank `>` between paragraphs
2. Tables need a blank line before AND after
3. Lists need a blank line before the first item when preceded by non-list content
4. Heading levels must be sequential — don't skip `##` → `####`
5. Horizontal rules (`---`) need blank lines before and after
6. Every doc longer than ~3 screens must have a TOC — regenerate it when headings change

### 🚚 Courier analogy vocabulary (for all docs)

| Concept | Courier analogy |
|---|---|
| LLM | Courier |
| Chunks / data fragments | Parcel |
| Vector store / search index | GPS warehouse with stadium signs |
| Embedding | GPS coordinates |
| Ingestion pipeline | Post office pre-sorting |
| Prompt / query | Shipping manifest |
| Token | Cargo unit |
| API endpoint | Depot's front door |
| FastAPI | Depot manager |
| Evaluation | Report card |
| Metrics | Tachograph |
| CI/CD | Robot depot hand |
| Terraform | Depot blueprints |
| Delta Lake | The warehouse floor (append-only, versioned) |
| Unity Catalog | The warehouse inventory system (who owns what, who can access what) |
| Medallion architecture | Sorting stages: unsorted mail (Bronze) → verified addresses (Silver) → ready for delivery (Gold) |
| MLflow | Trip logbook — every courier run recorded with route, fuel used, and outcome |
| Model Serving | Permanent courier stationed at a desk — always ready, scales to zero when idle |
| Vector Search | Stadium seating chart — find any seat in ~9 steps, not 50,000 brute-force checks |
| Agent | Dispatcher routing parcels to the right courier |

**Hard rules for courier analogy cells:**
- Every cell must be a full sentence (12–25 words) that names THIS row's concept
- ❌ NEVER write noun + emoji only (e.g., `Depot manager 🏭`, `GPS stamp 📍`) — rewrite to a sentence
- ❌ NEVER multi-sentence stories — one line maximum
- Lead with the technical concept name, then the courier image

### Security — never commit
```bash
# Run before every commit on new/changed files:
git ls-files | xargs grep -inE "(password|api[_-]?key|token)\s*=\s*['\"][^'\"]{6,}['\"]" 2>/dev/null \
  | grep -vE "var\.|os\.environ|getenv|YOUR_|<.*>|test-key|your-key|example"
```
If any hit appears → fix before staging.

---

## Hands-on Lab Format

**MANDATORY: All labs use Swagger UI steps. NEVER curl commands.**

| ❌ Never | ✅ Always |
|---|---|
| `curl -X POST http://localhost:8000/v1/ask -d '...'` | "Open Swagger UI → `POST /v1/ask` → Try it out → paste JSON → Execute" |

### Lab template
```markdown
## Lab N: <Name> — "<one-line description>"

**What it covers:** <Databricks/Azure feature>
**Config knob:** `<ENV_VAR>` (default: `<value>`)
**Hypothesis:** <expected outcome>

### Setup
1. Set `<ENV_VAR>=<value>` in `.env`
2. <Any pipeline/re-ingest steps>
3. Run the same 3 questions via Swagger UI

### Results table
| Value | Result | Latency | Cost | Notes |
|---|---|---|---|---|

### What we learned
<1 paragraph: trade-off + engineering rule of thumb>

### 🚚 Courier takeaway
<1 sentence in courier vocabulary>
```

---

## Observability & Logging Standards

### Structured logging (loguru — mandatory everywhere)

```python
from loguru import logger

# ✅ Correct — %s format, no f-strings
logger.info("Processing order %s for customer %s", order_id, customer_id)
logger.bind(pipeline="silver_orders", batch_date=batch_date).info("Starting pipeline run")

# ✅ Correct — exception only inside except block
try:
    result = await process_order(order_id)
except Exception as exc:
    logger.exception("Failed to process order %s: %s", order_id, exc)
    raise

# ❌ Never — f-string in log call
logger.info(f"Processing order {order_id}")

# ❌ Never — logger.exception outside except
logger.exception("something failed")  # logs NoneType: None
```

### What to log at each layer

| Layer | What to log | Level |
|---|---|---|
| Bronze ingestion | Batch file name, record count, ingestion timestamp | `INFO` |
| Silver pipeline | Rows passed/failed per expectation, schema mismatches | `INFO` / `WARNING` |
| Gold pipeline | Output row count, execution duration, downstream tables written | `INFO` |
| ML training | Hyperparams, metrics (RMSE, AUC), model version registered | `INFO` |
| Model Serving | Input record count, prediction latency, model version used | `INFO` |
| Agent tools | Tool name, NL query received, SQL generated, row count returned | `INFO` |
| API gateway | Route, latency (ms), HTTP status, Databricks call latency | `INFO` |
| Errors everywhere | Full stack trace via `logger.exception()` inside except blocks | `ERROR` |

### Databricks-native observability

- **MLflow tracking:** every training run logs params, metrics, artifacts automatically
- **Lakeflow pipeline events:** monitor via Databricks UI event log (no extra code)
- **Lakehouse Monitoring:** enable on Gold tables for data quality drift detection
- **Databricks system tables:** `system.billing.usage` for cost attribution, `system.access.audit` for access logs
- **Azure Monitor:** Container Apps logs stream to Log Analytics workspace automatically

### Sentry (API gateway — production errors)

```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn=settings.sentry_dsn,
    environment=settings.api_env,
    integrations=[FastApiIntegration()],
    traces_sample_rate=0.1,  # 10% of requests
)
```

Add `sentry_dsn` to `Settings` and `.env.example`. Never log Sentry DSN to stdout.

---

## CI/CD & Docker Standards

### GitHub Actions workflows

| File | Trigger | What it does |
|---|---|---|
| `.github/workflows/ci.yml` | Every push / PR | Ruff lint + format check + pytest |
| `.github/workflows/deploy.yml` | Push to `main` | Docker build → push to ACR → `databricks bundle deploy` → Container Apps deploy |

### Pre-commit hooks (local — run before every push)

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    hooks:
      - id: check-toml
      - id: check-yaml
      - id: trailing-whitespace
      - id: detect-private-key        # blocks accidental secret commits
  - repo: local
    hooks:
      - id: ruff-lint
        entry: poetry run ruff check --fix
      - id: ruff-format
        entry: poetry run ruff format
```

**Run manually:** `poetry run pre-commit run --all-files`

### Dockerfile (FastAPI — public base image)

```dockerfile
FROM python:3.12-slim

WORKDIR /app
RUN pip install poetry==1.8.3

COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-interaction

COPY src/ ./src/

HEALTHCHECK CMD curl -f http://localhost:8000/health || exit 1

CMD ["poetry", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Ruff configuration (`pyproject.toml`)

```toml
[tool.ruff]
line-length = 120
target-version = "py312"
src = ["src/", "tests/"]

[tool.ruff.lint]
extend-select = ["I"]   # import sorting
```

---

## Terraform Standards

### Resource naming
All resources follow: `helix-prod-{type}-{name}` (see Naming Conventions section)

### Mandatory tags on every resource

```hcl
locals {
  common_tags = {
    "project"     = "helix"
    "environment" = "prod"
    "managed-by"  = "terraform"
    "owner"       = "helix-team"
  }
}
```

### Structure rules
- `terraform/azure/` — all Azure resources, one `.tf` file per service
- `terraform/databricks/` — all Databricks workspace resources
- `databricks.bundle.yml` — Databricks Asset Bundle root (jobs, pipelines, model endpoints as IaC)
- Never put provider config in `main.tf` alongside resources — keep `providers.tf` separate
- Use `variable` blocks with `description` and `type` — no raw strings
- Secrets via `azurerm_key_vault_secret` data source — never `var.secret = "hardcoded"`
- Remote state: Azure Storage backend — never local state in CI

### Databricks Asset Bundle (`databricks.bundle.yml`)
```yaml
bundle:
  name: shopstream-databricks-ai-platform

targets:
  prod:
    mode: production
    workspace:
      host: ${var.DATABRICKS_HOST}

resources:
  jobs:
    nightly_batch:
      name: helix_nightly_batch
      # ... job definition
  pipelines:
    orders_bronze:
      name: helix_orders_bronze_pipeline
      # ... pipeline definition
```

All Databricks workspace resources must be declared here — never created manually via UI.

---

## Production Resilience Patterns

### API gateway (FastAPI)
- All Databricks calls: async httpx with `timeout=30.0` — never block the event loop
- Graceful degradation: if Model Serving is down, return cached last result with `stale=true` flag
- Health check (`/health`) must check Databricks connectivity, not just return 200
- Rate limiting at Unity AI Gateway level — not in the FastAPI app itself

### Lakeflow Jobs
- Every job has `on_failure` email + webhook alert configured
- Nightly batch has a repair job: re-run only failed tasks, not the whole DAG
- SLA: Gold tables must be ready by 06:00 UTC — alert if not

### Delta Lake
- Never delete rows — use `is_deleted` soft-delete column + downstream filter
- Schema evolution: `mergeSchema = true` on append, explicit `ALTER TABLE` for breaking changes
- Time travel retention: 30 days minimum on Gold tables

### Data contracts
- Bronze tables enforce schema via Auto Loader `schemaHints`
- Silver tables enforce business rules via `@dlt.expect_or_drop`
- Gold tables have Lakehouse Monitoring enabled — drift alerts within 24h

---

## Cost Controls (mandatory — pay-as-you-go subscription)

| Control | Setting | Where |
|---|---|---|
| Cluster auto-terminate | 30 minutes | `terraform/databricks/compute.tf` (cluster policy) |
| SQL Warehouse auto-stop | 10 minutes | SQL Warehouse config |
| Serverless jobs | Always enabled | `data_platform/jobs/*.yml` |
| Event Hubs tier | Basic (labs), Standard (streaming tests) | `terraform/azure/event_hubs.tf` |
| Foundation Model API | Rate limit 200 req/day (labs) | Unity AI Gateway config |
| Budget alert | €50/month | Azure Cost Management (manual setup) |
| Teardown script | `scripts/teardown.sh` | Run after every lab session |

> **Rule:** Never provision Standard_D-series VMs for interactive clusters. Use serverless or smallest available instance type.

---

## Definition of Done

A story is NOT done until all are checked:

- [ ] Code follows Pre-Commit Review Process (all 7 steps)
- [ ] Tests written: happy path + error path + edge cases
- [ ] `ruff format . && ruff check .` — clean
- [ ] All tests pass: `pytest --tb=short -q`
- [ ] PR created + Copilot PR comments fetched + ALL fixed
- [ ] Relevant docs updated (or confirmed no doc change needed)
- [ ] `.env.example` updated if new env vars added

---

## Universal No-Loss Change Guardrails

Applies to every change: code, docs, tests, config, infra, renames, cleanups.

### Rule 1: No silent omissions
Never silently drop behavior, test coverage, or learning outcomes.
If anything is removed: explicitly list it as Preserved / Merged / Intentionally removed (with reason).

### Rule 2: Parity check before declaring done
Before saying work is complete, produce a parity view:

| Original item | New destination | Status |
|---|---|---|
| Function / table / section from old state | Exact new location | Preserved / Merged / Removed |

### Rule 3: Stop-and-ask triggers
Stop and ask before proceeding if:
- Ambiguous mapping (multiple possible destinations)
- Incomplete source inventory
- Any uncertainty about whether removal is safe

### Rule 4: After any rename
`grep -rn "OLD_NAME" .` across entire repo. Expect zero hits. Fix all before committing.

---

## Security Rules

- All secrets via Azure Key Vault → Databricks secret scope — never hardcoded
- Managed Identity for Container Apps ↔ Azure services — never store client secrets in app config
- Unity Catalog column masking on PII fields (`customer_email`, `first_name`)
- Unity Catalog row filters per team/role
- No `terraform.tfvars` committed — use environment variables (`TF_VAR_*`)
- `terraform.tfstate` gitignored — use Azure Storage backend for remote state
- `AZURE_CLIENT_SECRET` only in GitHub Secrets / Key Vault — never in `.env` on CI
