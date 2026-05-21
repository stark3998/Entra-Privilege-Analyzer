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

variable "tags" {
  description = "Tags applied to all resources"
  type        = map(string)
  default     = {}
}
