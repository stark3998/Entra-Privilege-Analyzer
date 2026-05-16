output "cosmos_account_id" {
  description = "Cosmos DB account resource ID"
  value       = azurerm_cosmosdb_account.main.id
}

output "cosmos_endpoint" {
  description = "Cosmos DB account endpoint"
  value       = azurerm_cosmosdb_account.main.endpoint
}

output "cosmos_primary_key" {
  description = "Cosmos DB primary key"
  value       = azurerm_cosmosdb_account.main.primary_key
  sensitive   = true
}

output "cosmos_database_name" {
  description = "Cosmos DB master database name (project databases are created dynamically)"
  value       = azurerm_cosmosdb_sql_database.main.name
}

output "redis_id" {
  description = "Redis cache resource ID"
  value       = azurerm_redis_cache.main.id
}

output "redis_hostname" {
  description = "Redis cache hostname"
  value       = azurerm_redis_cache.main.hostname
}

output "redis_port" {
  description = "Redis cache SSL port"
  value       = azurerm_redis_cache.main.ssl_port
}

output "redis_primary_key" {
  description = "Redis cache primary access key"
  value       = azurerm_redis_cache.main.primary_access_key
  sensitive   = true
}
