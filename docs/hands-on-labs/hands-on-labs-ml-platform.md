# Helix ML Platform Labs (ML-01 to ML-05)

## Table of Contents

- [ML-01 Feature Store Schema Mismatch](#lab-ml-01-feature-store-schema-mismatch-recovery)
- [ML-02 Unstable Training Metrics](#lab-ml-02-unstable-training-metrics-recovery)
- [ML-03 Wrong Champion Model Alias](#lab-ml-03-wrong-champion-model-alias-recovery)
- [ML-04 Model Serving Deployment Failure](#lab-ml-04-model-serving-deployment-failure-recovery)
- [ML-05 Live Prediction Feature Lookup Failure](#lab-ml-05-live-prediction-feature-lookup-failure-recovery)
- [ML-06 Inference Table Drift Detection](#lab-ml-06-inference-table-drift-detection-failure)

---

## Lab ML-01: Feature Store Schema Mismatch Recovery

| Duration | Databricks Feature | Azure Feature | Estimated Cost | Prerequisites |
|---|---|---|---|---|
| 45 min | Feature Store | ADLS Gen2 | ~EUR 0.50 | DP-01 to DP-10 complete |

**Start With Failure**

Register feature table with wrong data type for customer lifetime value.

**Failure Signals**

- Feature lookup errors during training.
- Null-heavy feature column in model input.

**Guided Fix Path**

1. Align feature schema with source Gold table.
2. Re-register feature spec.
3. Re-run feature validation checks.

**Compare Before vs After**

| Metric | Before | After |
|---|---:|---:|
| Feature null ratio | High | Low |
| Training readiness checks | Failing | Passing |

**What You'll Learn**

Feature contracts are like DE data contracts between Silver and Gold consumers.

**Courier Analogy**

The parcel weight field was stored as text, so sorting machines could not route by weight.

**Steps**

1. Run feature pipeline notebook.
2. Inspect feature schema in Databricks UI.
3. Correct type mapping.
4. Re-run and validate schema + sample rows.

**Config Knobs**

| Variable | Default | What changing it does |
|---|---|---|
| FEATURE_STRICT_SCHEMA | false | Enforces hard schema checks before register |

**Results Table**

| Metric | Before | After | Interpretation |
|---|---:|---:|---|
| Schema violations | >0 | 0 | Feature contract restored |

**What We Learned**

Most ML failures start in feature quality, not model code. Fixing schema contracts stabilizes training.

---

## Lab ML-02: Unstable Training Metrics Recovery

| Duration | Databricks Feature | Azure Feature | Estimated Cost | Prerequisites |
|---|---|---|---|---|
| 60 min | MLflow Tracking | Azure Blob artifacts | ~EUR 1.50 | ML-01 |

**Start With Failure**

Train with noisy feature set and no random seed control.

**Failure Signals**

- RMSE swings heavily run-to-run.
- No reproducible baseline in MLflow.

**Guided Fix Path**

1. Add fixed random seed.
2. Remove known noisy features.
3. Compare 3 repeated runs.

**Compare Before vs After**

| Metric | Before | After |
|---|---:|---:|
| RMSE variance | High | Lower |
| Reproducibility | Poor | Good |

**What You'll Learn**

This mirrors flaky DE jobs where non-deterministic ordering causes unstable outputs.

**Courier Analogy**

Different shift rules each day made delivery times unpredictable until route rules were standardized.

**Steps**

1. Run training notebook three times.
2. Record metrics in MLflow.
3. Apply seed + feature cleanup.
4. Re-run and compare spread.

**Config Knobs**

| Variable | Default | What changing it does |
|---|---|---|
| TRAIN_RANDOM_SEED | unset | Makes experiments reproducible |
| ENABLE_NOISY_FEATURES | true | Includes/excludes unstable predictors |

**Results Table**

| Metric | Before | After | Interpretation |
|---|---:|---:|---|
| RMSE std-dev | High | Lower | Stable training behavior |

**What We Learned**

Reproducibility is a platform requirement. MLflow only helps if runs are comparable.

---

## Lab ML-03: Wrong Champion Model Alias Recovery

| Duration | Databricks Feature | Azure Feature | Estimated Cost | Prerequisites |
|---|---|---|---|---|
| 35 min | MLflow Registry | Model registry service | ~EUR 0.25 | ML-02 |

**Start With Failure**

Alias `champion` points to older underperforming model version.

**Failure Signals**

- Production endpoint serves lower-quality predictions.
- Registry UI and expected version mismatch.

**Guided Fix Path**

1. Compare model metrics by version.
2. Move alias to best validated version.
3. Add pre-alias validation checklist.

**Compare Before vs After**

| Metric | Before | After |
|---|---:|---:|
| Champion RMSE | Worse | Better |
| Alias correctness | Wrong | Correct |

**What You'll Learn**

Registry aliasing is like DE table alias promotion (dev to prod) with validation gates.

**Courier Analogy**

The depot marked an old map as "current route"; updating the sign restored correct dispatching.

**Steps**

1. Open MLflow Registry UI.
2. Inspect version metrics.
3. Update `champion` alias.
4. Trigger quick smoke prediction.

**Config Knobs**

| Variable | Default | What changing it does |
|---|---|---|
| REQUIRE_ALIAS_GATE | false | Blocks alias updates without metric checks |

**Results Table**

| Metric | Before | After | Interpretation |
|---|---:|---:|---|
| Alias-to-best-model match | No | Yes | Promotion pipeline improved |

**What We Learned**

Model governance failures are usually metadata failures. Alias discipline prevents silent regressions.

---

## Lab ML-04: Model Serving Deployment Failure Recovery

| Duration | Databricks Feature | Azure Feature | Estimated Cost | Prerequisites |
|---|---|---|---|---|
| 50 min | Model Serving | Endpoint auth/network | ~EUR 2.00 | ML-03 |

**Start With Failure**

Deploy endpoint with missing environment variable for model dependencies.

**Failure Signals**

- Endpoint stuck in failed state.
- Health check returns model load error.

**Guided Fix Path**

1. Inspect serving build logs.
2. Add missing dependency/env var.
3. Redeploy and verify ready status.

**Compare Before vs After**

| Metric | Before | After |
|---|---:|---:|
| Deployment status | Failed | Ready |
| Health checks | Failing | Passing |

**What You'll Learn**

Serving deploy issues are equivalent to broken container builds in DE APIs.

**Courier Analogy**

Trucks were dispatched without fuel cards; adding required credentials got the fleet moving.

**Steps**

1. Deploy from Databricks serving UI.
2. Review logs for missing config.
3. Patch endpoint config.
4. Redeploy and run health check.

**Config Knobs**

| Variable | Default | What changing it does |
|---|---|---|
| SERVING_ENV_VALIDATION | false | Validates required env vars pre-deploy |

**Results Table**

| Metric | Before | After | Interpretation |
|---|---:|---:|---|
| Time to ready | Infinite | Measurable | Deploy path fixed |

**What We Learned**

Deployment reliability needs preflight checks, not trial-and-error redeploy loops.

---

## Lab ML-05: Live Prediction Feature Lookup Failure Recovery

| Duration | Databricks Feature | Azure Feature | Estimated Cost | Prerequisites |
|---|---|---|---|---|
| 45 min | Model Serving + Feature lookup | API endpoint | ~EUR 1.00 | ML-04 |

**Start With Failure**

Send prediction requests missing required entity keys.

**Failure Signals**

- 4xx/5xx prediction errors.
- Fallback defaults overused in logs.

**Guided Fix Path**

1. Validate request schema in API layer.
2. Add clear error messages for missing keys.
3. Re-test with valid payload and confirm lookup success.

**Compare Before vs After**

| Metric | Before | After |
|---|---:|---:|
| Prediction error rate | High | Low |
| Feature lookup success | Low | High |

**What You'll Learn**

Entity key integrity is the ML equivalent of primary-key integrity in star schemas.

**Courier Analogy**

Prediction requests arrived without tracking numbers; routing only works when parcel IDs are present.

**Steps**

1. Use Swagger UI: call prediction endpoint with invalid payload.
2. Inspect error response/logs.
3. Add validation in request contract.
4. Retry with valid payload.

**Config Knobs**

| Variable | Default | What changing it does |
|---|---|---|
| STRICT_ENTITY_KEY_VALIDATION | false | Rejects malformed requests early |

**Results Table**

| Metric | Before | After | Interpretation |
|---|---:|---:|---|
| Failed predictions | Many | Few | Request validation fixed |

**What We Learned**

Serving reliability comes from strong contracts at the edge, not post-failure patching deeper in the stack.

---

## Lab ML-06: Inference Table Drift Detection Failure

| Duration | Databricks Feature | Azure Feature | Estimated Cost | Prerequisites |
|---|---|---|---|---|
| 60 min | Inference Tables + Lakehouse Monitoring | None | ~EUR 1.00 | ML-01 to ML-05 complete |

**What You'll Learn**

Inference Tables are auto-created Delta tables that log every prediction from a Model Serving endpoint. They capture request, response, latency, and model version. This lab teaches you to:
- Query inference tables for latency + error trends
- Detect data drift in prediction inputs
- Compare model versions using production metrics
- Set up automated monitoring

DE parallel: Inference Tables are like ETL job output audit logs. Instead of losing predictions in logs, you get a queryable fact table with full lineage.

**Start With Failure**

Model Serving endpoint returns predictions but silently slows down. You have no idea why.

**Failure Signals**

- User-side: requests are timing out
- Logs: no errors, just slow responses
- No visibility: no audit trail of what predictions were made

**Guided Fix Path**

1. Enable Inference Table logging on the Model Serving endpoint (Databricks UI)
2. Query the inference table to find latency trend
3. Detect when degradation started (yesterday? this morning?)
4. Compare input feature distributions before/after degradation
5. Identify: changed data (drift) vs degraded model performance

**Steps**

1. In Databricks UI → AI & BI → Model Serving → Edit your endpoint → Toggle "Enable Inference Table Logging" → save
2. Wait 5 minutes for first predictions to log
3. Open a Databricks SQL notebook and run:

```sql
SELECT
  DATE(timestamp) as date,
  ROUND(AVG(latency_ms), 2) as avg_latency,
  PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) as p95_latency,
  COUNT(*) as predictions
FROM helix_gold.ml_platform.forecast_model_predictions
WHERE timestamp >= CURRENT_TIMESTAMP() - INTERVAL 24 HOUR
GROUP BY DATE(timestamp)
ORDER BY date DESC
```

4. Look for sudden latency spike. Note the exact timestamp.
5. Run drift query to see if input features changed around that time:

```sql
SELECT
  DATE_TRUNC('hour', timestamp) as hour,
  COUNT(*) as predictions,
  ROUND(AVG(CAST(features['order_amount'] as DOUBLE)), 2) as avg_order_amount,
  ROUND(AVG(CAST(features['customer_age'] as DOUBLE)), 2) as avg_customer_age
FROM helix_gold.ml_platform.forecast_model_predictions
WHERE timestamp >= CURRENT_TIMESTAMP() - INTERVAL 48 HOUR
GROUP BY DATE_TRUNC('hour', timestamp)
ORDER BY hour DESC
```

6. Compare averages from yesterday vs today. If order_amount or age shifted 10%+ → **data drift**
7. Compare model versions:

```sql
SELECT
  model_version,
  COUNT(*) as predictions,
  ROUND(AVG(latency_ms), 2) as avg_latency_ms,
  ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms), 2) as p95_latency_ms
FROM helix_gold.ml_platform.forecast_model_predictions
WHERE timestamp >= CURRENT_TIMESTAMP() - INTERVAL 24 HOUR
GROUP BY model_version
ORDER BY predictions DESC
```

8. If old version (v1) is faster than new (v2) by >20% → investigate v2 or rollback

**Config Knobs**

| Variable | Default | What changing it does |
|---|---|---|
| INFERENCE_TABLE_RETENTION_DAYS | 90 | How long predictions are kept (cost vs audit depth) |
| DRIFT_ALERT_THRESHOLD_PCT | 10 | Trigger alert if feature distribution shifts >10% |

**Results Table**

| Metric | Before | After | Interpretation |
|---|---:|---:|---|
| Visibility into predictions | 0% | 100% | Every prediction is queryable |
| Time to identify drift | Hours to days | Minutes | SQL query surface |
| Ability to compare models | Manual testing | Objective (prod metrics) | v2 vs v1 decision made on data |
| Audit trail (compliance) | Gone after 7 days | 90-day retention | Full lineage for regulators |

**Courier Analogy**

Before Inference Tables: parcels disappeared into the black box. You never knew which routes failed or slowed down.

After Inference Tables: every parcel's delivery is logged — route taken, time to delivery, any errors. The ledger never lies.

**What We Learned**

1. Inference Tables are free observability. Enable them on every Model Serving endpoint.
2. Latency trends catch problems early (before users complain)
3. Feature distributions tell you if your data changed (drift) vs your model degraded
4. Model version comparison on prod metrics is more trustworthy than test benchmarks
5. Audit trails are not just compliance; they are your debugging toolkit
