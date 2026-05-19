resource "databricks_storage_credential" "adls" {
  name = "helix-adls-credential"

  azure_managed_identity {
    access_connector_id = var.access_connector_id
  }
}

resource "databricks_external_location" "bronze" {
  name            = "helix-bronze"
  url             = "abfss://bronze@${var.storage_account_name}.dfs.core.windows.net/"
  credential_name = databricks_storage_credential.adls.name
}

resource "databricks_external_location" "silver" {
  name            = "helix-silver"
  url             = "abfss://silver@${var.storage_account_name}.dfs.core.windows.net/"
  credential_name = databricks_storage_credential.adls.name
}

resource "databricks_external_location" "gold" {
  name            = "helix-gold"
  url             = "abfss://gold@${var.storage_account_name}.dfs.core.windows.net/"
  credential_name = databricks_storage_credential.adls.name
}