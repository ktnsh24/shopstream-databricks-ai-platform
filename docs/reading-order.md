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

### Level 1 — Run the data labs

1. [hands-on-labs-overview.md](hands-on-labs/hands-on-labs-overview.md) — Read the overview and cost guardrails
2. [hands-on-labs-data-platform.md](hands-on-labs/hands-on-labs-data-platform.md) — DP-01 through DP-10 (all 10 data engineering labs)

### Level 2 — Run the ML labs

1. [hands-on-labs-ml-platform.md](hands-on-labs/hands-on-labs-ml-platform.md) — ML-01 through ML-05

---

## If you're an AI/ML Engineer (Ketan's track)

After reading the brand-new section above, continue with:

### Level 1 — Run all labs

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

### Setup & Tooling

| Document | What it covers | Audience |
|---|---|---|
| [getting-started.md](setup-and-tooling/getting-started.md) | First-time local setup | Everyone |
| [resume-from-shutdown.md](setup-and-tooling/resume-from-shutdown.md) | Recreate Vector Search + Model Serving after cost shutdown | AI/ML Engineers |

### Hands-on Labs

| Document | Labs | Audience |
|---|---|---|
| [hands-on-labs-overview.md](hands-on-labs/hands-on-labs-overview.md) ⭐ | All 24 labs — overview, cost guardrails, learning order | Everyone |
| [hands-on-labs-data-platform.md](hands-on-labs/hands-on-labs-data-platform.md) | DP-01 to DP-10 — data engineering labs | Everyone |
| [hands-on-labs-ml-platform.md](hands-on-labs/hands-on-labs-ml-platform.md) | ML-01 to ML-05 — ML platform labs | Both |
| [hands-on-labs-ai-platform.md](hands-on-labs/hands-on-labs-ai-platform.md) | AI-01 to AI-10 — AI platform labs | AI/ML Engineers |
| [hands-on-labs-api-gateway.md](hands-on-labs/hands-on-labs-api-gateway.md) | GW-01 to GW-04 — API gateway labs | AI/ML Engineers |
