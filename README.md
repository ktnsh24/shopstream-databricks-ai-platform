# ShopStream Databricks AI Platform

A production-grade AI data platform built on Azure Databricks. Business teams ask natural-language questions about ShopStream (fictional e-commerce) operational data and get live, data-grounded answers in seconds.

## What it does

- Ingests order, customer, and product data via streaming (Event Hubs) and batch (ADLS Gen2)
- Processes data through Bronze → Silver → Gold Medallion architecture using Lakeflow pipelines
- Trains and serves ML models (revenue forecast, churn prediction) via MLflow + Model Serving
- Answers business questions via a multi-tool AI agent backed by Databricks Foundation Model APIs
- Exposes everything through a FastAPI gateway deployed on Azure Container Apps

## Quick links

| | |
|---|---|
| **Deploy from scratch** | [docs/setup-and-tooling/getting-started.md](docs/setup-and-tooling/getting-started.md) |
| **Resume after shutdown** | [docs/setup-and-tooling/resume-from-shutdown.md](docs/setup-and-tooling/resume-from-shutdown.md) |
| **Architecture** | [docs/architecture-and-design/system-design.md](docs/architecture-and-design/system-design.md) |
| **Repo structure** | [docs/architecture-and-design/repo-structure.md](docs/architecture-and-design/repo-structure.md) |
| **Hands-on labs** | [docs/hands-on-labs/hands-on-labs-overview.md](docs/hands-on-labs/hands-on-labs-overview.md) |
| **Reading order** | [docs/reading-order.md](docs/reading-order.md) |
| **API examples** | [docs/reference/example-conversations.md](docs/reference/example-conversations.md) |

## Current status

| Phase | Topic | Status |
|---|---|---|
| 00 | Setup + tooling | ✅ Done |
| 01 | Azure infra (Terraform) | ✅ Done |
| 02 | Data platform (Lakeflow pipelines) | ⏳ Planned |
| 03 | ML platform (MLflow, Feature Store) | ⏳ Planned |
| 04 | AI platform (agent, RAG, Vector Search) | ✅ Done |
| 05 | API Gateway (FastAPI on Container Apps) | ✅ Done |
| 06 | Multi-agent supervisor | ✅ Done |
| 07 | MCP Server | ⏳ Planned |
| 08 | Observability (guardrails, monitoring) | ✅ Done |
| 09 | Production patterns (gatekeeper, retry, structured output) | ✅ Done |

## Tech stack

| Layer | Technology |
|---|---|
| Cloud | Azure (Container Apps, ACR, Key Vault, ADLS Gen2) |
| Data platform | Azure Databricks, Lakeflow SDP (DLT), Delta Lake |
| Governance | Unity Catalog |
| ML | MLflow, Databricks Feature Store, Model Serving |
| AI | Foundation Model APIs (Llama 3.3 70B), Mosaic AI Vector Search, Agent Framework |
| API | FastAPI, httpx, Pydantic v2, Poetry |
| IaC | Terraform (azurerm) |
