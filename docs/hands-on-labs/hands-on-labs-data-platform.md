# ShopStream Databricks Data Platform Labs (DP-01 to DP-10)

## Table of Contents

- [DP-01 Auto Loader Schema Drift](#lab-dp-01-auto-loader-schema-drift-recovery)
- [DP-02 Streaming Lag and Late Data](#lab-dp-02-streaming-lag-and-late-data-recovery)
- [DP-03 SCD2 Not Closing Old Rows](#lab-dp-03-scd2-not-closing-old-rows-recovery)
- [DP-04 SCD1 Creating Duplicates](#lab-dp-04-scd1-creating-duplicates-recovery)
- [DP-05 Truncate-Load Wiping Reference Data](#lab-dp-05-truncate-load-wiping-reference-data-recovery)
- [DP-06 Data Quality Rule Too Weak](#lab-dp-06-data-quality-rule-too-weak-recovery)
- [DP-07 Gold Aggregation Mismatch](#lab-dp-07-gold-aggregation-mismatch-recovery)
- [DP-08 Time Travel Wrong Version](#lab-dp-08-time-travel-wrong-version-recovery)
- [DP-09 CDF Not Capturing Changes](#lab-dp-09-cdf-not-capturing-changes-recovery)
- [DP-10 Point-in-Time Join Leakage](#lab-dp-10-point-in-time-join-leakage-recovery)

---

## Lab DP-01: Auto Loader Schema Drift Recovery

| Duration | Databricks Feature | Azure Feature | Estimated Cost | Prerequisites |
|---|---|---|---|---|
| 45 min | Auto Loader | ADLS Gen2 | ~EUR 0.50 | Workspace + raw returns file |

**Start With Failure**
Upload a returns file with a new unexpected column (`refund_channel`) while strict schema is enabled.

**Failure Signals**
- Pipeline run fails on schema mismatch.
- Bronze table does not append new rows.

**Guided Fix Path**
1. Enable schema evolution for the source.
2. Re-run ingest job.
3. Validate new column appears in Bronze with null-safe defaults where missing.

**Compare Before vs After**

| Run | Rows ingested | Error count | New column present |
|---|---:|---:|---|
| Before fix | 0 | 1 | No |
| After fix | >0 | 0 | Yes |

**What You'll Learn**
Schema drift is the DE equivalent of upstream contract drift in batch pipelines.

**Courier Analogy**
A new parcel label appears at the loading dock; the scanner must learn it instead of rejecting the whole truck.

**Steps**
1. Run Bronze ingest pipeline from Databricks Jobs UI.
2. Inspect pipeline error details.
3. Update pipeline schema evolution setting.
4. Re-run and validate row count and columns in SQL editor.

**Config Knobs**

| Variable | Default | What changing it does |
|---|---|---|
| AUTLOADER_SCHEMA_EVOLUTION | false | Allows new columns from raw data |

**Results Table**

| Metric | Before | After | Interpretation |
|---|---:|---:|---|
| Ingest success rate | 0% | 100% | Drift handled safely |

**What We Learned**
Small schema changes can stop ingestion entirely. Enabling controlled schema evolution restores flow without manual table rebuild.

---

## Lab DP-02: Streaming Lag and Late Data Recovery

| Duration | Databricks Feature | Azure Feature | Estimated Cost | Prerequisites |
|---|---|---|---|---|
| 60 min | Structured Streaming | Event Hubs | ~EUR 1.00 | DP-01 |

**Start With Failure**
Run stream with too-small watermark causing late events to be dropped.

**Failure Signals**
- Missing orders in Bronze vs produced events.
- Lag and dropped records in streaming metrics.

**Guided Fix Path**
1. Increase watermark threshold.
2. Tune trigger interval.
3. Re-run stream and compare ingest completeness.

**Compare Before vs After**

| Metric | Before | After |
|---|---:|---:|
| Produced events | 100 | 100 |
| Landed events | 82 | 99-100 |
| End-to-end lag | High | Lower |

**What You'll Learn**
Late data tuning is like handling delayed partition arrivals in daily batch windows.

**Courier Analogy**
Parcels arriving a bit late were thrown away at the gate; you extend the acceptance window.

**Steps**
1. Start stream job in Databricks.
2. Publish test events.
3. Inspect dropped records and lag.
4. Adjust watermark + trigger.
5. Re-run and verify completeness.

**Config Knobs**

| Variable | Default | What changing it does |
|---|---|---|
| STREAM_WATERMARK_MINUTES | 5 | Larger value accepts later events |
| STREAM_TRIGGER_SECONDS | 60 | Lower value reduces perceived lag |

**Results Table**

| Metric | Before | After | Interpretation |
|---|---:|---:|---|
| Data completeness | 82% | 99%+ | Better late-event tolerance |

**What We Learned**
Streaming failures are often configuration failures, not code bugs. Tuning windows and triggers restores reliability.

---

## Lab DP-03: SCD2 Not Closing Old Rows Recovery

| Duration | Databricks Feature | Azure Feature | Estimated Cost | Prerequisites |
|---|---|---|---|---|
| 45 min | Lakeflow apply_changes SCD2 | ADLS Gen2 | ~EUR 0.75 | DP-02 |

**Start With Failure**
Run customer SCD2 merge without proper sequence column.

**Failure Signals**
- Multiple current rows for same customer.
- `__END_AT` remains null on old row.

**Guided Fix Path**
1. Set correct sequence/order column.
2. Re-run SCD2 pipeline.
3. Assert one current row per customer.

**Compare Before vs After**

| Check | Before | After |
|---|---|---|
| Current rows per customer | >1 possible | Exactly 1 |
| History integrity | Broken | Correct |

**What You'll Learn**
SCD2 correctness depends on ordering guarantees, same as CDC replay ordering.

**Courier Analogy**
A customer moved address; without closing the old ticket, dispatch has two active destinations.

**Steps**
1. Trigger SCD2 pipeline.
2. Query duplicates in current flag.
3. Fix sequence key in pipeline config.
4. Re-run and validate history.

**Config Knobs**

| Variable | Default | What changing it does |
|---|---|---|
| SCD2_SEQUENCE_COL | ingestion_ts | Determines row version order |

**Results Table**

| Metric | Before | After | Interpretation |
|---|---:|---:|---|
| Customers with >1 active row | >0 | 0 | SCD2 fixed |

**What We Learned**
Without deterministic ordering, history tables lie. Fixing sequence logic restores trustworthy dimensions.

---

## Lab DP-04: SCD1 Creating Duplicates Recovery

| Duration | Databricks Feature | Azure Feature | Estimated Cost | Prerequisites |
|---|---|---|---|---|
| 40 min | Lakeflow apply_changes SCD1 | ADLS Gen2 | ~EUR 0.75 | DP-03 |

**Start With Failure**
Use append path accidentally instead of upsert for product dimension.

**Failure Signals**
- Duplicate product IDs.
- Different prices for same key in current table.

**Guided Fix Path**
1. Switch write mode to SCD1/upsert.
2. Deduplicate by business key.
3. Re-run and validate one row per product.

**Compare Before vs After**

| Metric | Before | After |
|---|---:|---:|
| Duplicate product keys | High | 0 |
| Row count inflation | Yes | No |

**What You'll Learn**
SCD1 is equivalent to latest-snapshot semantics in warehouse dimensions.

**Courier Analogy**
Old product cards were stacked instead of replaced, confusing the pickers.

**Steps**
1. Run SCD1 pipeline.
2. Identify duplicate keys in SQL.
3. Correct merge semantics.
4. Re-run and validate uniqueness.

**Config Knobs**

| Variable | Default | What changing it does |
|---|---|---|
| PRODUCT_DIM_MODE | append | Must be upsert for SCD1 |

**Results Table**

| Metric | Before | After | Interpretation |
|---|---:|---:|---|
| Key uniqueness | Failing | Passing | Correct SCD1 behavior |

**What We Learned**
SCD1 failures silently poison downstream joins. Fixing key semantics prevents revenue mismatches.

---

## Lab DP-05: Truncate-Load Wiping Reference Data Recovery

| Duration | Databricks Feature | Azure Feature | Estimated Cost | Prerequisites |
|---|---|---|---|---|
| 35 min | Overwrite write mode | ADLS Gen2 | ~EUR 0.25 | DP-04 |

**Start With Failure**
Run truncate-load with an incomplete reference file.

**Failure Signals**
- Reference table row count suddenly drops.
- Downstream joins lose region values.

**Guided Fix Path**
1. Add row-count guardrail before overwrite.
2. Reject file if below threshold.
3. Re-run with complete file.

**Compare Before vs After**

| Metric | Before | After |
|---|---:|---:|
| Region rows | Reduced | Restored |
| Null join rate | High | Low |

**What You'll Learn**
This is the DE equivalent of preventing destructive full-refresh loads without validation.

**Courier Analogy**
You replaced the depot route map with a half-printed version; add a completeness check before replacement.

**Steps**
1. Execute truncate-load job.
2. Measure row-count drop.
3. Add pre-check validation.
4. Re-run with valid input and verify joins.

**Config Knobs**

| Variable | Default | What changing it does |
|---|---|---|
| REF_MIN_ROWS | 1 | Blocks dangerous low-volume overwrite |

**Results Table**

| Metric | Before | After | Interpretation |
|---|---:|---:|---|
| Bad overwrite incidents | 1 | 0 | Guardrail effective |

**What We Learned**
Overwrite is safe only with data-quality gates. Validate volume before replacing dimensions.

---

## Lab DP-06: Data Quality Rule Too Weak Recovery

| Duration | Databricks Feature | Azure Feature | Estimated Cost | Prerequisites |
|---|---|---|---|---|
| 45 min | Lakeflow expectations | Event Hubs + ADLS | ~EUR 0.75 | DP-05 |

**Start With Failure**
Current quality rule accepts null `order_id` due to weak condition.

**Failure Signals**
- Bad rows reach Silver.
- Downstream aggregate errors.

**Guided Fix Path**
1. Tighten expectation expression.
2. Re-run pipeline with bad sample.
3. Confirm invalid rows are dropped and audited.

**Compare Before vs After**

| Metric | Before | After |
|---|---:|---:|
| Invalid rows passing | >0 | 0 |
| Data quality score | Low | High |

**What You'll Learn**
Quality rules are equivalent to schema + business-rule checks in ETL validation layers.

**Courier Analogy**
Parcels without tracking IDs were still loaded; tighten gate checks.

**Steps**
1. Inject invalid sample rows.
2. Run Silver pipeline.
3. Observe expectation report.
4. Tighten rule and rerun.

**Config Knobs**

| Variable | Default | What changing it does |
|---|---|---|
| EXPECT_ORDER_ID_NOT_NULL | false | Enforces strict key validation |

**Results Table**

| Metric | Before | After | Interpretation |
|---|---:|---:|---|
| Bad row leakage | Yes | No | Rule now protects Silver |

**What We Learned**
Weak quality checks create expensive downstream debugging. Strong checks fail early and cheaply.

---

## Lab DP-07: Gold Aggregation Mismatch Recovery

| Duration | Databricks Feature | Azure Feature | Estimated Cost | Prerequisites |
|---|---|---|---|---|
| 50 min | Delta aggregations | SQL Warehouse | ~EUR 1.00 | DP-06 |

**Start With Failure**
Gold revenue aggregation groups on wrong date field.

**Failure Signals**
- Dashboard total differs from Silver source totals.
- Daily buckets inconsistent.

**Guided Fix Path**
1. Identify incorrect grouping key.
2. Patch aggregation logic.
3. Recompute Gold and reconcile sums.

**Compare Before vs After**

| Metric | Before | After |
|---|---:|---:|
| Revenue reconciliation error | High | Near zero |
| Dashboard trust | Low | High |

**What You'll Learn**
Aggregation bugs are equivalent to wrong group-by keys in warehouse marts.

**Courier Analogy**
You sorted parcels by pickup date instead of delivery date, so daily dispatch numbers were wrong.

**Steps**
1. Run Gold job and capture totals.
2. Run reconciliation SQL.
3. Fix grouping key.
4. Re-run and validate parity.

**Config Knobs**

| Variable | Default | What changing it does |
|---|---|---|
| GOLD_DATE_COLUMN | event_date | Controls daily bucket semantics |

**Results Table**

| Metric | Before | After | Interpretation |
|---|---:|---:|---|
| Sum mismatch | Present | Removed | Aggregation corrected |

**What We Learned**
Gold must reconcile to Silver totals. If it does not, business reporting is not trustworthy.

---

## Lab DP-08: Time Travel Wrong Version Recovery

| Duration | Databricks Feature | Azure Feature | Estimated Cost | Prerequisites |
|---|---|---|---|---|
| 30 min | Delta time travel | SQL Warehouse | ~EUR 0.25 | DP-07 |

**Start With Failure**
Analyst queries wrong table version and validates against stale output.

**Failure Signals**
- Historical numbers do not match run logs.
- Audit report mismatch.

**Guided Fix Path**
1. Identify expected commit/version from run metadata.
2. Query exact version or timestamp.
3. Document repeatable validation query.

**Compare Before vs After**

| Metric | Before | After |
|---|---:|---:|
| Audit reproducibility | Low | High |
| Validation errors | Frequent | Rare |

**What You'll Learn**
Reproducibility in DE requires explicit version pinning, not latest-table assumptions.

**Courier Analogy**
You reviewed yesterday's manifest while investigating today's truck.

**Steps**
1. List Delta history.
2. Query incorrect version and note mismatch.
3. Query correct version.
4. Save validated SQL snippet.

**Config Knobs**

| Variable | Default | What changing it does |
|---|---|---|
| TIME_TRAVEL_VERSION | latest | Pins reproducible snapshot |

**Results Table**

| Metric | Before | After | Interpretation |
|---|---:|---:|---|
| Snapshot correctness | Unreliable | Reliable | Version pinning works |

**What We Learned**
Delta time travel is powerful only when version selection is explicit and documented.

---

## Lab DP-09: CDF Not Capturing Changes Recovery

| Duration | Databricks Feature | Azure Feature | Estimated Cost | Prerequisites |
|---|---|---|---|---|
| 35 min | Change Data Feed | SQL Warehouse | ~EUR 0.25 | DP-08 |

**Start With Failure**
CDF disabled on source table before updates.

**Failure Signals**
- `table_changes` returns empty set.
- CDC downstream job misses updates.

**Guided Fix Path**
1. Enable CDF on source table.
2. Re-run update workload.
3. Re-query changes and validate `_change_type`.

**Compare Before vs After**

| Metric | Before | After |
|---|---:|---:|
| CDF rows captured | 0 | >0 |
| CDC pipeline correctness | Failing | Passing |

**What You'll Learn**
CDC reliability depends on source table capabilities enabled before change events.

**Courier Analogy**
The depot forgot to turn on scan logging, so no movement history exists.

**Steps**
1. Execute update operation.
2. Query `table_changes` and observe empty result.
3. Enable CDF and rerun update.
4. Validate captured inserts/updates/deletes.

**Config Knobs**

| Variable | Default | What changing it does |
|---|---|---|
| ENABLE_CDF | false | Turns on change capture |

**Results Table**

| Metric | Before | After | Interpretation |
|---|---:|---:|---|
| Change visibility | None | Full | CDF operational |

**What We Learned**
CDC should be treated like observability: if not enabled early, history cannot be recovered retroactively.

---

## Lab DP-10: Point-in-Time Join Leakage Recovery

| Duration | Databricks Feature | Azure Feature | Estimated Cost | Prerequisites |
|---|---|---|---|---|
| 60 min | SCD2 temporal joins | SQL Warehouse | ~EUR 0.50 | DP-09 |

**Start With Failure**
Join facts to current dimension row instead of time-valid row.

**Failure Signals**
- Historical orders show current customer segment.
- Backtest metrics drift unexpectedly.

**Guided Fix Path**
1. Replace naive join with temporal join (`BETWEEN __START_AT AND __END_AT`).
2. Recompute validation sample.
3. Confirm old orders keep old segment.

**Compare Before vs After**

| Metric | Before | After |
|---|---:|---:|
| Historical label leakage | High | Near zero |
| Backtest trust | Low | High |

**What You'll Learn**
Temporal correctness is critical for both analytics and ML feature generation.

**Courier Analogy**
You assigned old parcels to the customer's new address plan, rewriting history.

**Steps**
1. Run baseline join and capture wrong outputs.
2. Implement temporal condition.
3. Re-run and compare sample orders.
4. Document reusable PIT join pattern.

**Config Knobs**

| Variable | Default | What changing it does |
|---|---|---|
| USE_PIT_JOIN | false | Enables correct historical mapping |

**Results Table**

| Metric | Before | After | Interpretation |
|---|---:|---:|---|
| Temporal accuracy | Poor | Strong | Leakage removed |

**What We Learned**
Point-in-time joins are the DE equivalent of training-data correctness guarantees.
