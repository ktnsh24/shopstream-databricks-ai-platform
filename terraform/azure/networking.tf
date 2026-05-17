# Log Analytics workspace removed — destroyed to save cost.
# Re-add before deploying Container App if centralised log routing is needed.
# resource "azurerm_log_analytics_workspace" "main" {
#   name                = "${var.project}-logs-${local.suffix}"
#   location            = data.azurerm_resource_group.main.location
#   resource_group_name = data.azurerm_resource_group.main.name
#   sku                 = "PerGB2018"
#   retention_in_days   = 30
#   tags = local.tags
# }


}