# ---------------------------------------------------------------------------
# Inference Tables — enable auto-logging on the helix-shopstream-agent endpoint
# ---------------------------------------------------------------------------
#
# What this does:
#   Every request and response to the helix-shopstream-agent serving endpoint
#   is automatically written as a row to a Delta table in Hive Metastore.
#   This is the equivalent of turning on access logging on an S3 bucket —
#   nothing changes in the application, but you get a full audit trail.
#
# DE parallel:
#   CDC (Change Data Capture) log — every LLM request/response is an event,
#   queryable with SQL just like any other Delta table.
#
# Table produced:
#   hive_metastore.ml.shopstream_inference_logs
#   Columns: request_timestamp, databricks_request_id, request, response, status_code
#
# Activate (one-time, Databricks UI):
#   Serving → helix-shopstream-agent → Edit endpoint config →
#   Inference Tables → Enable → Catalog: hive_metastore, Schema: ml,
#   Table prefix: shopstream_inference → Save
#
# Or via REST API (run scripts/enable_inference_tables.sh once):
#   The endpoint is managed by MLflow PyFunc registration, not Terraform.
#   Adding a databricks_model_serving resource here would conflict with the
#   MLflow-managed lifecycle. Use the REST API script for the live endpoint.
#   This file documents the desired state for reference and future Terraform
#   -managed deployments.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# LLM Monitoring job — scheduled error rate + drift checks
# ---------------------------------------------------------------------------
#
# The monitoring job is defined in databricks.yml (resources.jobs.llm_monitoring).
# This file contains only the Databricks Workflows schedule.
#
# If moving to Terraform-only deployment in future, add:
#
# resource "databricks_job" "llm_monitoring" {
#   name = "helix_llm_monitoring"
#
#   schedule {
#     quartz_cron_expression = "0 0/15 * * * ?"   # every 15 minutes
#     timezone_id            = "UTC"
#     pause_status           = "UNPAUSED"
#   }
#
#   task {
#     task_key = "check"
#     python_wheel_task {
#       package_name = "shopstream_databricks_ai_platform"
#       entry_point  = "run_llm_monitoring"
#     }
#     new_cluster {
#       spark_version             = "15.4.x-scala2.12"
#       node_type_id              = "Standard_DS3_v2"
#       num_workers               = 1
#       autotermination_minutes   = 10
#     }
#   }
#
#   email_notifications {
#     on_failure = [var.alert_email]
#   }
# }
