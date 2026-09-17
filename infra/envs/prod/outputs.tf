output "backend_fqdn" {
  description = "Backend Container App FQDN"
  value       = module.compute.backend_fqdn
}

output "frontend_fqdn" {
  description = "Frontend Container App FQDN"
  value       = module.compute.frontend_fqdn
}

output "acr_login_server" {
  description = "ACR login server for docker push"
  value       = module.compute.acr_login_server
}

output "acr_name" {
  description = "ACR name for az acr login"
  value       = module.compute.acr_name
}

output "cosmos_endpoint" {
  description = "Cosmos DB account endpoint"
  value       = module.data.cosmos_endpoint
}

output "key_vault_name" {
  description = "Key Vault name"
  value       = module.security.key_vault_name
}

output "application_client_id" {
  description = "Entra ID application client ID (set as AZURE_CLIENT_ID in GitHub vars)"
  value       = module.identity.application_client_id
}

output "collection_application_client_id" {
  description = "Collection application client ID for split authorization workflows"
  value       = module.identity.collection_application_client_id
}

output "mutation_application_client_id" {
  description = "Mutation application client ID for split authorization workflows"
  value       = module.identity.mutation_application_client_id
}

output "collection_managed_identity_client_id" {
  description = "Collection managed identity client ID"
  value       = module.identity.collection_managed_identity_client_id
}

output "mutation_managed_identity_client_id" {
  description = "Mutation managed identity client ID"
  value       = module.identity.mutation_managed_identity_client_id
}

output "tenant_id" {
  description = "Entra ID tenant ID (set as AZURE_TENANT_ID in GitHub vars)"
  value       = module.identity.tenant_id
}

output "backend_container_app_name" {
  description = "Backend Container App name for CD pipeline"
  value       = module.compute.backend_container_app_name
}

output "frontend_container_app_name" {
  description = "Frontend Container App name for CD pipeline"
  value       = module.compute.frontend_container_app_name
}

output "resource_group_name" {
  description = "Resource group name"
  value       = local.resource_group_name
}

output "cosmos_database_name" {
  description = "Cosmos DB master database name"
  value       = module.data.cosmos_database_name
}

output "function_app_hostname" {
  description = "Scan Function App hostname"
  value       = module.functions.function_app_hostname
}

output "function_app_name" {
  description = "Scan Function App name"
  value       = module.functions.function_app_name
}

output "agent_function_app_url" {
  description = "Scoped copilot gateway Function App base URL wired into the backend"
  value       = "https://${module.functions.function_app_hostname}"
}

output "log_analytics_workspace_id" {
  description = "Log Analytics workspace resource ID (for KQL queries)"
  value       = module.observability.log_analytics_workspace_id
}

output "budget_name" {
  description = "Resource group budget name when enabled"
  value       = module.observability.budget_name
}

output "tenant_evidence_storage_account_name" {
  description = "Storage account that stores immutable evidence, snapshots, and audit blobs"
  value       = module.data.tenant_evidence_storage_account_name
}

output "tenant_evidence_snapshot_container_name" {
  description = "Blob container used for immutable access snapshots"
  value       = module.data.tenant_evidence_snapshot_container_name
}

output "tenant_evidence_audit_container_name" {
  description = "Blob container used for immutable audit archives"
  value       = module.data.tenant_evidence_audit_container_name
}

output "tenant_evidence_queue_names" {
  description = "Queue names for collection, mutation, and agent workloads"
  value       = module.data.tenant_evidence_queue_names
}

output "collection_credential_reference" {
  description = "Key Vault secret URI for the collection application credential"
  value       = module.security.secret_uris.collection_app_secret
}

output "mutation_credential_reference" {
  description = "Key Vault secret URI for the mutation application credential"
  value       = module.security.secret_uris.mutation_app_secret
}
