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

variable "encryption_key" {
  description = "Base64-encoded 32-byte AES-256-GCM key for encrypting stored credentials"
  type        = string
  sensitive   = true
}

variable "scan_function_key" {
  description = "Function-level auth key for the scan Function App"
  type        = string
  sensitive   = true
  default     = ""
}

variable "agent_function_key" {
  description = "Function-level auth key for the durable agent endpoint"
  type        = string
  sensitive   = true
  default     = ""
}

variable "cors_origin_regex" {
  description = "Regex for allowed browser origins for the frontend"
  type        = string
  default     = "^https://(ca-entraperm-frontend-prod\\.[a-z0-9-]+\\.[a-z]+\\.azurecontainerapps\\.io|[a-z0-9-]+\\.jatinmadan\\.com)$"
}

variable "tenant_evidence_raw_ttl_seconds" {
  description = "Retention period for raw tenant evidence in seconds."
  type        = number
  default     = 31536000
}

variable "monthly_budget_amount" {
  description = "Optional monthly budget amount for the production resource group. Set to null to disable."
  type        = number
  default     = null
}

variable "budget_contact_emails" {
  description = "Optional email recipients for budget notifications."
  type        = list(string)
  default     = []
}

variable "platform_allowed_ip_ranges" {
  description = "Optional IPv4 CIDR ranges allowed to access secured data-plane resources."
  type        = list(string)
  default     = []
}

variable "platform_allowed_subnet_ids" {
  description = "Optional subnet resource IDs allowed to access secured data-plane resources."
  type        = list(string)
  default     = []
}

variable "allow_trusted_azure_services" {
  description = "Whether trusted Azure services can bypass data-plane network ACLs where supported."
  type        = bool
  default     = true
}

variable "key_vault_public_network_access_enabled" {
  description = "Whether Key Vault public network access remains enabled."
  type        = bool
  default     = true
}

variable "tenant_evidence_storage_public_network_access_enabled" {
  description = "Whether the immutable tenant evidence storage account keeps public network access enabled."
  type        = bool
  default     = true
}

variable "functions_storage_public_network_access_enabled" {
  description = "Whether the Functions host storage account keeps public network access enabled."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tags applied to all resources"
  type        = map(string)
  default     = {}
}
