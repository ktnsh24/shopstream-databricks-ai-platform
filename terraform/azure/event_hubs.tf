# Event Hubs removed — deleted 2026-05-17 to save ~$25/month.
# Uncomment when resuming Phase 01 (streaming pipeline).
#
# resource "azurerm_eventhub_namespace" "main" {
#   name                = "${var.project}-events-${local.suffix}"
#   location            = data.azurerm_resource_group.main.location
#   resource_group_name = data.azurerm_resource_group.main.name
#   sku                 = "Standard"
#   capacity            = 1
#   tags = local.tags
# }
#
# resource "azurerm_eventhub" "orders" {
#   name                = "orders"
#   namespace_name      = azurerm_eventhub_namespace.main.name
#   resource_group_name = data.azurerm_resource_group.main.name
#   partition_count     = 2
#   message_retention   = 1
# }
#
# resource "azurerm_eventhub_consumer_group" "databricks" {
#   name                = "databricks-streaming"
#   namespace_name      = azurerm_eventhub_namespace.main.name
#   eventhub_name       = azurerm_eventhub.orders.name
#   resource_group_name = data.azurerm_resource_group.main.name
# }

