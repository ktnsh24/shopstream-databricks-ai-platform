# Databricks notebook source

# COMMAND ----------
# MAGIC %md
# MAGIC # ShopStream — Agent Evaluation with MLflow
# MAGIC
# MAGIC **What this notebook does:**
# MAGIC 1. Loads the 15-row golden dataset from Unity Catalog
# MAGIC 2. Runs the `@champion` agent model against every question
# MAGIC 3. Scores each answer using two methods:
# MAGIC    - **Keyword check** — does the answer contain the expected keywords? (rule-based, free)
# MAGIC    - **LLM-as-judge** — does the answer correctly address the question? (uses LLM, costs tokens)
# MAGIC 4. Logs all results to an MLflow experiment
# MAGIC 5. Prints a pass/fail summary
# MAGIC
# MAGIC **Prerequisites:**
# MAGIC - `golden_dataset.py` has been run (golden_dataset table exists)
# MAGIC - `agent_pyfunc.py` has been run (`@champion` agent is registered)

# COMMAND ----------

%pip install --quiet openai lightgbm

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

import mlflow
import pandas as pd
from openai import OpenAI
import os
import importlib.util as _ilu
import pathlib as _pathlib
import glob as _glob
import subprocess as _sp

# COMMAND ----------

CATALOG = "helix_databricks"
DATABASE = "default"
GOLDEN_TABLE = f"{CATALOG}.{DATABASE}.golden_dataset"
AGENT_MODEL_NAME = f"{CATALOG}.{DATABASE}.helix-shopstream-agent"
JUDGE_MODEL = "databricks-meta-llama-3-3-70b-instruct"
EXPERIMENT_NAME = "/helix/agent-evaluation"

# Databricks requires experiment paths to be under /Users/{username}/ unless the
# parent folder already exists. Derive the username at runtime and use that as prefix.
try:
    _username = spark.sql("SELECT current_user()").collect()[0][0]  # noqa: F821
    EXPERIMENT_NAME = f"/Users/{_username}/helix/agent-evaluation"
except Exception:
    pass  # fallback to /helix/agent-evaluation if spark not available

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 1: Load golden dataset

# COMMAND ----------

golden_df = spark.table(GOLDEN_TABLE).toPandas()
print(f"Loaded {len(golden_df)} golden Q&A pairs")
print(golden_df[["question_id", "category", "question"]].to_string(index=False))

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 2: Load the @champion agent and run inference

# COMMAND ----------

mlflow.set_registry_uri("databricks-uc")

# Load ShopStreamAgent directly from the committed source file — no MLflow schema enforcement.
def _find_model_file() -> str:
    try:
        _nb_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()  # noqa: F821
        for _pfx in ("/Workspace", ""):
            _c = _pathlib.Path(_pfx + _nb_path).parent.parent / "agents" / "shopstream_agent_model.py"
            if _c.exists():
                return str(_c)
    except Exception:
        pass
    for _root in ("/Workspace", "/Repos"):
        _hits = _glob.glob(f"{_root}/**/shopstream_agent_model.py", recursive=True)
        if _hits:
            return _hits[0]
    try:
        _r = _sp.run(["find", "/Workspace", "/Repos", "-name", "shopstream_agent_model.py"],
                     capture_output=True, text=True, timeout=20)
        _lines = [l.strip() for l in _r.stdout.splitlines() if l.strip()]
        if _lines:
            return _lines[0]
    except Exception:
        pass
    raise FileNotFoundError("shopstream_agent_model.py not found. Sync the repo in Databricks Repos.")

_model_file = _find_model_file()
_spec = _ilu.spec_from_file_location("shopstream_agent_model", _model_file)
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
agent = _mod.ShopStreamAgent()
print(f"Loaded ShopStreamAgent from: {_model_file}")

input_df = pd.DataFrame({"question": golden_df["question"].astype(str).tolist()})
predictions = agent.predict(None, input_df)
golden_df["agent_answer"] = predictions["answer"].tolist()

print("Agent responses collected.")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 3: Keyword-based scoring (rule-based, free)
# MAGIC
# MAGIC For each question, the golden dataset has `expected_answer_keywords` —
# MAGIC a space-separated list of words that must appear in a correct answer.
# MAGIC This is cheap: just a string contains check, no LLM call.

# COMMAND ----------

def keyword_score(answer: str, keywords_str: str) -> float:
    """1.0 if ALL keywords present (case-insensitive), 0.0 otherwise."""
    if not keywords_str:
        return 1.0
    answer_lower = answer.lower()
    keywords = keywords_str.lower().split()
    return 1.0 if all(k in answer_lower for k in keywords) else 0.0

