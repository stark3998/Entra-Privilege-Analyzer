output "acr_id" {
  description = "Azure Container Registry resource ID"
  value       = azurerm_container_registry.main.id
}

output "acr_login_server" {
  description = "ACR login server (e.g., myacr.azurecr.io)"
  value       = azurerm_container_registry.main.login_server
}

output "acr_name" {
  description = "ACR name"
  value       = azurerm_container_registry.main.name
}

output "container_app_environment_id" {
  description = "Container App Environment resource ID"
  value       = azurerm_container_app_environment.main.id
}

output "backend_fqdn" {
  description = "Backend Container App FQDN"
  value       = azurerm_container_app.backend.ingress[0].fqdn
}

output "backend_container_app_name" {
  description = "Backend Container App name"
  value       = azurerm_container_app.backend.name
}

output "frontend_fqdn" {
  description = "Frontend Container App FQDN"
  value       = azurerm_container_app.frontend.ingress[0].fqdn
}

output "frontend_container_app_name" {
  description = "Frontend Container App name"
  value       = azurerm_container_app.frontend.name
}
