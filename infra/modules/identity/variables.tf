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

variable "tags" {
  description = "Tags applied to all resources"
  type        = map(string)
  default     = {}
}
