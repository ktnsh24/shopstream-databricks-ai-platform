# ============================================================
# User access — Vaishnavi (data platform developer)
# All permissions Vaishnavi needs to deploy and run pipelines.
# ============================================================

variable "vaishnavi_email" {
  description = "Vaishnavi's Databricks user email"
  type        = string
  default     = "vaishnavi.sahu.nl@gmail.com"
}

# ------------------------------------------------------------------
# Secret scope — READ access so pipelines can call dbutils.secrets
# ------------------------------------------------------------------
resource "databricks_secret_acl" "vaishnavi_helix_scope" {
  principal  = var.vaishnavi_email
  permission = "READ"
  scope      = databricks_secret_scope.helix.name
}

# ------------------------------------------------------------------
# Unity Catalog — helix_bronze
# ------------------------------------------------------------------
resource "databricks_grants" "bronze_catalog" {
  catalog = "helix_bronze"

  grant {
    principal  = var.vaishnavi_email
    privileges = ["USE_CATALOG", "CREATE_SCHEMA", "USE_SCHEMA", "CREATE_TABLE", "SELECT", "MODIFY"]
  }
}

# ------------------------------------------------------------------
# Unity Catalog — helix_silver
# ------------------------------------------------------------------
resource "databricks_grants" "silver_catalog" {
  catalog = "helix_silver"

  grant {
    principal  = var.vaishnavi_email
    privileges = ["USE_CATALOG", "CREATE_SCHEMA", "USE_SCHEMA", "CREATE_TABLE", "SELECT", "MODIFY"]
  }
}

# ------------------------------------------------------------------
# Unity Catalog — helix_gold
# ------------------------------------------------------------------
resource "databricks_grants" "gold_catalog" {
  catalog = "helix_gold"

  grant {
    principal  = var.vaishnavi_email
    privileges = ["USE_CATALOG", "CREATE_SCHEMA", "USE_SCHEMA", "CREATE_TABLE", "SELECT", "MODIFY"]
  }
}
