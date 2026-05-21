output "key_vault_id" {
  description = "Key Vault resource ID"
  value       = azurerm_key_vault.main.id
}

output "key_vault_name" {
  description = "Key Vault name"
  value       = azurerm_key_vault.main.name
}

output "key_vault_uri" {
  description = "Key Vault URI"
  value       = azurerm_key_vault.main.vault_uri
}

# Secret URIs for Container App secretRef
output "secret_uris" {
  description = "Map of secret names to their Key Vault secret URIs"
  value = {
    app_client_secret       = azurerm_key_vault_secret.app_client_secret.versionless_id
    cosmos_key              = azurerm_key_vault_secret.cosmos_key.versionless_id
    cosmos_endpoint         = azurerm_key_vault_secret.cosmos_endpoint.versionless_id
    redis_password          = azurerm_key_vault_secret.redis_password.versionless_id
    foundry_key             = azurerm_key_vault_secret.foundry_key.versionless_id
    appinsights_conn_string = azurerm_key_vault_secret.appinsights_connection_string.versionless_id
    encryption_key          = azurerm_key_vault_secret.encryption_key.versionless_id
    scan_function_key       = azurerm_key_vault_secret.scan_function_key.versionless_id
  }
}
