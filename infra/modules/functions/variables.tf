# -----------------------------------------------------------------------------
# Module: functions — Input Variables
# -----------------------------------------------------------------------------

variable "project_name" {
  description = "Short project name for resource naming (lowercase, no hyphens)"
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

# ---------------------
# Identity
# ---------------------

variable "managed_identity_id" {
  description = "User-assigned managed identity resource ID (shared with backend Container App)"
  type        = string
}

variable "managed_identity_principal_id" {
  description = "User-assigned managed identity principal (object) ID"
  type        = string
}

variable "managed_identity_client_id" {
  description = "User-assigned managed identity client ID exposed to the Function App."
  type        = string
}

variable "collection_managed_identity_id" {
  description = "Optional collection managed identity resource ID assigned to the Function App."
  type        = string
  default     = null
}

variable "collection_managed_identity_client_id" {
  description = "Optional collection managed identity client ID exposed to the Function App."
  type        = string
  default     = null
}

variable "mutation_managed_identity_id" {
  description = "Optional mutation managed identity resource ID assigned to the Function App."
  type        = string
  default     = null
}

variable "mutation_managed_identity_client_id" {
  description = "Optional mutation managed identity client ID exposed to the Function App."
  type        = string
  default     = null
}

# ---------------------
# Key Vault
# ---------------------

variable "key_vault_uri" {
  description = "Key Vault URI (e.g., https://kv-myapp-dev.vault.azure.net/)"
  type        = string
}

variable "secret_uris" {
  description = "Map of Key Vault secret URIs for app settings Key Vault references"
  type        = map(string)
  # Expected keys: "cosmos_endpoint", "cosmos_key", "encryption_key"
}

# ---------------------
# Cosmos DB
# ---------------------

variable "cosmos_database_name" {
  description = "Cosmos DB database name"
  type        = string
}

# ---------------------
# Observability
# ---------------------

variable "application_insights_connection_string" {
  description = "Application Insights connection string"
  type        = string
}

variable "tenant_evidence_raw_ttl_seconds" {
  description = "Retention period for raw tenant evidence in seconds."
  type        = number
  default     = 31536000
}

variable "tenant_evidence_storage_account_name" {
  description = "Storage account name used for immutable evidence, snapshots, and audit blobs."
  type        = string
}

variable "tenant_evidence_blob_endpoint" {
  description = "Blob endpoint for immutable evidence storage."
  type        = string
}

variable "tenant_evidence_queue_endpoint" {
  description = "Queue endpoint for evidence and agent work dispatch."
  type        = string
}

variable "tenant_evidence_snapshot_container_name" {
  description = "Blob container name for immutable access snapshots."
  type        = string
}

variable "tenant_evidence_audit_container_name" {
  description = "Blob container name for immutable audit records."
  type        = string
}

variable "tenant_evidence_raw_container_name" {
  description = "Blob container name for raw tenant evidence payloads."
  type        = string
}

variable "tenant_evidence_queue_names" {
  description = "Queue names for collection, mutation, and agent workloads."
  type = object({
    collection            = string
    collection_deadletter = string
    mutation              = string
    mutation_deadletter   = string
    agent                 = string
    agent_deadletter      = string
  })
}

variable "agent_runtime_enabled" {
  description = "Whether durable agent runtime settings are enabled on the Function App."
  type        = bool
  default     = true
}

variable "foundry_project_endpoint" {
  description = "Microsoft Foundry project endpoint used by Agent Framework clients."
  type        = string
}

variable "durable_task_hub_name" {
  description = "Durable Functions task hub name."
  type        = string
  default     = "EntraPermScanHub"
}

# ---------------------
# Scaling
# ---------------------

variable "always_ready_instances" {
  description = "Number of always-ready instances to avoid cold starts (Flex Consumption)"
  type        = number
  default     = 1
}

variable "maximum_instance_count" {
  description = "Maximum instance count for parallel activity execution (Flex Consumption)"
  type        = number
  default     = 10
}

variable "public_network_access_enabled" {
  description = "Whether the Function App storage account keeps public network access enabled."
  type        = bool
  default     = true
}

variable "allowed_ip_ranges" {
  description = "Optional IPv4 CIDR ranges allowed to access the Function App storage account."
  type        = list(string)
  default     = []
}

variable "allowed_subnet_ids" {
  description = "Optional subnet resource IDs allowed to access the Function App storage account."
  type        = list(string)
  default     = []
}

variable "allow_trusted_azure_services" {
  description = "Whether trusted Azure services can bypass Function App storage account network ACLs."
  type        = bool
  default     = true
}

# ---------------------
# Tags
# ---------------------

variable "tags" {
  description = "Tags applied to all resources"
  type        = map(string)
  default     = {}
}
