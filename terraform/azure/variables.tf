variable "environment" {
  description = "Deployment environment: dev, staging, or prod"
  type        = string
  default     = "dev"
}

variable "location" {
  description = "Azure region for all resources"
  type        = string
  default     = "westeurope"
}

variable "resource_group_name" {
  description = "Name of the Azure resource group (created manually in Phase 00)"
  type        = string
  default     = "shopstream-databricks-ai-platform-rg"
}

variable "project" {
  description = "Project name prefix for resource naming"
  type        = string
  default     = "helix"
}

variable "databricks_host" {
  description = "Databricks workspace URL, e.g. https://<workspace>.azuredatabricks.net"
  type        = string
  sensitive   = true
}

variable "databricks_token" {
  description = "Databricks personal access token for the Container App"
  type        = string
  sensitive   = true
}
