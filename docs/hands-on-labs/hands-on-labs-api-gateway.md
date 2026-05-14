# Helix API Gateway Labs (GW-01 to GW-04)

## Table of Contents

- [GW-01 Deployment Fails in Container Apps](#lab-gw-01-deployment-fails-in-container-apps-recovery)
- [GW-02 Metrics Endpoint Returns Stale Data](#lab-gw-02-metrics-endpoint-returns-stale-data-recovery)
- [GW-03 Streaming Response Breaks Mid-Flight](#lab-gw-03-streaming-response-breaks-mid-flight-recovery)
- [GW-04 Forecast and Visualize Contract Mismatch](#lab-gw-04-forecast-and-visualize-contract-mismatch-recovery)

---

## Lab GW-01: Deployment Fails in Container Apps Recovery

| Duration | Databricks Feature | Azure Feature | Estimated Cost | Prerequisites |
|---|---|---|---|---|
| 45 min | Serving client integration | Container Apps + ACR | ~EUR 1.00 | AI track complete |

**Start With Failure**

Deploy gateway with incorrect runtime environment variable mapping.

**Failure Signals**

- Container starts then crashes.
- Health endpoint unavailable.

**Guided Fix Path**

1. Read Container Apps logs.
2. Patch missing/incorrect env vars.
3. Redeploy and verify healthy startup.

**Compare Before vs After**

| Metric | Before | After |
|---|---:|---:|
| Startup success | No | Yes |
| Health checks passing | 0% | 100% |

**What You'll Learn**

Deployment failures are often configuration drift, same as broken DE Airflow workers after env changes.

**Courier Analogy**

The dispatch center opened without route credentials; restoring config reopened operations.

**Steps**

1. Deploy gateway image.
2. Open Azure logs for failing revision.
3. Update env vars/secrets.
4. Redeploy and call health endpoint via Swagger UI.

**Config Knobs**

| Variable | Default | What changing it does |
|---|---|---|
| GATEWAY_STARTUP_VALIDATE_ENV | false | Fails fast with clear config errors |

**Results Table**

| Metric | Before | After | Interpretation |
|---|---:|---:|---|
| Mean time to recover | High | Lower | Better startup diagnostics |

**What We Learned**

Fast recovery needs clear startup validation and observability, not manual guesswork.

---

## Lab GW-02: Metrics Endpoint Returns Stale Data Recovery

| Duration | Databricks Feature | Azure Feature | Estimated Cost | Prerequisites |
|---|---|---|---|---|
| 40 min | SQL query path | SQL Warehouse | ~EUR 0.50 | GW-01 |

**Start With Failure**

Metrics endpoint uses stale cached snapshot after Gold updates.

**Failure Signals**

- Swagger response does not reflect latest table values.
- Timestamp freshness lags beyond target SLA.

**Guided Fix Path**

1. Add freshness timestamp to response.
2. Reduce or bypass stale cache for critical metrics.
3. Re-test after table update.

**Compare Before vs After**

| Metric | Before | After |
|---|---:|---:|
| Data freshness lag | High | Low |
| Trust in endpoint | Low | High |

**What You'll Learn**

Freshness guarantees are DE SLA concepts applied at API edges.

**Courier Analogy**

The dashboard showed yesterday's truck counts until the cache window was tightened.

**Steps**

1. Swagger UI: call GET metrics.
2. Update source Gold data.
3. Call endpoint again and observe stale response.
4. Apply freshness controls and retest.

**Config Knobs**

| Variable | Default | What changing it does |
|---|---|---|
| METRICS_CACHE_TTL_SECONDS | 300 | Lower value improves freshness |

**Results Table**

| Metric | Before | After | Interpretation |
|---|---:|---:|---|
| Freshness SLA hit rate | Low | High | Staleness controlled |

**What We Learned**

Caching improves speed but can break trust if freshness is unmanaged.

---

## Lab GW-03: Streaming Response Breaks Mid-Flight Recovery

| Duration | Databricks Feature | Azure Feature | Estimated Cost | Prerequisites |
|---|---|---|---|---|
| 50 min | SSE/async gateway path | Container Apps networking | ~EUR 1.00 | GW-02 |

**Start With Failure**

Long response streams terminate early under timeout settings.

**Failure Signals**

- Partial answer in client.
- Server logs show timeout/cancelled stream.

**Guided Fix Path**

1. Increase stream timeout safely.
2. Add heartbeat chunks.
3. Re-test long prompt streaming.

**Compare Before vs After**

| Metric | Before | After |
|---|---:|---:|
| Stream completion rate | Low | High |
| Timeout errors | High | Lower |

**What You'll Learn**

Streaming reliability is like DE long-running job heartbeat handling.

**Courier Analogy**

The live delivery tracker stopped updating mid-route; heartbeat pings kept the channel alive.

**Steps**

1. Swagger UI: call POST ask with complex prompt.
2. Observe broken stream.
3. Tune timeout and heartbeat settings.
4. Re-run and verify full stream completion.

**Config Knobs**

| Variable | Default | What changing it does |
|---|---|---|
| STREAM_TIMEOUT_SECONDS | 30 | Prevents premature connection close |
| STREAM_HEARTBEAT_SECONDS | 0 | Keeps long streams active |

**Results Table**

| Metric | Before | After | Interpretation |
|---|---:|---:|---|
| Full-stream success | Low | High | Runtime stability improved |

**What We Learned**

Streaming paths need explicit timeout and keepalive design, not default API settings.

---

## Lab GW-04: Forecast and Visualize Contract Mismatch Recovery

| Duration | Databricks Feature | Azure Feature | Estimated Cost | Prerequisites |
|---|---|---|---|---|
| 45 min | Model serving + chart generation | API contracts | ~EUR 1.50 | GW-03 |

**Start With Failure**

Forecast endpoint output schema no longer matches visualize endpoint input schema.

**Failure Signals**

- Visualize call returns validation error.
- Chart payload misses required fields.

**Guided Fix Path**

1. Compare response/request schemas.
2. Introduce adapter or contract versioning.
3. Re-run forecast then visualize flow.

**Compare Before vs After**

| Metric | Before | After |
|---|---:|---:|
| Forecast-to-chart success | Low | High |
| Contract validation errors | High | Lower |

**What You'll Learn**

API contract drift is the same as schema drift between DE jobs.

**Courier Analogy**

Forecast parcels used a new label format that the chart station could not read until a translation step was added.

**Steps**

1. Swagger UI: run forecast endpoint.
2. Send result to visualize endpoint.
3. Capture validation failure.
4. Apply schema adapter/version fix and rerun.

**Config Knobs**

| Variable | Default | What changing it does |
|---|---|---|
| ENABLE_FORECAST_VISUALIZE_ADAPTER | false | Maps forecast payload to visualization contract |

**Results Table**

| Metric | Before | After | Interpretation |
|---|---:|---:|---|
| End-to-end UX success | Low | High | Contract compatibility restored |

**What We Learned**

Great models still fail users if interface contracts drift. End-to-end contract checks are mandatory.
