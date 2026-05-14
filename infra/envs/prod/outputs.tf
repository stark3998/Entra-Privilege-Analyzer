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
