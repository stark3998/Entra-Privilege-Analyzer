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

variable "managed_identity_principal_id" {
  description = "Principal ID of the managed identity that needs Key Vault access"
  type        = string
}

variable "additional_secrets_user_principal_ids" {
  description = "Additional principal IDs that require Key Vault secret read access."
  type        = list(string)
  default     = []
}

variable "app_client_secret" {
  description = "Entra ID application client secret"
  type        = string
  sensitive   = true
}

variable "cosmos_primary_key" {
  description = "Cosmos DB primary key"
  type        = string
  sensitive   = true
}

variable "cosmos_endpoint" {
  description = "Cosmos DB account endpoint URL"
  type        = string
}

variable "redis_primary_key" {
  description = "Redis cache primary access key"
  type        = string
  sensitive   = true
}

variable "foundry_key" {
  description = "Azure AI Foundry API key"
  type        = string
  sensitive   = true
}

variable "appinsights_connection_string" {
  description = "Application Insights connection string"
  type        = string
  sensitive   = true
}

variable "encryption_key" {
  description = "Base64-encoded 32-byte AES-256-GCM key for encrypting stored credentials"
  type        = string
  sensitive   = true
}

variable "scan_function_key" {
  description = "Function-level auth key for the scan Function App"
  type        = string
  sensitive   = true
}

variable "agent_function_key" {
  description = "Function-level auth key for the durable agent endpoint"
  type        = string
  sensitive   = true
  default     = ""
}

variable "collection_app_client_secret" {
  description = "Client secret for the dedicated collection Entra application"
  type        = string
  sensitive   = true
  default     = ""
}

variable "mutation_app_client_secret" {
  description = "Client secret for the dedicated mutation Entra application"
  type        = string
  sensitive   = true
  default     = ""
}

variable "purge_protection_enabled" {
  description = "Whether Key Vault purge protection is enabled."
  type        = bool
  default     = true
}

variable "soft_delete_retention_days" {
  description = "Soft delete retention period for Key Vault secrets."
  type        = number
  default     = 90
}

variable "public_network_access_enabled" {
  description = "Whether Key Vault public network access remains enabled."
  type        = bool
  default     = true
}

variable "allowed_ip_ranges" {
  description = "Optional IPv4 CIDR ranges allowed to access Key Vault when network ACLs are enforced."
  type        = list(string)
  default     = []
}

variable "allowed_subnet_ids" {
  description = "Optional subnet resource IDs allowed to access Key Vault when network ACLs are enforced."
  type        = list(string)
  default     = []
}

variable "allow_trusted_azure_services" {
  description = "Whether trusted Azure services can bypass Key Vault network ACLs."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tags applied to all resources"
  type        = map(string)
  default     = {}
}
