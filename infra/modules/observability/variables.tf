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

variable "log_retention_days" {
  description = "Log Analytics retention period in days"
  type        = number
  default     = 30
}

variable "monthly_budget_amount" {
  description = "Optional monthly budget amount for the deployment resource group. Set to null to disable."
  type        = number
  default     = null
}

variable "budget_contact_emails" {
  description = "Optional email recipients for budget threshold notifications."
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Tags applied to all resources"
  type        = map(string)
  default     = {}
}
