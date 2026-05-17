# Databricks notebook source

# COMMAND ----------

%pip install --quiet mlflow openai

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------
# MAGIC %md
# MAGIC # ShopStream AI Agent — MLflow PyFunc Registration
# MAGIC
# MAGIC **What this notebook does:**
# MAGIC 1. Defines `ShopStreamAgent` as an MLflow PyFunc model — wraps the full agent loop
# MAGIC 2. Runs a local smoke test to verify it works before registering
# MAGIC 3. Registers the model to Unity Catalog: `helix_databricks.default.helix-shopstream-agent`
# MAGIC 4. Sets the `@champion` alias so Model Serving can load it
# MAGIC
# MAGIC **Prerequisites:**
# MAGIC - `embed_documents.py` complete (document_chunks table exists)
# MAGIC - `create_index.py` complete (Vector Search index is ONLINE)
# MAGIC - Both ML models (`helix-churn-prediction`, `helix-revenue-forecast`) have `@champion` alias
# MAGIC
# MAGIC **Run order for Phase 04:**
# MAGIC 1. `embed_documents.py`
# MAGIC 2. `create_index.py`
# MAGIC 3. **This notebook** (`agent_pyfunc.py`)
# MAGIC 4. `golden_dataset.py`
# MAGIC 5. `evaluator.py`

# COMMAND ----------

import json
import logging
import os
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import mlflow
import pandas as pd
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState
from databricks.sdk.service.vectorsearch import VectorIndexType
from openai import OpenAI

# COMMAND ----------

# Constants
CATALOG = "helix_databricks"
DATABASE = "default"
AGENT_MODEL_NAME = f"{CATALOG}.{DATABASE}.helix-shopstream-agent"

GATEKEEPER_MODEL = "databricks-meta-llama-3-1-8b-instruct"
MAIN_AGENT_MODEL = "databricks-meta-llama-3-3-70b-instruct"
FORECAST_MODEL_UC = f"{CATALOG}.{DATABASE}.helix-revenue-forecast"

VS_ENDPOINT = "helix-vs-endpoint"
VS_INDEX = f"{CATALOG}.{DATABASE}.document_chunks_index"

MAX_TOOL_ROUNDS = 10

logger = logging.getLogger(__name__)

# COMMAND ----------
# MAGIC %md
# MAGIC ## Steps 1–3: Tools, agent loop, and PyFunc wrapper
# MAGIC
# MAGIC All logic lives in `shopstream_agent_model.py` (already loaded above).
# MAGIC Import directly from there — no duplication.

# COMMAND ----------
# NOTE: _agent_module is loaded in the cell below (Step 5). Run cells top to bottom.



# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 4: Load model class from committed file
# MAGIC
# MAGIC MLflow cannot pickle a class defined in a notebook scope (cloudpickle fails).
# MAGIC The fix: `ShopStreamAgent` lives in a committed `.py` file under `ai_platform/agents/`.
# MAGIC We load it with `importlib` so the class has a real module (not `__main__`),
# MAGIC then pass an instance to `python_model` and bundle the source file via `code_paths`.

# COMMAND ----------

import importlib.util as _ilu
import pathlib as _pathlib
import glob as _glob
import subprocess as _sp

# --- Locate shopstream_agent_model.py ---
def _find_model_file() -> str:
    # Strategy 1: derive from the running notebook's workspace path (Databricks Repos)
    try:
        _nb_path = (
            dbutils.notebook.entry_point  # noqa: F821
            .getDbutils().notebook().getContext().notebookPath().get()
        )
        print(f"[DEBUG] notebookPath = {_nb_path!r}")
        # notebookPath may or may not start with /Workspace
        for _pfx in ("/Workspace", ""):
            _c = _pathlib.Path(_pfx + _nb_path).parent / "shopstream_agent_model.py"
            print(f"[DEBUG]   checking {_c} — exists={_c.exists()}")
            if _c.exists():
                return str(_c)
    except Exception as _e:
        print(f"[DEBUG] notebook context error: {_e}")

    # Strategy 2: glob common Databricks workspace roots
    for _root in ("/Workspace", "/Repos"):
        _hits = _glob.glob(f"{_root}/**/shopstream_agent_model.py", recursive=True)
        if _hits:
            print(f"[DEBUG] glob found: {_hits[0]}")
            return _hits[0]

    # Strategy 3: shell find (most reliable — walks the real filesystem)
    try:
        _r = _sp.run(
            ["find", "/Workspace", "/Repos", "-name", "shopstream_agent_model.py"],
            capture_output=True, text=True, timeout=20,
        )
        _lines = [l.strip() for l in _r.stdout.splitlines() if l.strip()]
        if _lines:
            print(f"[DEBUG] shell find: {_lines[0]}")
            return _lines[0]
        print(f"[DEBUG] shell find stdout={_r.stdout!r}  stderr={_r.stderr!r}")
    except Exception as _e:
        print(f"[DEBUG] shell find error: {_e}")

    # Strategy 4: __file__ (local dev / plain Python run)
    if "__file__" in dir():
        _local = _pathlib.Path(__file__).parent / "shopstream_agent_model.py"
        if _local.exists():
            return str(_local)

    raise FileNotFoundError(
        "shopstream_agent_model.py not found. Check the [DEBUG] lines above to see "
        "what paths were searched. Make sure the repo is synced in Databricks Repos."
    )

_MODEL_FILE = _find_model_file()
_spec = _ilu.spec_from_file_location("shopstream_agent_model", _MODEL_FILE)
_agent_module = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_agent_module)
ShopStreamAgentClass = _agent_module.ShopStreamAgent
print(f"Loaded ShopStreamAgent from: {_MODEL_FILE}")

# Pull helpers into local scope for smoke test cells below
_run_gatekeeper = _agent_module._run_gatekeeper
_run_agent = _agent_module._run_agent
_make_client = _agent_module._make_client

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 5: Smoke test — run the agent locally before registering

# COMMAND ----------

test_client = _make_client()

test_questions = [
    "What was total revenue last 7 days?",
    "What is the return policy for electronics?",
]

print("=== Smoke test ===")
for q in test_questions:
    allowed, reason = _run_gatekeeper(q, test_client)
    print(f"\nQ: {q}")
    print(f"Gatekeeper: {'ALLOWED' if allowed else f'BLOCKED ({reason})'}")
    if allowed:
        answer = _run_agent(q, test_client)
        print(f"Answer: {answer[:300]}...")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 6: Register to Unity Catalog and set @champion alias

# COMMAND ----------

mlflow.set_registry_uri("databricks-uc")

# COMMAND ----------
with mlflow.start_run(run_name="shopstream-agent-registration"):
    model_info = mlflow.pyfunc.log_model(
        artifact_path="agent",
        python_model=ShopStreamAgentClass(),
        code_paths=[_MODEL_FILE],
        registered_model_name=AGENT_MODEL_NAME,
        input_example=pd.DataFrame({"question": ["What was total revenue last 7 days?"]}),
    )

print(f"Model registered: {model_info.model_uri}")

# Set @champion alias on the latest version
client_mlflow = mlflow.tracking.MlflowClient()
versions = client_mlflow.search_model_versions(f"name='{AGENT_MODEL_NAME}'")
latest = max(versions, key=lambda v: int(v.version))
client_mlflow.set_registered_model_alias(AGENT_MODEL_NAME, alias="champion", version=latest.version)

print(f"@champion alias set on version {latest.version}")
print(f"\nDone. Run golden_dataset.py next to create the evaluation dataset.")
