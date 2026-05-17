resource "azurerm_user_assigned_identity" "databricks" {
  name                = "${var.project}-databricks-identity"
  location            = data.azurerm_resource_group.main.location
  resource_group_name = data.azurerm_resource_group.main.name

  tags = local.tags
}

resource "azurerm_role_assignment" "databricks_storage" {
  scope                = azurerm_storage_account.data.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.databricks.principal_id
}

resource "azurerm_key_vault_access_policy" "databricks_identity" {
  key_vault_id = azurerm_key_vault.main.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = azurerm_user_assigned_identity.databricks.principal_id

  secret_permissions = ["Get", "List"]
}