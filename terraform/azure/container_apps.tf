resource "azurerm_container_app_environment" "main" {
  name                = "${var.project}-cae-${local.suffix}"
  location            = data.azurerm_resource_group.main.location
  resource_group_name = data.azurerm_resource_group.main.name
  # log_analytics_workspace_id omitted — workspace destroyed to save cost

  tags = local.tags
}

resource "azurerm_container_app" "api" {
  name                         = "${var.project}-api"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = data.azurerm_resource_group.main.name
  revision_mode                = "Single"

  template {
    container {
      name   = "api"
      image  = "${azurerm_container_registry.main.login_server}/${var.project}-api:latest"
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }
      env {
        name        = "DATABRICKS_HOST"
        secret_name = "databricks-host"
      }
      env {
        name        = "DATABRICKS_TOKEN"
        secret_name = "databricks-token"
      }
    }

    min_replicas = 1
    max_replicas = 3
  }

  secret {
    name  = "databricks-host"
    value = var.databricks_host
  }

  secret {
    name  = "databricks-token"
    value = var.databricks_token
  }

  ingress {
    external_enabled = true
    target_port      = 8000
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  registry {
    server               = azurerm_container_registry.main.login_server
    username             = azurerm_container_registry.main.admin_username
    password_secret_name = "registry-password"
  }

  secret {
    name  = "registry-password"
    value = azurerm_container_registry.main.admin_password
  }

  tags = local.tags
}