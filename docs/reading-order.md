# ShopStream Databricks AI Platform — Reading Order

> **Start here.** This page tells you what to read and in what order, whether you're a new team member, a data engineer, or an AI/ML engineer.

---

## Table of Contents

- [If you're brand new to the project](#if-youre-brand-new-to-the-project)
- [If you're a Data Engineer](#if-youre-a-data-engineer)
- [If you're an AI/ML Engineer (Ketan's track)](#if-youre-an-aiml-engineer-ketans-track)
- [All Documents Index](#all-documents-index)

---

## If you're brand new to the project

Read these first, in order. Takes about 45 minutes.

1. [docs/architecture-and-design/system-design.md](architecture-and-design/system-design.md) ⭐ **Start here — the full picture**
   - What Helix is, what problem it solves
   - Full architecture diagram (data sources → Databricks → API → teams)
   - Three data flows: batch, streaming, AI query
   - Technology choices and why

2. [docs/architecture-and-design/repo-structure.md](architecture-and-design/repo-structure.md)
   - What every folder and file does
   - How the folders connect to each other
   - Ownership map (who builds what)

3. [docs/setup-and-tooling/getting-started.md](setup-and-tooling/getting-started.md)
   - One-time setup: poetry install, pre-commit, `.env`
   - Run the data generators
   - Verify your environment is working

---

## If you're a Data Engineer

After reading the brand-new section above, continue with:

### Level 1 — Understand the data layer

1. [data-model.md](architecture-and-design/data-model.md) — All Bronze, Silver, Gold table schemas; column names, types, business meaning
2. [azure-setup.md](setup-and-tooling/azure-setup.md) — Terraform init + apply, Key Vault config, ADLS Gen2 folder structure

### Level 2 — Run the data labs

1. [hands-on-labs-overview.md](hands-on-labs/hands-on-labs-overview.md) — Read the overview and cost guardrails
2. [hands-on-labs-data-platform.md](hands-on-labs/hands-on-labs-data-platform.md) — DP-01 through DP-10 (all 10 data engineering labs)

### Level 3 — Run the ML labs

1. [hands-on-labs-ml-platform.md](hands-on-labs/hands-on-labs-ml-platform.md) — ML-01 through ML-05

---

## If you're an AI/ML Engineer (Ketan's track)

After reading the brand-new section above, continue with:

### Level 1 — Understand the AI layer

1. [rag-pipeline.md](ai-engineering/rag-pipeline.md) — How documents get chunked, embedded, and indexed; how Vector Search stays in sync with Delta
2. [agent-framework.md](ai-engineering/agent-framework.md) — How the agent orchestrator works, what each tool does, how tool selection happens
3. [multi-agent.md](ai-engineering/multi-agent.md) — How the supervisor routes questions to specialist sub-agents (fraud / pricing / customer)
4. [mlflow-tracking.md](ai-engineering/mlflow-tracking.md) — Experiment tracking, model registry, model aliases, PyFunc wrappers
5. [evaluation.md](ai-engineering/evaluation.md) — Rule-based vs LLM-as-judge; how to interpret faithfulness and relevance scores
6. [observability.md](ai-engineering/observability.md) — Inference Tables, Lakehouse Monitoring, Llama Guard guardrails, drift detection

### Level 2 — Production patterns

1. [production-patterns.md](ai-engineering/production-patterns.md) — Gatekeeper (cheap model blocks bad inputs), retry with backoff, structured output with Pydantic

### Level 3 — Understand the MCP server

1. [mcp-server.md](ai-engineering/mcp-server.md) — How to connect an AI client (Claude Desktop, Copilot) to live Databricks data via MCP tools

### Level 3 — Understand the API

1. [api-reference.md](architecture-and-design/api-reference.md) — Every endpoint: request schema, response schema, worked examples

### Level 4 — Run all labs

1. [hands-on-labs-overview.md](hands-on-labs/hands-on-labs-overview.md) — Read the overview and cost guardrails
2. [hands-on-labs-data-platform.md](hands-on-labs/hands-on-labs-data-platform.md) — DP-01 through DP-10 (do these first — foundation)
3. [hands-on-labs-ml-platform.md](hands-on-labs/hands-on-labs-ml-platform.md) — ML-01 through ML-05
4. [hands-on-labs-ai-platform.md](hands-on-labs/hands-on-labs-ai-platform.md) — AI-01 through AI-10
5. [hands-on-labs-api-gateway.md](hands-on-labs/hands-on-labs-api-gateway.md) — GW-01 through GW-04

---

## All Documents Index

### Architecture & Design

| Document | What it covers | Audience |
|---|---|---|
| [system-design.md](architecture-and-design/system-design.md) ⭐ | Full architecture, data flows, tech choices, cost table | Everyone |
| [repo-structure.md](architecture-and-design/repo-structure.md) | Every folder and file, ownership map | Everyone |
| [data-model.md](architecture-and-design/data-model.md) | Bronze/Silver/Gold table schemas, column meanings | Data Engineers |
| [api-reference.md](architecture-and-design/api-reference.md) | All 7 API endpoints with request/response schemas | AI/ML Engineers |

### Setup & Tooling

| Document | What it covers | Audience |
|---|---|---|
| [getting-started.md](setup-and-tooling/getting-started.md) | First-time local setup | Everyone |
| [azure-setup.md](setup-and-tooling/azure-setup.md) | Terraform, Key Vault, ADLS, Event Hubs | Data Engineers |
| [databricks-setup.md](setup-and-tooling/databricks-setup.md) | Unity Catalog, secret scopes, cluster policies | Both |

### AI Engineering

| Document | What it covers | Audience |
|---|---|---|
| [rag-pipeline.md](ai-engineering/rag-pipeline.md) | Document ingestion, chunking, embedding, vector index | AI/ML Engineers |
| [agent-framework.md](ai-engineering/agent-framework.md) | Multi-tool agent, tool selection, structured output | AI/ML Engineers |
| [multi-agent.md](ai-engineering/multi-agent.md) | Supervisor + specialist sub-agents (fraud / pricing / customer) | AI/ML Engineers |
| [mlflow-tracking.md](ai-engineering/mlflow-tracking.md) | Experiments, model registry, PyFunc, Model Serving | AI/ML Engineers |
| [evaluation.md](ai-engineering/evaluation.md) | Rule-based eval, LLM-as-judge, MLflow Evaluate | AI/ML Engineers |
| [observability.md](ai-engineering/observability.md) | Inference Tables, Lakehouse Monitoring, Llama Guard, drift detection | AI/ML Engineers |
| [production-patterns.md](ai-engineering/production-patterns.md) | Gatekeeper, retry with backoff, structured output — production-hardened patterns | AI/ML Engineers |
| [mcp-server.md](ai-engineering/mcp-server.md) | MCP protocol, tool registration, Claude Desktop integration | AI/ML Engineers |

### Hands-on Labs

| Document | Labs | Audience |
|---|---|---|
| [hands-on-labs-overview.md](hands-on-labs/hands-on-labs-overview.md) ⭐ | All 24 labs — overview, cost guardrails, learning order | Everyone |
| [hands-on-labs-data-platform.md](hands-on-labs/hands-on-labs-data-platform.md) | DP-01 to DP-10 — data engineering labs | Everyone |
| [hands-on-labs-ml-platform.md](hands-on-labs/hands-on-labs-ml-platform.md) | ML-01 to ML-05 — ML platform labs | Both |
| [hands-on-labs-ai-platform.md](hands-on-labs/hands-on-labs-ai-platform.md) | AI-01 to AI-10 — AI platform labs | AI/ML Engineers |
| [hands-on-labs-api-gateway.md](hands-on-labs/hands-on-labs-api-gateway.md) | GW-01 to GW-04 — API gateway labs | AI/ML Engineers |
