variable "project_name" {
  description = "Short project name for resource naming"
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

variable "log_analytics_workspace_id" {
  description = "Log Analytics workspace ID for Container App Environment"
  type        = string
}

variable "managed_identity_id" {
  description = "User-assigned managed identity resource ID"
  type        = string
}

variable "managed_identity_principal_id" {
  description = "User-assigned managed identity principal (object) ID"
  type        = string
}

variable "managed_identity_client_id" {
  description = "User-assigned managed identity client ID for Azure SDK auth"
  type        = string
}

# Key Vault secret URIs for Container App secretRef
variable "secret_uris" {
  description = "Map of Key Vault secret URIs for Container App secret references"
  type = object({
    app_client_secret       = string
    cosmos_key              = string
    cosmos_endpoint         = string
    redis_password          = string
    foundry_key             = string
    appinsights_conn_string = string
    encryption_key          = string
    scan_function_key       = string
  })
}

variable "key_vault_uri" {
  description = "Key Vault URI"
  type        = string
}

# Image tags — initial values; CD pipeline overrides via az containerapp update
variable "backend_image_tag" {
  description = "Docker image tag for the backend container"
  type        = string
  default     = "initial"
}

variable "frontend_image_tag" {
  description = "Docker image tag for the frontend container"
  type        = string
  default     = "initial"
}

# App config
variable "application_client_id" {
  description = "Entra ID application client ID"
  type        = string
}

variable "tenant_id" {
  description = "Entra ID tenant ID"
  type        = string
}

variable "cors_origin_regex" {
  description = "Regex for allowed browser origins when exact frontend URLs are not known at deploy time"
  type        = string
  default     = ""
}

variable "cosmos_database_name" {
  description = "Cosmos DB database name"
  type        = string
}

variable "redis_hostname" {
  description = "Redis cache hostname"
  type        = string
}

variable "redis_port" {
  description = "Redis cache SSL port"
  type        = number
}

variable "scan_function_app_url" {
  description = "Base URL of the scan Function App (e.g., https://func-entraperm-scan-prod.azurewebsites.net)"
  type        = string
  default     = ""
}

variable "foundry_endpoint" {
  description = "Azure AI Foundry endpoint URL"
  type        = string
}

variable "foundry_model" {
  description = "Azure AI Foundry model deployment name"
  type        = string
  default     = "gpt-4o"
}

variable "tags" {
  description = "Tags applied to all resources"
  type        = map(string)
  default     = {}
}
