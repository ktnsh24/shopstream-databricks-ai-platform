# ShopStream Databricks AI Platform - Hands-on Labs Overview (Fail-First Edition)

## Table of Contents

- [Purpose](#purpose)
- [Fail-First Learning Contract](#fail-first-learning-contract)
- [Prerequisites](#prerequisites)
- [Track Map (24 Labs)](#track-map-24-labs)
- [Where to Run Each Track](#where-to-run-each-track)
- [Cost Guardrails](#cost-guardrails)
- [Recommended Order](#recommended-order)
- [Lab Files](#lab-files)

---

## Purpose

These labs are designed to teach how to recover a broken system, not just how to run a healthy demo.

Each lab starts with failure, then guides you to a safe fix, then proves improvement with before/after numbers.

> DE parallel: this is the same as running a pipeline postmortem where you first reproduce the failed DAG run, then apply one fix at a time until SLA is restored.

---

## Fail-First Learning Contract

Every lab in this project must include:

1. Broken baseline state
2. Observable failure signals
3. Guided fix path (smallest change first)
4. Before vs after comparison
5. Plain conclusion with DE parallel

If a lab has only happy-path steps, it is incomplete.

---

## Prerequisites

Before running labs:

1. Azure subscription and Databricks workspace are provisioned
2. Terraform baseline applied
3. Local environment configured from `.env.example`
4. Seed data generated at least once
5. Swagger UI is reachable for API labs

Setup guide: [../setup-and-tooling/getting-started.md](../setup-and-tooling/getting-started.md)

---

## Track Map (24 Labs)

| Track | Labs | Goal |
|---|---:|---|
| Data Platform | 10 | Recover ingestion, quality, SCD, and performance failures |
| ML Platform | 5 | Recover feature/training/serving failures |
| AI Platform | 5 | Recover retrieval/agent/evaluation failures |
| API Gateway | 4 | Recover deployment, routing, and runtime failures |
| **Total** | **24** | **Broken to production-ready progression** |

---

## Where to Run Each Track

- Data Platform: Databricks Jobs, Lakeflow pipelines, SQL editor
- ML Platform: Databricks notebooks, MLflow UI, Model Serving endpoints
- AI Platform: Agent and evaluation notebooks plus Swagger UI for app endpoints
- API Gateway: Swagger UI only for endpoint calls (never curl)

---

## Cost Guardrails

| Guardrail | Target |
|---|---|
| Cluster auto-terminate | 30 min max |
| SQL warehouse auto-stop | 10 min max |
| LLM request cap | 200/day max |
| Session teardown | Run `scripts/teardown.sh` after every lab block |

---

## Recommended Order

1. Data Platform labs DP-01 to DP-10
2. ML Platform labs ML-01 to ML-05
3. AI Platform labs AI-01 to AI-05
4. API Gateway labs GW-01 to GW-04

This sequence follows DE reality: stable data first, then model quality, then AI behavior, then serving/runtime.

---

## Lab Files

- [hands-on-labs-data-platform.md](hands-on-labs-data-platform.md)
- [hands-on-labs-ml-platform.md](hands-on-labs-ml-platform.md)
- [hands-on-labs-ai-platform.md](hands-on-labs-ai-platform.md)
- [hands-on-labs-api-gateway.md](hands-on-labs-api-gateway.md)
