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

output "tenant_evidence_storage_account_id" {
  description = "Tenant evidence storage account resource ID"
  value       = azurerm_storage_account.tenant_evidence.id
}

output "tenant_evidence_storage_account_name" {
  description = "Tenant evidence storage account name"
  value       = azurerm_storage_account.tenant_evidence.name
}

output "tenant_evidence_blob_endpoint" {
  description = "Tenant evidence blob endpoint"
  value       = azurerm_storage_account.tenant_evidence.primary_blob_endpoint
}

output "tenant_evidence_queue_endpoint" {
  description = "Tenant evidence queue endpoint"
  value       = azurerm_storage_account.tenant_evidence.primary_queue_endpoint
}

output "tenant_evidence_snapshot_container_name" {
  description = "Blob container used for immutable access snapshots"
  value       = azurerm_storage_container.access_snapshots.name
}

output "tenant_evidence_audit_container_name" {
  description = "Blob container used for immutable audit archives"
  value       = azurerm_storage_container.audit_archive.name
}

output "tenant_evidence_raw_container_name" {
  description = "Blob container used for tenant evidence payloads"
  value       = azurerm_storage_container.tenant_evidence.name
}

output "tenant_evidence_queue_names" {
  description = "Queue names for collection, mutation, and agent workflows with explicit dead-letter queues."
  value = {
    collection            = azurerm_storage_queue.tenant_evidence["collection"].name
    collection_deadletter = azurerm_storage_queue.tenant_evidence["collection_deadletter"].name
    mutation              = azurerm_storage_queue.tenant_evidence["mutation"].name
    mutation_deadletter   = azurerm_storage_queue.tenant_evidence["mutation_deadletter"].name
    agent                 = azurerm_storage_queue.tenant_evidence["agent"].name
    agent_deadletter      = azurerm_storage_queue.tenant_evidence["agent_deadletter"].name
  }
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
