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

variable "github_repository" {
  description = "GitHub repository in owner/repo format for OIDC federation"
  type        = string
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

variable "tags" {
  description = "Tags applied to all resources"
  type        = map(string)
  default     = {}
}
