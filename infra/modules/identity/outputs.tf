output "application_client_id" {
  description = "Entra ID application (client) ID"
  value       = azuread_application.app.client_id
}

output "application_object_id" {
  description = "Entra ID application object ID"
  value       = azuread_application.app.object_id
}

output "service_principal_object_id" {
  description = "Service principal object ID"
  value       = azuread_service_principal.app.object_id
}

output "client_secret" {
  description = "Application client secret value (store in Key Vault)"
  value       = azuread_application_password.app.value
  sensitive   = true
}

output "managed_identity_id" {
  description = "User-assigned managed identity resource ID"
  value       = azurerm_user_assigned_identity.app.id
}

output "managed_identity_client_id" {
  description = "User-assigned managed identity client ID"
  value       = azurerm_user_assigned_identity.app.client_id
}

output "managed_identity_principal_id" {
  description = "User-assigned managed identity principal (object) ID"
  value       = azurerm_user_assigned_identity.app.principal_id
}

output "tenant_id" {
  description = "Entra ID tenant ID"
  value       = data.azuread_client_config.current.tenant_id
}
