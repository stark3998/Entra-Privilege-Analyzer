# -----------------------------------------------------------------------------
# Module: functions — Outputs
# -----------------------------------------------------------------------------

output "function_app_hostname" {
  description = "Default hostname of the Function App (e.g., func-myapp-scan-dev.azurewebsites.net)"
  value       = azurerm_linux_function_app.scan.default_hostname
}

output "function_app_id" {
  description = "Resource ID of the Function App"
  value       = azurerm_linux_function_app.scan.id
}

output "function_app_name" {
  description = "Name of the Function App"
  value       = azurerm_linux_function_app.scan.name
}

output "storage_account_name" {
  description = "Name of the storage account used for Durable Functions Task Hub"
  value       = azurerm_storage_account.functions.name
}
