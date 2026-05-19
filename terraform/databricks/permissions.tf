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
# Workspace entitlements — required to log in and run notebooks/jobs
# ------------------------------------------------------------------
resource "databricks_user" "vaishnavi" {
  user_name = var.vaishnavi_email
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

# ------------------------------------------------------------------
# External locations — READ/WRITE FILES so notebooks can access ADLS
# ------------------------------------------------------------------
resource "databricks_grants" "bronze_location" {
  external_location = "helix-bronze"
  grant {
    principal  = var.vaishnavi_email
    privileges = ["READ_FILES", "WRITE_FILES", "CREATE_EXTERNAL_TABLE"]
  }
}

resource "databricks_grants" "silver_location" {
  external_location = "helix-silver"
  grant {
    principal  = var.vaishnavi_email
    privileges = ["READ_FILES", "WRITE_FILES", "CREATE_EXTERNAL_TABLE"]
  }
}

resource "databricks_grants" "gold_location" {
  external_location = "helix-gold"
  grant {
    principal  = var.vaishnavi_email
    privileges = ["READ_FILES", "WRITE_FILES", "CREATE_EXTERNAL_TABLE"]
  }
}
