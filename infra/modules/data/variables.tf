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

variable "collection_managed_identity_principal_id" {
  description = "Principal ID of the collection managed identity that needs tenant-evidence data plane access."
  type        = string
  default     = null
}

variable "mutation_managed_identity_principal_id" {
  description = "Principal ID of the mutation managed identity that needs snapshot, audit, and queue access."
  type        = string
  default     = null
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

variable "tenant_evidence_storage_public_network_access_enabled" {
  description = "Whether the immutable tenant evidence storage account keeps public network access enabled."
  type        = bool
  default     = true
}

variable "tenant_evidence_storage_allowed_ip_ranges" {
  description = "Optional IPv4 CIDR ranges allowed to access the tenant evidence storage account."
  type        = list(string)
  default     = []
}

variable "tenant_evidence_storage_allowed_subnet_ids" {
  description = "Optional subnet resource IDs allowed to access the tenant evidence storage account."
  type        = list(string)
  default     = []
}

variable "tenant_evidence_storage_allow_trusted_azure_services" {
  description = "Whether trusted Azure services can bypass tenant evidence storage network ACLs."
  type        = bool
  default     = true
}

variable "tenant_evidence_blob_delete_retention_days" {
  description = "Retention period for soft-deleted tenant evidence blobs."
  type        = number
  default     = 30
}

variable "tenant_evidence_container_delete_retention_days" {
  description = "Retention period for soft-deleted tenant evidence containers."
  type        = number
  default     = 30
}

variable "tags" {
  description = "Tags applied to all resources"
  type        = map(string)
  default     = {}
}
