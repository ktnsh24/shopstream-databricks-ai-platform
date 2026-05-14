# ShopStream Databricks AI Platform Labs (AI-01 to AI-10)

## Table of Contents

- [AI-01 Broken Retrieval Index](#lab-ai-01-broken-retrieval-index-recovery)
- [AI-02 Text-to-SQL Hallucination](#lab-ai-02-text-to-sql-hallucination-recovery)
- [AI-03 Multi-Tool Agent Misrouting](#lab-ai-03-multi-tool-agent-misrouting-recovery)
- [AI-04 Rule-Based Evaluator Blind Spots](#lab-ai-04-rule-based-evaluator-blind-spots-recovery)
- [AI-05 LLM-as-Judge Drift](#lab-ai-05-llm-as-judge-drift-recovery)
- [AI-06 MLflow Tracing — Black Box to Waterfall](#lab-ai-06-mlflow-tracing--black-box-to-waterfall)
- [AI-07 RAG Evaluation with mlflow.genai.evaluate()](#lab-ai-07-rag-evaluation-with-mlflowgenaievaluate)
- [AI-08 Chunk Size and Overlap Tuning](#lab-ai-08-chunk-size-and-overlap-tuning)
- [AI-09 Embedding Model Comparison](#lab-ai-09-embedding-model-comparison)
- [AI-10 Retrieval K and Score Threshold Tuning](#lab-ai-10-retrieval-k-and-score-threshold-tuning)

---

## Lab AI-01: Broken Retrieval Index Recovery

| Duration | Databricks Feature | Azure Feature | Estimated Cost | Prerequisites |
|---|---|---|---|---|
| 50 min | Vector Search | ADLS Gen2 | ~EUR 1.50 | ML track complete |

**Start With Failure**

Ingest docs but leave index unsynced after Delta updates.

**Failure Signals**

- Relevant docs not returned.
- Retrieval recall drops sharply.

**Guided Fix Path**

1. Force index sync.
2. Verify embedding dimensions and chunk metadata.
3. Re-test retrieval quality.

**Compare Before vs After**

| Metric | Before | After |
|---|---:|---:|
| Retrieval recall@k | Low | Higher |
| Empty context answers | Frequent | Rare |

**What You'll Learn**

Vector index sync is like DE index maintenance after large table updates.

**Courier Analogy**

The locker map was not refreshed after new parcels arrived, so pickers searched the wrong shelves.

**Steps**

1. Run document ingest notebook.
2. Query retrieval with known questions.
3. Trigger index sync.
4. Re-run retrieval checks.

**Config Knobs**

| Variable | Default | What changing it does |
|---|---|---|
| VECTOR_INDEX_SYNC_MODE | manual | Controls index freshness behavior |

**Results Table**

| Metric | Before | After | Interpretation |
|---|---:|---:|---|
| Context relevance | Poor | Better | Index freshness fixed |

**What We Learned**

Most "LLM quality" issues in RAG are retrieval freshness issues.

---

## Lab AI-02: Text-to-SQL Hallucination Recovery

| Duration | Databricks Feature | Azure Feature | Estimated Cost | Prerequisites |
|---|---|---|---|---|
| 45 min | Foundation Model API + UC schema grounding | SQL Warehouse | ~EUR 1.00 | AI-01 |

**Start With Failure**

Ask business questions with insufficient schema grounding in prompt context.

**Failure Signals**

- Generated SQL references non-existent columns.
- Query execution fails or returns nonsense.

**Guided Fix Path**

1. Inject explicit allowed table/column context.
2. Add SQL validation layer before execution.
3. Re-run same questions and compare execution pass rate.

**Compare Before vs After**

| Metric | Before | After |
|---|---:|---:|
| SQL execution pass rate | Low | High |
| Invalid column errors | High | Lower |

**What You'll Learn**

Grounded text-to-SQL is like strict semantic-layer modeling in BI tools.

**Courier Analogy**

The dispatcher guessed shelf names; giving a real depot map stopped wrong pickup instructions.

**Steps**

1. Use Swagger UI: POST ask endpoint with SQL question.
2. Capture failed SQL.
3. Enable schema grounding + validation.
4. Retry and confirm executable SQL.

**Config Knobs**

| Variable | Default | What changing it does |
|---|---|---|
| SQL_SCHEMA_GROUNDING | false | Adds strict schema context |
| SQL_VALIDATE_BEFORE_RUN | false | Blocks invalid SQL execution |

**Results Table**

| Metric | Before | After | Interpretation |
|---|---:|---:|---|
| Hallucinated SQL rate | High | Lower | Better grounding |

**What We Learned**

Text-to-SQL needs guardrails. Prompt quality alone is not enough for production reliability.

---

## Lab AI-03: Multi-Tool Agent Misrouting Recovery

| Duration | Databricks Feature | Azure Feature | Estimated Cost | Prerequisites |
|---|---|---|---|---|
| 60 min | Agent Framework tools | SQL + Vector services | ~EUR 1.50 | AI-02 |

**Start With Failure**

Agent sends all questions to one tool regardless of intent.

**Failure Signals**

- Low-quality answers for mixed analytics+policy questions.
- Tool call traces show missing multi-step plan.

**Guided Fix Path**

1. Tighten tool-selection prompt/instructions.
2. Add routing rule checks.
3. Validate multi-tool traces for complex prompts.

**Compare Before vs After**

| Metric | Before | After |
|---|---:|---:|
| Single-tool overuse | High | Lower |
| Multi-hop answer quality | Low | Higher |

**What You'll Learn**

Agent routing errors are like DAG dependency errors where one task is overused and others are skipped.

**Courier Analogy**

Every parcel was sent to the same sorting lane, even when some needed customs and others needed cold-chain.

**Steps**

1. Use Swagger UI: ask a multi-source question.
2. Inspect tool trace metadata.
3. Update tool routing guidance.
4. Re-test and verify multiple tools were used.

**Config Knobs**

| Variable | Default | What changing it does |
|---|---|---|
| TOOL_ROUTING_STRICT_MODE | false | Enforces intent-to-tool constraints |

**Results Table**

| Metric | Before | After | Interpretation |
|---|---:|---:|---|
| Correct tool sequence rate | Low | Higher | Routing quality improved |

**What We Learned**

Agents are orchestration systems. Reliability comes from routing rules + observability, not model size.

---

## Lab AI-04: Rule-Based Evaluator Blind Spots Recovery

| Duration | Databricks Feature | Azure Feature | Estimated Cost | Prerequisites |
|---|---|---|---|---|
| 40 min | MLflow Evaluate rule mode | Evaluation dataset | ~EUR 0.50 | AI-03 |

**Start With Failure**

Use only lexical overlap metrics for answer quality.

**Failure Signals**

- Good paraphrases scored too low.
- Some wrong but keyword-heavy answers score too high.

**Guided Fix Path**

1. Keep rule-based lane as baseline.
2. Add retrieval and faithfulness sub-metrics.
3. Flag disagreement cases for manual review.

**Compare Before vs After**

| Metric | Before | After |
|---|---:|---:|
| False negatives | High | Lower |
| False positives | High | Lower |

**What You'll Learn**

This mirrors DE data quality scorecards where one metric never captures all failure modes.

**Courier Analogy**

You judged deliveries only by label text match, ignoring whether parcel contents were correct.

**Steps**

1. Run evaluator in rule mode.
2. Inspect low/high outlier cases.
3. Add secondary checks.
4. Re-score and compare.

**Config Knobs**

| Variable | Default | What changing it does |
|---|---|---|
| EVAL_RULE_THRESHOLD | 0.70 | Tightens/loosens pass criteria |

**Results Table**

| Metric | Before | After | Interpretation |
|---|---:|---:|---|
| Rule-only reliability | Lower | Better | Better evaluator coverage |

**What We Learned**

Rule-based evaluation is useful but incomplete. It should be treated as one lane, not the whole truth.

---

## Lab AI-05: LLM-as-Judge Drift Recovery

| Duration | Databricks Feature | Azure Feature | Estimated Cost | Prerequisites |
|---|---|---|---|---|
| 50 min | MLflow Evaluate judge mode | Foundation Model API | ~EUR 2.00 | AI-04 |

**Start With Failure**

Run judge mode with vague rubric and no calibration examples.

**Failure Signals**

- Judge scores drift between runs.
- Overly generous or harsh scoring patterns.

**Guided Fix Path**

1. Define strict rubric with examples.
2. Freeze judge prompt version.
3. Compare judge lane with rule lane and inspect disagreements.

**Compare Before vs After**

| Metric | Before | After |
|---|---:|---:|
| Judge consistency | Low | Higher |
| Agreement with manual review | Low | Higher |

**What You'll Learn**

Judge calibration is like DE metric definition governance in KPI pipelines.

**Courier Analogy**

Different supervisors graded delivery quality differently until a shared scorecard was enforced.

**Steps**

1. Run evaluator in LLM-judge mode.
2. Capture inconsistent cases.
3. Add rubric + examples.
4. Re-run and compare consistency.

**Config Knobs**

| Variable | Default | What changing it does |
|---|---|---|
| EVAL_MODE | rule_based | Switches to llm_judge or combined |
| JUDGE_RUBRIC_VERSION | v1 | Keeps scoring criteria stable |

**Results Table**

| Metric | Before | After | Interpretation |
|---|---:|---:|---|
| Score stability | Weak | Better | Judge now calibrated |

**What We Learned**

LLM-as-judge is powerful only with rubric discipline. Combined mode gives the most trustworthy view.

---

## Lab AI-06: MLflow Tracing — Black Box to Waterfall

| Duration | Databricks Feature | Azure Feature | Estimated Cost | Prerequisites |
|---|---|---|---|---|
| 45 min | MLflow Tracing (`@mlflow.trace`) | None | ~EUR 0.50 | AI-03 complete |

**What You'll Learn**

Without tracing, an agent question is a black box: a question goes in, an answer comes out. You cannot tell which chunks were retrieved, what the LLM was given, or how long each step took. `@mlflow.trace` decorators turn every function call into a named span that appears in MLflow's Traces UI as a waterfall diagram.

DE parallel: this is like adding `logger.info()` to every stage of a Spark job, then viewing the stage breakdown in the Spark UI. The data flows through your pipeline; tracing shows you exactly where time was spent and what data was passed.

**Start With Failure**

Run the agent without any tracing. Ask a question that returns a wrong answer.

**Failure Signals**

- You see the wrong answer but cannot tell if the problem is retrieval, the prompt, or the LLM.
- MLflow Experiments shows the run but no span details.

**Guided Fix Path**

1. Add `mlflow.openai.autolog()` at the top of `orchestrator.py`.
2. Add `@mlflow.trace(span_type="RETRIEVER")` to the `retrieve()` call in `search_documents.py`.
3. Re-run the same question.
4. Open MLflow → Experiments → your run → Traces tab — find the span that shows the wrong or missing retrieved chunks.

**Steps**

1. Open `ai_platform/agents/orchestrator.py` in a Databricks notebook.
2. Add `import mlflow` and `mlflow.openai.autolog()` before the first API call.
3. Open `ai_platform/agents/tools/search_documents.py`.
4. Add `@mlflow.trace(span_type="RETRIEVER")` on the retrieval function.
5. Ask the agent: `"What does the return policy say about electronics?"`
6. Open Databricks → Machine Learning → Experiments → your experiment → click the run → Traces.
7. Expand the waterfall. Confirm you can see: the retrieval span (which chunks were returned), the LLM span (what prompt was sent, what was returned), and the total latency per span.

**Config Knobs**

| Variable | Default | What changing it does |
|---|---|---|
| `MLFLOW_EXPERIMENT_NAME` | `/Users/.../helix-agent-eval` | Where traces are stored |

**Results Table**

| Metric | Before | After | Interpretation |
|---|---:|---:|---|
| Time to diagnose a wrong answer | Minutes to hours | Seconds | Span shows exact failure point |
| Visible spans in MLflow UI | 0 | 3+ (retrieve, LLM, tool calls) | Full waterfall visible |

**Courier Analogy**

Before tracing, you knew a parcel was lost but not which depot. The trace labels every depot handoff with a timestamp and parcel contents.

**What We Learned**

Tracing is the single cheapest improvement to agent debuggability. One `autolog()` call and one decorator give you full visibility into every agent run.

---

## Lab AI-07: RAG Evaluation with mlflow.genai.evaluate()

| Duration | Databricks Feature | Azure Feature | Estimated Cost | Prerequisites |
|---|---|---|---|---|
| 60 min | MLflow `mlflow.genai.evaluate()` + Unity Catalog eval table | None | ~EUR 2.00 | AI-06 complete, golden dataset written |

**What You'll Learn**

`mlflow.genai.evaluate()` runs a set of LLM-based judges against your agent's answers. The three judges you care most about:

- **RetrievalGroundedness** — did the answer come from retrieved chunks, or did the agent make something up? Score 0 = hallucination. Score 1 = fully grounded.
- **RelevanceToQuery** — did the answer address the question? Score 0 = off-topic. Score 1 = directly answers the question.
- **Safety** — did the answer contain harmful content? Score 0 = unsafe. Score 1 = safe.

DE parallel: this is your data quality report on the agent. `RetrievalGroundedness` is like a null-check on the output: if the answer is not grounded in data, it is fabricated and should not reach users. The golden dataset is your test suite — the same concept as `pytest` fixtures for unit tests.

**Start With Failure**

Run the agent against the golden dataset without any evaluation. Accept every answer as correct.

**Failure Signals**

- No visibility into which questions the agent answers poorly.
- No way to compare two versions of the agent.

**Guided Fix Path**

1. Run `golden_dataset.py` to write the Q&A pairs to `helix_gold.ai_platform.golden_dataset`.
2. Run `evaluator.py` to score all answers.
3. Find the rows where `RetrievalGroundedness` score < 0.5.
4. Increase `num_results` in `search_documents.py` (more context = better grounding).
5. Re-run evaluation and compare scores.

**Steps**

1. Open Databricks → Workspace → `ai_platform/evaluation/golden_dataset.py`.
2. Run `create_golden_dataset(spark)` — verify the table exists: `SELECT * FROM helix_gold.ai_platform.golden_dataset`.
3. Open `evaluator.py`. Run `run_evaluation()`.
4. Open the MLflow experiment in Databricks → Machine Learning → Experiments.
5. Click the eval run → Artifacts → `eval_results_table`.
6. Sort by `RetrievalGroundedness` score ascending — identify the worst answers.
7. For each failing row: click the trace link — inspect which chunks were retrieved.
8. Tune `num_results` in `search_documents.py` from 5 → 10. Re-run evaluation.

**Config Knobs**

| Variable | Default | What changing it does |
|---|---|---|
| `num_results` (in search_documents.py) | 5 | More chunks = better grounding, higher cost |
| `Guidelines` scorer rules | cite_source | Add custom rules per use case |

**Results Table**

| Metric | Before | After | Interpretation |
|---|---:|---:|---|
| RetrievalGroundedness avg | < 0.5 | > 0.8 | Answers grounded in retrieved data |
| RelevanceToQuery avg | Varies | > 0.8 | Answers address the question |
| Safety pass rate | Unknown | 100% | No harmful outputs |

**Courier Analogy**

The quality inspector checked 15 parcels from last week against the original manifest. Any parcel where the contents did not match the shipping note was flagged as a grounding failure.

**What We Learned**

Evaluation is the difference between a demo and a production system. `RetrievalGroundedness` is the most important metric for RAG — if the answer is not grounded in retrieved chunks, it is fabricated data and cannot be trusted.

---

## Lab AI-08: Chunk Size and Overlap Tuning

| Duration | Databricks Feature | Azure Feature | Estimated Cost | Prerequisites |
|---|---|---|---|---|
| 60 min | Vector Search + Foundation Model API | ADLS Gen2 | ~EUR 1.50 | AI-07 |

### What this lab teaches

When you embed a document, you first split it into chunks. The size of each chunk (how many tokens) and the overlap (how many tokens are shared between adjacent chunks) directly control retrieval quality.

- **Too large a chunk (e.g. 1024 tokens):** the retrieved chunk contains the answer buried inside a lot of noise. The LLM has to work harder and may miss the key sentence. Recall looks ok but answer precision drops.
- **Too small a chunk (e.g. 64 tokens):** the answer is split across multiple chunks. You retrieve half the answer in chunk 3 and the other half in chunk 7. Neither chunk alone is enough context for the LLM.
- **Zero overlap:** the boundary between chunk N and chunk N+1 can cut a sentence in half. A question about that sentence retrieves a fragment.
- **High overlap (e.g. 100 tokens):** the index grows larger, costs more to store and query, but boundary cuts disappear.

This lab makes those tradeoffs physical. You run the same 5 questions against 4 different chunk configurations and record what changes.

### Step 1 — Set your baseline config

Open `.env` (or the environment config for the AI platform) and set:

```bash
RAG_CHUNK_SIZE=512
RAG_CHUNK_OVERLAP=50
```

Re-ingest the ShopStream product documentation:

```bash
# From the repo root
python scripts/ingest_documents.py --source data/product_docs/
```

Wait for the Vector Search index to sync. In the Databricks workspace: **Catalog** → **helix_gold** → **ai_platform** → **product_docs_index** → confirm `Status = Online`.

### Step 2 — Run your 5 test questions

Use the same 5 questions for every experiment. Write them down now — do not change them between runs.

Suggested questions for ShopStream:

1. "What is the return policy for electronics?"
2. "How long does standard shipping take to Amsterdam?"
3. "What payment methods are accepted at checkout?"
4. "Can I cancel an order after it has been dispatched?"
5. "What is the warranty period for ShopStream branded products?"

For each question, call the RAG endpoint via Swagger UI (`POST /api/v1/chat`) and record:

- Did the answer cite a specific policy or did it say "I don't have that information"?
- Did the answer contain a specific number (days, %, etc.) or was it vague?
- Rate the answer: 1 (wrong/vague), 2 (partial), 3 (correct and specific)

### Step 3 — Change chunk size to 1024, re-ingest, re-run

```bash
RAG_CHUNK_SIZE=1024
RAG_CHUNK_OVERLAP=50
python scripts/ingest_documents.py --source data/product_docs/
```

Wait for index sync. Run the same 5 questions. Record scores.

### Step 4 — Change chunk size to 256, re-ingest, re-run

```bash
RAG_CHUNK_SIZE=256
RAG_CHUNK_OVERLAP=50
python scripts/ingest_documents.py --source data/product_docs/
```

Run and record.

### Step 5 — Test overlap effect: zero overlap

```bash
RAG_CHUNK_SIZE=256
RAG_CHUNK_OVERLAP=0
python scripts/ingest_documents.py --source data/product_docs/
```

Run and record. Look specifically at Q4 (cancel after dispatch) — does the policy get cut mid-sentence?

### Results Table

Fill in your own scores as you run:

| Config | Q1 score | Q2 score | Q3 score | Q4 score | Q5 score | Total /15 |
|---|---|---|---|---|---|---|
| chunk=512, overlap=50 | | | | | | |
| chunk=1024, overlap=50 | | | | | | |
| chunk=256, overlap=50 | | | | | | |
| chunk=256, overlap=0 | | | | | | |

### What to look for

- **The config with the highest total score** is your best starting point for production.
- **Q4 with overlap=0** usually shows a drop — the cancellation policy is typically a multi-sentence rule that gets cut.
- **chunk=1024** often scores ok on simple questions but poorly on precise ones (warranty period, exact shipping days) because the answer is buried in noise.
- **chunk=256 with overlap=50** is the typical winner for product documentation.

### Config Knobs

| Variable | Values tried | Effect |
|---|---|---|
| `RAG_CHUNK_SIZE` | 256 / 512 / 1024 | Smaller = more precise retrieval, larger = more context per chunk |
| `RAG_CHUNK_OVERLAP` | 0 / 50 | Overlap prevents boundary cuts; 0 is cheaper but riskier |

### Courier Analogy

Chunking is like dividing a 100-page depot manual into sections for new staff. If each section is 80 pages (chunk=1024), the new staff member finds the answer eventually but has to read a lot of noise first. If each section is 2 pages (chunk=64), the answer about cancellation policy is split across section 12 and section 13 — neither section alone is useful. The right section size is the one where the answer fits completely in one section with a bit of surrounding context.

### What We Learned

Chunk size is the single highest-impact tuning knob in a RAG system. Most teams set it once and never revisit it. After this lab you will have a real number — based on your actual documents and actual questions — not a default from a tutorial.

---

## Lab AI-09: Embedding Model Comparison

| Duration | Databricks Feature | Azure Feature | Estimated Cost | Prerequisites |
|---|---|---|---|---|
| 45 min | Vector Search + Foundation Model API | ADLS Gen2 | ~EUR 1.00 | AI-08 |

### What this lab teaches

The embedding model converts a chunk of text into a vector of numbers. Two different embedding models produce different vectors for the same text — which means they have different ideas of what "similar" means. This directly controls which chunks get retrieved for a given question.

Databricks gives you access to multiple embedding models via the Foundation Model API. This lab compares two of them on the same questions and documents.

### Step 1 — Ingest with the default embedding model

The default in this platform is `databricks-gte-large-en`. Make sure your `.env` has:

```bash
EMBEDDING_MODEL=databricks-gte-large-en
RAG_CHUNK_SIZE=256
RAG_CHUNK_OVERLAP=50
```

Re-ingest:

```bash
python scripts/ingest_documents.py --source data/product_docs/
```

Run the same 5 questions from AI-08. Record retrieval scores.

### Step 2 — Switch to a smaller embedding model

Change to `databricks-bge-large-en` (faster, smaller):

```bash
EMBEDDING_MODEL=databricks-bge-large-en
```

Re-ingest and re-run the same 5 questions. Record.

### Step 3 — Compare results

| Config | Q1 | Q2 | Q3 | Q4 | Q5 | Total /15 | Avg latency (ms) |
|---|---|---|---|---|---|---|---|
| gte-large-en | | | | | | | |
| bge-large-en | | | | | | | |

### What to look for

- **Quality difference:** which model retrieves the right chunk more often?
- **Latency difference:** check the Inference Tables log. Is one model noticeably slower per embed call?
- **Cost difference:** `gte-large-en` uses more tokens per call. Check Databricks usage dashboard.

The right embedding model is the one with the best quality/cost/latency tradeoff for your specific documents and questions.

### Config Knobs

| Variable | Values tried | Effect |
|---|---|---|
| `EMBEDDING_MODEL` | gte-large-en / bge-large-en | Changing this means re-ingesting everything — vectors are not compatible across models |

### Courier Analogy

Two depot GPS systems produce location codes for the same address using different coordinate formats. A parcel labelled with GPS system A cannot be found by a picker using GPS system B. When you change embedding models, you must re-label every parcel (re-ingest) because the coordinate space has changed.

### What We Learned

You cannot mix embedding models. A model change = full re-ingest. Run this lab before you have millions of documents in production, not after. The quality difference between models is real but often smaller than the chunk size effect from AI-08.

---

## Lab AI-10: Retrieval K and Score Threshold Tuning

| Duration | Databricks Feature | Azure Feature | Estimated Cost | Prerequisites |
|---|---|---|---|---|
| 45 min | Vector Search + Foundation Model API | ADLS Gen2 | ~EUR 0.75 | AI-09 |

### What this lab teaches

After chunking and embedding, the retrieval step selects the **top K** most similar chunks to pass to the LLM. K is a number you control. So is the **score threshold** — the minimum similarity score a chunk must have to be included at all.

- **K too low (e.g. K=1):** you pass the single best chunk. If the answer requires two sections of the policy (step 1 and step 2 of the return process), you only get one.
- **K too high (e.g. K=20):** you pass 20 chunks. Most are noise. The LLM context window fills up. The LLM has to search through noise to find the answer, and precision drops.
- **No score threshold:** you always pass K chunks even if the best match has similarity score 0.3 — meaning it is probably irrelevant. The LLM gets a bad context and hallucinates.
- **Threshold too high:** you pass zero chunks for unusual questions, and the LLM says "I don't have that information" even when the document exists.

### Step 1 — Baseline: K=5, no threshold

Set in your config:

```bash
RAG_NUM_RESULTS=5
RAG_SCORE_THRESHOLD=0.0
```

Run the 5 questions. Record scores and note any "I don't have that information" responses.

### Step 2 — Lower K to 1

```bash
RAG_NUM_RESULTS=1
```

Re-run. Which questions get worse? Multi-part policy questions (like Q4, cancellation) are the ones that usually fail here because one chunk is not enough context.

### Step 3 — Raise K to 10

```bash
RAG_NUM_RESULTS=10
```

Re-run. Do answers improve, stay the same, or get worse (more noise)? Check the MLflow trace — how many tokens are in the context now?

### Step 4 — Add a score threshold

Reset K=5. Add a threshold:

```bash
RAG_NUM_RESULTS=5
RAG_SCORE_THRESHOLD=0.75
```

Re-run. Now ask a question that is clearly outside the document set: "What is the ShopStream CEO's home address?" — the system should return 0 results above the threshold and the LLM should say it does not have that information, rather than making something up.

### Results Table

| Config | Q1 | Q2 | Q3 | Q4 | Q5 | Total /15 | Hallucination on off-topic |
|---|---|---|---|---|---|---|---|
| K=5, threshold=0.0 | | | | | | | ? |
| K=1, threshold=0.0 | | | | | | | ? |
| K=10, threshold=0.0 | | | | | | | ? |
| K=5, threshold=0.75 | | | | | | | None expected |

### What to look for

- **K=1 score vs K=5 score** — the delta tells you how much the second and third chunks contribute.
- **K=10 vs K=5** — if scores are similar, the extra chunks are noise. If scores improve, the relevant content is spread across more chunks (increase K in production).
- **threshold=0.75 off-topic test** — if the model still answers with a threshold, lower the threshold is not doing its job.

### Config Knobs

| Variable | Values tried | Effect |
|---|---|---|
| `RAG_NUM_RESULTS` | 1 / 5 / 10 | How many chunks reach the LLM context window |
| `RAG_SCORE_THRESHOLD` | 0.0 / 0.75 | Minimum similarity score to include a chunk |

### Courier Analogy

K is how many parcels you pull from the locker for a customer. Pull 1 — fast, but if the order has two items you miss one. Pull 20 — slow, noisy, the customer has to sort through unrelated packages. The score threshold is the minimum match quality — if the locker scan says this parcel is only a 20% match for the customer's ID, do not give it to them. A no-threshold system hands over random parcels and hopes for the best.

### What We Learned

K and score threshold together control the quality/cost/reliability tradeoff of retrieval. K controls how much context you provide; threshold controls how much noise you filter. Running this lab before production means you have a number based on your data, not a guess.

---
