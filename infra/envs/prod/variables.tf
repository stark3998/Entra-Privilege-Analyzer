variable "project_name" {
  description = "Short project name used in resource naming (no hyphens, max 10 chars)"
  type        = string
  default     = "entraperm"

  validation {
    condition     = can(regex("^[a-z0-9]{3,10}$", var.project_name))
    error_message = "project_name must be 3-10 lowercase alphanumeric characters."
  }
}

variable "location" {
  description = "Azure region for all resources"
  type        = string
  default     = "eastus2"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "prod"
}

variable "existing_resource_group_name" {
  description = "Existing Azure resource group name to deploy into. If null, Terraform creates a new resource group."
  type        = string
  default     = null
}

variable "github_repository" {
  description = "GitHub repository in owner/repo format for OIDC federation"
  type        = string
}

variable "existing_application_client_id" {
  description = "Existing Entra application client ID to reuse for login and backend auth. If null, Terraform creates a new app registration."
  type        = string
  default     = null
}

variable "existing_application_client_secret" {
  description = "Client secret for the existing Entra application. Required when existing_application_client_id is set."
  type        = string
  default     = null
  sensitive   = true
}

variable "foundry_endpoint" {
  description = "Azure AI Foundry endpoint URL"
  type        = string
}

variable "foundry_key" {
  description = "Azure AI Foundry API key (stored in Key Vault, never in plain env vars)"
  type        = string
  sensitive   = true
}

variable "foundry_model" {
  description = "Azure AI Foundry model deployment name"
  type        = string
  default     = "gpt-4o"
}

variable "cors_origin_regex" {
  description = "Regex for allowed browser origins for the frontend"
  type        = string
  default     = "^https://ca-entraperm-frontend-prod\\.[a-z0-9-]+\\.[a-z]+\\.azurecontainerapps\\.io$"
}

variable "tags" {
  description = "Tags applied to all resources"
  type        = map(string)
  default     = {}
}
