# Getting Started — Deploy Helix From Scratch

This guide takes you from zero to a running Helix stack on a **new Azure account and a new Databricks workspace**. Follow the steps in order. Every step has been verified on the original deployment.

---

## Table of Contents

1. [What you need before you start](#1-what-you-need-before-you-start)
2. [Phase 00 — Clone the repo and install tools](#2-phase-00--clone-the-repo-and-install-tools)
3. [Phase 01 — Create Azure resources with Terraform](#3-phase-01--create-azure-resources-with-terraform)
4. [Phase 01 — Store secrets in Key Vault manually](#4-phase-01--store-secrets-in-key-vault-manually)
5. [Phase 01 — Create Databricks workspace manually](#5-phase-01--create-databricks-workspace-manually)
6. [Phase 04 — Run AI platform notebooks in order](#6-phase-04--run-ai-platform-notebooks-in-order)
7. [Phase 04 — Register model and start serving endpoint](#7-phase-04--register-model-and-start-serving-endpoint)
8. [Phase 05 — Build and deploy the API Gateway](#8-phase-05--build-and-deploy-the-api-gateway)
9. [Phase 05 — Set env vars on serving endpoint](#9-phase-05--set-env-vars-on-serving-endpoint)
10. [Phase 05 — Seed gold tables](#10-phase-05--seed-gold-tables)
11. [Verify end-to-end](#11-verify-end-to-end)
12. [Known gotchas](#12-known-gotchas)
13. [Teardown](#13-teardown)

---

## 1. What you need before you start

| Tool | Version | How to install |
|---|---|---|
| Azure CLI | >= 2.60 | `brew install azure-cli` or <https://docs.microsoft.com/en-us/cli/azure/install-azure-cli> |
| Terraform | >= 1.7.0 | `brew install terraform` or <https://developer.hashicorp.com/terraform/install> |
| Python | 3.11 | `pyenv install 3.11` |
| Poetry | >= 1.8 | `pip install poetry` |
| Git | any | comes with OS |

**Azure requirements:**
- An Azure subscription where you have **Contributor** role on the subscription (not just on a resource group)
- You must be able to create a Databricks workspace — some subscriptions require a quota request first

**Databricks requirements:**
- A Databricks workspace on Azure (Premium tier — required for Unity Catalog and Vector Search)
- Unity Catalog metastore attached to the workspace

**What you do NOT need:**
- Docker installed locally (builds run on Azure Container Registry)
- A running cluster before Terraform — clusters are created in the notebooks

---

## 2. Phase 00 — Clone the repo and install tools

```bash
git clone <https://github.com/ktnsh24/shopstream-databricks-ai-platform.git>
cd shopstream-databricks-ai-platform

# Install Python dependencies
poetry install

# Log in to Azure
az login
az account set --subscription "<your-subscription-id>"

```

Verify:

```bash
az account show --query "{name:name, id:id}" -o table
terraform version
python --version  # should be 3.11.x

```

---

## 3. Phase 01 — Create Azure resources with Terraform

Terraform creates: Key Vault, ADLS Gen2 storage, Azure Container Registry, Container App Environment, managed identity, and networking.

**Step 1 — Create the resource group manually (Terraform does not create it):**

```bash
az group create \
  --name shopstream-databricks-ai-platform-rg \
  --location westeurope

```

**Step 2 — Initialise Terraform:**

```bash
cd terraform/azure
terraform init

```

**Step 3 — Apply. You must pass `databricks_host` and `databricks_token` as vars:**

```bash
terraform apply \
  -var="databricks_host=<https://<your-workspace>>.azuredatabricks.net" \
  -var="databricks_token=<your-databricks-pat>"

```

When prompted `Do you want to perform these actions?` type `yes`.

**What Terraform creates:**

| Resource | Name pattern | Notes |
|---|---|---|
| Key Vault | `helix-kv-<suffix>` | Suffix is random 6 chars, set on first apply |
| Storage account | `helixdata<suffix>` | ADLS Gen2, holds raw data |
| Container Registry | `helixacr<suffix>` | Used to build and store API Gateway image |
| Container App Environment | `helix-cae-<suffix>` | northeurope — westeurope had capacity issues |
| Container App | `helix-api` | The FastAPI gateway, min replicas = 0 |
| Managed identity | `helix-databricks-identity` | Used by Databricks to access storage |

> **Important:** Terraform state is stored locally in `terraform/azure/terraform.tfstate`. Do not delete this file. If you lose it, you will need to import all resources manually with `terraform import`. Back it up somewhere safe.

---

## 4. Phase 01 — Store secrets in Key Vault manually

Terraform creates the Key Vault but **does not** store the secrets. You must do this step manually.

Get your Key Vault name from Terraform output:

```bash
terraform output key_vault_uri
# Returns: <https://helix-kv-<suffix>>.vault.azure.net/
# Key Vault name is: helix-kv-<suffix>

```

Store the Databricks host and token (strip any `\r` if pasting from Windows):

```bash
KV_NAME="helix-kv-<suffix>"   # replace with your actual name
DATABRICKS_HOST="<https://<your-workspace>>.azuredatabricks.net"
DATABRICKS_TOKEN="<your-pat>"

az keyvault secret set --vault-name "$KV_NAME" --name databricks-host --value "$DATABRICKS_HOST"
az keyvault secret set --vault-name "$KV_NAME" --name databricks-token --value "$DATABRICKS_TOKEN"

```

**Windows users:** if you paste a token from the Databricks UI into a Windows terminal, it often has a trailing `\r` character. This causes 401 errors that are very hard to debug. Always strip it:

```bash
CLEAN_TOKEN=$(echo "$DATABRICKS_TOKEN" | tr -d '\r')
az keyvault secret set --vault-name "$KV_NAME" --name databricks-token --value "$CLEAN_TOKEN"
```

---

## 5. Phase 01 — Create Databricks workspace manually

Terraform does **not** create the Databricks workspace itself — it is created manually in the Azure Portal and then referenced by name.

**Step 1 — Create workspace in Azure Portal:**
1. Go to Azure Portal → Create a resource → Azure Databricks
2. Name: `helix-databricks`
3. Resource group: `shopstream-databricks-ai-platform-rg`
4. Region: `westeurope`
5. Pricing tier: **Premium** (required for Unity Catalog)
6. Click Create

**Step 2 — Attach Unity Catalog metastore:**
1. Go to Databricks → Account Console (accounts.azuredatabricks.net)
2. Catalog → Metastores → Assign to workspace `helix-databricks`

**Step 3 — Create the Unity Catalog and schema:**

In a Databricks notebook:

```sql
CREATE CATALOG IF NOT EXISTS helix_databricks;
CREATE SCHEMA IF NOT EXISTS helix_databricks.default;

```

**Step 4 — Create a SQL Warehouse:**
1. Databricks → SQL → SQL Warehouses → Create Warehouse
2. Name: `helix-warehouse`
3. Size: Small (2 DBU) — enough for the agent's SQL tool
4. Auto-stop: 10 minutes

**Step 5 — Generate a Personal Access Token:**
1. Databricks → top-right user menu → Settings → Developer → Access Tokens → Generate new token
2. Name: `helix-api`
3. Copy the token immediately — you cannot retrieve it again

---

## 6. Phase 04 — Run AI platform notebooks in order

Upload the notebooks to Databricks Repos or run them in the workspace. They must run **in this exact order**:

| Order | Notebook | What it does |
|---|---|---|
| 1 | `ai_platform/rag/ingest_documents.py` | Loads policy documents into `document_chunks` table |
| 2 | `ai_platform/rag/vector_search_index.py` | Creates Vector Search endpoint + index on `document_chunks` |
| 3 | `ai_platform/agents/agent_pyfunc.py` | Registers the agent to Unity Catalog + sets `@champion` alias |
| 4 | `ai_platform/evaluation/golden_dataset.py` | Creates 15 Q&A pairs in `golden_dataset` table |

**How to sync notebooks to Databricks:**
1. Databricks → Repos → Add Repo → paste your GitHub repo URL
2. Open each notebook in the order above
3. **Always use Run All** — never run individual cells after `restartPython()` or you will hit `NameError`

**Vector Search requirements:**
- Vector Search endpoint `helix-vs-endpoint` must be in `ONLINE` state before running `agent_pyfunc.py`
- Check status: Databricks → Compute → Vector Search

---

## 7. Phase 04 — Register model and start serving endpoint

After `agent_pyfunc.py` runs successfully, the model is in Unity Catalog. Now start Model Serving.

**Step 1 — Create the serving endpoint:**
1. Databricks → Serving → Create serving endpoint
2. Name: `helix-shopstream-agent`
3. Model: `helix_databricks.default.helix-shopstream-agent`
4. Version: latest (whatever was just registered)
5. Scale to zero: **enabled**

**Step 2 — Set environment variables on the endpoint** (critical — without these the agent cannot call the LLM):

```bash
DATABRICKS_HOST_BARE="<your-workspace>.azuredatabricks.net"   # NO https:// prefix
DATABRICKS_TOKEN="<your-pat>"
ENDPOINT_URL="<https://<your-workspace>>.azuredatabricks.net"

curl -X PUT "$ENDPOINT_URL/api/2.0/serving-endpoints/helix-shopstream-agent/config" \
  -H "Authorization: Bearer $DATABRICKS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"served_models\": [{
      \"model_name\": \"helix_databricks.default.helix-shopstream-agent\",
      \"model_version\": \"1\",
      \"workload_size\": \"Small\",
      \"scale_to_zero_enabled\": true,
      \"environment_vars\": {
        \"DATABRICKS_TOKEN\": \"$DATABRICKS_TOKEN\",
        \"DATABRICKS_HOST\": \"$DATABRICKS_HOST_BARE\"
      }
    }]
  }"

```

> **Why the bare hostname (no `https://`):** The agent code calls `f"<https://{host}/serving-endpoints">`. If `host` already contains `https://`, the URL becomes `https://<https://...>` and every LLM call returns a connection error.

Wait for status `READY` (5–10 minutes) before proceeding.

---

## 8. Phase 05 — Build and deploy the API Gateway

The API Gateway is a FastAPI app running in Azure Container Apps. It is built using ACR Tasks (no local Docker required).

**Step 1 — Get the ACR name:**

```bash
cd terraform/azure
terraform output  # look for container_registry_name or check Azure Portal
# ACR name is: helixacr<suffix>

```

**Step 2 — Build the image on ACR:**

```bash
cd shopstream-databricks-ai-platform

az acr build \
  --registry helixacr<suffix> \
  --image helix-api:latest \
  --file api_gateway/Dockerfile \
  --no-logs \
  api_gateway/

```

This takes 3–5 minutes.

**Step 3 — Set env vars on the Container App:**

```bash
az containerapp update \
  --name helix-api \
  --resource-group shopstream-databricks-ai-platform-rg \
  --set-env-vars \
    "DATABRICKS_HOST=<https://<your-workspace>>.azuredatabricks.net" \
    "DATABRICKS_TOKEN=<your-pat>"

```

**Step 4 — Force a new revision to pick up the new image:**

```bash
az containerapp update \
  --name helix-api \
  --resource-group shopstream-databricks-ai-platform-rg \
  --image helixacr<suffix>.azurecr.io/helix-api:latest \
  --revision-suffix "v$(date +%Y%m%d%H%M)"

```

**Step 5 — Get the app URL:**

```bash
az containerapp show \
  --name helix-api \
  --resource-group shopstream-databricks-ai-platform-rg \
  --query "properties.configuration.ingress.fqdn" -o tsv
# Returns something like: helix-api.niceriver-123f976f.northeurope.azurecontainerapps.io

```

---

## 9. Phase 05 — Set env vars on serving endpoint

This was already covered in step 7. If you need to update the token (e.g. after rotation), re-run the `curl -X PUT` command with the new token and wait for the endpoint to cycle back to `READY`.

---

## 10. Phase 05 — Seed gold tables

The data pipelines (Phase 02) are not built yet. Until they are, the agent needs data to query. Run this in a Databricks notebook to seed the three gold tables:

```python
from pyspark.sql import SparkSession
from datetime import date, timedelta
import random

spark = SparkSession.builder.getOrCreate()
today = date.today()

# revenue_daily — must have column order_date (not "date")
rows = [(str(today - timedelta(days=i)), round(random.uniform(8000, 25000), 2), random.randint(40, 200))
        for i in range(1, 31)]
spark.createDataFrame(rows, ["order_date", "total_revenue", "order_count"]) \
    .write.format("delta").mode("overwrite").saveAsTable("helix_databricks.default.revenue_daily")

# product_performance
products = ["Laptop", "Headphones", "Phone Case", "USB Hub", "Webcam"]
prod_rows = [(p, random.randint(10, 300), round(random.uniform(500, 15000), 2), str(today))
             for p in products]
spark.createDataFrame(prod_rows, ["product_name", "units_sold", "total_revenue", "snapshot_date"]) \
    .write.format("delta").mode("overwrite").saveAsTable("helix_databricks.default.product_performance")

# customer_metrics
segments = ["HIGH", "MEDIUM", "LOW"]
cust_rows = [(s, random.randint(100, 2000), round(random.uniform(0.1, 0.9), 3)) for s in segments]
spark.createDataFrame(cust_rows, ["churn_risk_segment", "customer_count", "predicted_churn_prob"]) \
    .write.format("delta").mode("overwrite").saveAsTable("helix_databricks.default.customer_metrics")

print("Done")

```

If you get a schema mismatch error, the table already exists with different columns. Drop it first:

```sql
DROP TABLE IF EXISTS helix_databricks.default.revenue_daily;
DROP TABLE IF EXISTS helix_databricks.default.product_performance;
DROP TABLE IF EXISTS helix_databricks.default.customer_metrics;
```

Then re-run the seed script.

---

## 11. Verify end-to-end

Replace `<your-app-url>` with the URL from step 8.

```bash
# Health check
curl -s "<https://<your-app-url>>/health"
# Expected: {"status": "ok", ...}

# Ask the agent a revenue question
curl -s -X POST "<https://<your-app-url>>/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "What was total revenue last 7 days?"}' | python3 -c "
import sys, json
print(json.loads(sys.stdin.read()).get('answer', ''))
"
# Expected: a sentence with actual euro amounts from the seeded data

```

---

## 12. Known gotchas

| Problem | Symptom | Fix |
|---|---|---|
| `\r` in secrets | 401 Unauthorized from Databricks | `echo "$TOKEN" \| tr -d '\r'` before storing |
| `gatekeeper unavailable` | Agent answers but can't classify questions | `DATABRICKS_HOST` on the serving endpoint has `https://` prefix — must be bare hostname |
| `NameError: _make_client` | Databricks notebook | You ran cells out of order after a `restartPython()`. Use **Run All** only |
| `FileNotFoundError: shopstream_agent_model.py` | During `agent_pyfunc.py` Run All | Repo is not synced in Databricks Repos. Go to Repos → Pull |
| Schema mismatch on seed script | Delta write error | Table was created earlier with different columns. Drop it first (see step 10) |
| Container App still running old code after `az acr build` | Old revision active | Use `--revision-suffix` flag to force a new revision (see step 8 step 4) |
| westeurope capacity error during Terraform | `Quota exceeded` | Override location to `northeurope`: `terraform apply -var="location=northeurope"` |
| Serving endpoint stays in `Updating` for >15 min | Databricks | Usually a cold-start timeout. Check Databricks Events log for the endpoint |

---

## 13. Teardown

To destroy all Azure resources (e.g. to stop all costs):

```bash
cd terraform/azure

terraform destroy \
  -var="databricks_host=<https://<your-workspace>>.azuredatabricks.net" \
  -var="databricks_token=<your-pat>"

```

To delete only the resource group (faster, removes everything including non-Terraform resources):

```bash
az group delete \
  --name shopstream-databricks-ai-platform-rg \
  --yes --no-wait

```

> Deleting the resource group does not delete the Databricks workspace itself if it was created in a separate managed resource group (Databricks creates its own `databricks-rg-*` resource group). Delete that separately if needed.
