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

variable "redirect_uris" {
  description = "Web redirect URIs for the Entra ID app"
  type        = list(string)
  default     = []
}

variable "spa_redirect_uris" {
  description = "SPA redirect URIs for the Entra ID app"
  type        = list(string)
  default     = ["http://localhost:5173"]
}

variable "github_repository" {
  description = "GitHub repository in owner/repo format for OIDC federation"
  type        = string
}

variable "existing_application_client_id" {
  description = "Existing Entra application client ID to reuse. If null, Terraform creates a new application registration."
  type        = string
  default     = null
}

variable "existing_application_client_secret" {
  description = "Client secret for an existing Entra application. Required when existing_application_client_id is set."
  type        = string
  default     = null
  sensitive   = true
}

variable "provision_split_authorization_apps" {
  description = "Whether to create dedicated collection and mutation application registrations for split-privilege workflows."
  type        = bool
  default     = true
}

variable "collection_graph_application_permissions" {
  description = "Microsoft Graph application permissions granted to the collection app registration."
  type        = list(string)
  default = [
    "AccessReview.Read.All",
    "Application.Read.All",
    "AuditLog.Read.All",
    "Directory.Read.All",
    "GroupMember.Read.All",
    "IdentityRiskEvent.Read.All",
    "IdentityRiskyServicePrincipal.Read.All",
    "Policy.Read.All",
    "RoleManagement.Read.All",
    "RoleManagement.Read.Directory",
    "User.Read.All",
  ]
}

variable "mutation_graph_application_permissions" {
  description = "Microsoft Graph application permissions granted to the mutation app registration."
  type        = list(string)
  default = [
    "Application.Read.All",
    "Application.ReadWrite.All",
    "Directory.Read.All",
    "PrivilegedAccess.ReadWrite.AzureAD",
    "RoleManagement.Read.Directory",
    "RoleManagement.ReadWrite.Directory",
  ]
}

variable "tags" {
  description = "Tags applied to all resources"
  type        = map(string)
  default     = {}
}
