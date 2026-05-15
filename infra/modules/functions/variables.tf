# -----------------------------------------------------------------------------
# Module: functions — Input Variables
# -----------------------------------------------------------------------------

variable "project_name" {
  description = "Short project name for resource naming (lowercase, no hyphens)"
  type        = string
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
}

variable "location" {
  description = "Azure region"
  type        = string
}

variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
}

# ---------------------
# Identity
# ---------------------

variable "managed_identity_id" {
  description = "User-assigned managed identity resource ID (shared with backend Container App)"
  type        = string
}

variable "managed_identity_principal_id" {
  description = "User-assigned managed identity principal (object) ID"
  type        = string
}

# ---------------------
# Key Vault
# ---------------------

variable "key_vault_uri" {
  description = "Key Vault URI (e.g., https://kv-myapp-dev.vault.azure.net/)"
  type        = string
}

variable "secret_uris" {
  description = "Map of Key Vault secret URIs for app settings Key Vault references"
  type        = map(string)
  # Expected keys: "cosmos_endpoint", "cosmos_key"
}

# ---------------------
# Cosmos DB
# ---------------------

variable "cosmos_database_name" {
  description = "Cosmos DB database name"
  type        = string
}

# ---------------------
# Observability
# ---------------------

variable "application_insights_connection_string" {
  description = "Application Insights connection string"
  type        = string
}

# ---------------------
# Scaling
# ---------------------

variable "always_ready_instances" {
  description = "Number of always-ready instances to avoid cold starts (Flex Consumption)"
  type        = number
  default     = 1
}

variable "maximum_instance_count" {
  description = "Maximum instance count for parallel activity execution (Flex Consumption)"
  type        = number
  default     = 10
}

# ---------------------
# Tags
# ---------------------

variable "tags" {
  description = "Tags applied to all resources"
  type        = map(string)
  default     = {}
}
