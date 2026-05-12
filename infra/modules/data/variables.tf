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
  description = "Principal ID of the managed identity that needs Cosmos DB access"
  type        = string
}

variable "redis_sku" {
  description = "Redis cache SKU (Basic, Standard, Premium)"
  type        = string
  default     = "Standard"
}

variable "redis_family" {
  description = "Redis cache family (C for Basic/Standard, P for Premium)"
  type        = string
  default     = "C"
}

variable "redis_capacity" {
  description = "Redis cache capacity (0-6 for C family, 1-5 for P family)"
  type        = number
  default     = 1
}

variable "tags" {
  description = "Tags applied to all resources"
  type        = map(string)
  default     = {}
}