golden_df["keyword_pass"] = golden_df.apply(
    lambda row: keyword_score(row["agent_answer"], row["expected_answer_keywords"]),
    axis=1,
)
keyword_pass_rate = golden_df["keyword_pass"].mean()
print(f"Keyword pass rate: {keyword_pass_rate:.0%} ({int(golden_df['keyword_pass'].sum())}/{len(golden_df)})")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 4: LLM-as-judge scoring (uses Llama 3.3 70B)
# MAGIC
# MAGIC For each Q&A pair, ask the judge LLM: "Is this answer correct?"
# MAGIC The judge scores 1 (correct), 0.5 (partially correct), or 0 (incorrect).
# MAGIC
# MAGIC 🚚 Courier analogy: the LLM judge is a senior sorter who checks whether
# MAGIC the answer was delivered to the right address — not just whether it arrived.

# COMMAND ----------

def llm_judge_score(question: str, answer: str, client: OpenAI) -> tuple[float, str]:
    """Ask the judge LLM to score the answer. Returns (score, reasoning)."""
    judge_prompt = f"""You are evaluating an AI assistant's answer to a business question.

Question: {question}

Answer given: {answer}

Score the answer:
- 1.0 = Correct and complete. The answer directly addresses the question with relevant data or information.
- 0.5 = Partially correct. The answer is on-topic but missing key information or has minor errors.
- 0.0 = Incorrect or off-topic. The answer does not address the question or is wrong.

Respond with EXACTLY this format and nothing else:
SCORE: <0.0 or 0.5 or 1.0>
REASON: <one sentence>"""

    try:
        response = client.chat.completions.create(
            model=JUDGE_MODEL,
            messages=[{"role": "user", "content": judge_prompt}],
            temperature=0,
            max_tokens=100,
        )
        text = response.choices[0].message.content.strip()
        lines = {line.split(":")[0].strip(): line.split(":", 1)[1].strip()
                 for line in text.splitlines() if ":" in line}
        score = float(lines.get("SCORE", "0.0"))
        reason = lines.get("REASON", "")
        return score, reason
    except Exception as exc:
        return 0.0, f"Judge error: {exc}"


def _get_databricks_token() -> str:
    try:
        return dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()  # noqa: F821
    except Exception:
        token = os.environ.get("DATABRICKS_TOKEN", "")
        if not token:
            raise RuntimeError("No Databricks token found. Set DATABRICKS_TOKEN env var.")
        return token


def _get_databricks_host() -> str:
    try:
        return dbutils.notebook.entry_point.getDbutils().notebook().getContext().browserHostName().get()  # noqa: F821
    except Exception:
        return os.environ.get("DATABRICKS_HOST", "").rstrip("/")


judge_client = OpenAI(
    api_key=_get_databricks_token(),
    base_url=f"https://{_get_databricks_host()}/serving-endpoints",
)

judge_scores = []
judge_reasons = []
for _, row in golden_df.iterrows():
    score, reason = llm_judge_score(row["question"], row["agent_answer"], judge_client)
    judge_scores.append(score)
    judge_reasons.append(reason)

golden_df["judge_score"] = judge_scores
golden_df["judge_reason"] = judge_reasons
judge_avg = golden_df["judge_score"].mean()
print(f"LLM-as-judge average score: {judge_avg:.2f} / 1.0")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 5: Log results to MLflow

# COMMAND ----------

mlflow.set_experiment(EXPERIMENT_NAME)

with mlflow.start_run(run_name="agent-eval-golden-15"):
    # Log aggregate metrics
    mlflow.log_metric("keyword_pass_rate", keyword_pass_rate)
    mlflow.log_metric("judge_avg_score", judge_avg)
    mlflow.log_metric("total_questions", len(golden_df))

    # Log per-category breakdown
    for category, group in golden_df.groupby("category"):
        mlflow.log_metric(f"keyword_pass_{category}", group["keyword_pass"].mean())
        mlflow.log_metric(f"judge_score_{category}", group["judge_score"].mean())

    # Log the full results table as an artifact
    results_path = "/tmp/eval_results.csv"
    golden_df.to_csv(results_path, index=False)
    mlflow.log_artifact(results_path, "evaluation")

print(f"Results logged to MLflow experiment: {EXPERIMENT_NAME}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 6: Print pass/fail summary

# COMMAND ----------

print("\n" + "=" * 60)
print("EVALUATION SUMMARY")
print("=" * 60)
print(f"Total questions: {len(golden_df)}")
print(f"Keyword pass rate: {keyword_pass_rate:.0%}")
print(f"LLM judge avg score: {judge_avg:.2f} / 1.0")
print("\nPer-category breakdown:")
summary = golden_df.groupby("category").agg(
    questions=("question_id", "count"),
    keyword_pass=("keyword_pass", "mean"),
    judge_score=("judge_score", "mean"),
).round(2)
print(summary.to_string())

print("\nFailed questions (keyword check):")
failed = golden_df[golden_df["keyword_pass"] == 0.0][["question_id", "question", "agent_answer", "judge_reason"]]
if failed.empty:
    print("  None — all questions passed keyword check!")
else:
    for _, row in failed.iterrows():
        print(f"\n  [{row['question_id']}] {row['question']}")
        print(f"  Answer: {str(row['agent_answer'])[:200]}...")
        print(f"  Judge: {row['judge_reason']}")

print("\nEvaluation complete.")
