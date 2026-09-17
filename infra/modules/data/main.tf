# -----------------------------------------------------------------------------
# Module: data
# Cosmos DB (serverless, NoSQL) + Azure Cache for Redis
# -----------------------------------------------------------------------------

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.116.0"
    }
  }
}

locals {
  cosmos_contributor_principal_ids = toset(compact([
    var.managed_identity_principal_id,
    var.collection_managed_identity_principal_id,
  ]))
  evidence_storage_principal_ids = toset(compact([
    var.managed_identity_principal_id,
    var.collection_managed_identity_principal_id,
    var.mutation_managed_identity_principal_id,
  ]))
  tenant_evidence_storage_default_action = var.tenant_evidence_storage_public_network_access_enabled && length(var.tenant_evidence_storage_allowed_ip_ranges) == 0 && length(var.tenant_evidence_storage_allowed_subnet_ids) == 0 ? "Allow" : "Deny"
  tenant_evidence_queue_names = {
    collection            = "tenant-evidence"
    collection_deadletter = "tenant-evidence-dlq"
    mutation              = "remediation-mutations"
    mutation_deadletter   = "remediation-mutations-dlq"
    agent                 = "agent-work-items"
    agent_deadletter      = "agent-work-items-dlq"
  }
}

# ---------------------
# Cosmos DB Account (serverless)
# ---------------------

resource "azurerm_cosmosdb_account" "main" {
  name                = "cosmos-${var.project_name}-${var.environment}"
  location            = var.location
  resource_group_name = var.resource_group_name
  offer_type          = "Standard"
  kind                = "GlobalDocumentDB"

  capabilities {
    name = "EnableServerless"
  }

  consistency_policy {
    consistency_level = "Session"
  }

  geo_location {
    location          = var.location
    failover_priority = 0
  }

  tags = var.tags
}

# ---------------------
# Cosmos DB SQL Database - Master
# Per-project databases (e.g., "project-<uuid>") are provisioned dynamically
# by the backend's ProjectDatabaseManager at project creation time.
# Terraform only manages the master database and its containers.
# ---------------------

resource "azurerm_cosmosdb_sql_database" "main" {
  name                = "entra-master"
  resource_group_name = var.resource_group_name
  account_name        = azurerm_cosmosdb_account.main.name
}

# ---------------------
# Master Containers
# ---------------------

resource "azurerm_cosmosdb_sql_container" "projects" {
  name                = "projects"
  resource_group_name = var.resource_group_name
  account_name        = azurerm_cosmosdb_account.main.name
  database_name       = azurerm_cosmosdb_sql_database.main.name
  partition_key_paths = ["/ownerId"]

  indexing_policy {
    indexing_mode = "consistent"

    included_path {
      path = "/*"
    }
  }
}

resource "azurerm_cosmosdb_sql_container" "tenant_registry" {
  name                = "tenant_registry"
  resource_group_name = var.resource_group_name
  account_name        = azurerm_cosmosdb_account.main.name
  database_name       = azurerm_cosmosdb_sql_database.main.name
  partition_key_paths = ["/id"]

  indexing_policy {
    indexing_mode = "consistent"

    included_path {
      path = "/*"
    }
  }
}

resource "azurerm_cosmosdb_sql_container" "project_members" {
  name                = "project_members"
  resource_group_name = var.resource_group_name
  account_name        = azurerm_cosmosdb_account.main.name
  database_name       = azurerm_cosmosdb_sql_database.main.name
  partition_key_paths = ["/projectId"]

  indexing_policy {
    indexing_mode = "consistent"

    included_path {
      path = "/*"
    }
  }
}

resource "azurerm_cosmosdb_sql_container" "scan_history" {
  name                = "scan_history"
  resource_group_name = var.resource_group_name
  account_name        = azurerm_cosmosdb_account.main.name
  database_name       = azurerm_cosmosdb_sql_database.main.name
  partition_key_paths = ["/projectId"]

  indexing_policy {
    indexing_mode = "consistent"

    included_path {
      path = "/*"
    }
  }
}

resource "azurerm_cosmosdb_sql_container" "scan_schedules" {
  name                = "scan_schedules"
  resource_group_name = var.resource_group_name
  account_name        = azurerm_cosmosdb_account.main.name
  database_name       = azurerm_cosmosdb_sql_database.main.name
  partition_key_paths = ["/projectId"]

  indexing_policy {
    indexing_mode = "consistent"

    included_path {
      path = "/*"
    }
  }
}

resource "azurerm_cosmosdb_sql_container" "alert_rules" {
  name                = "alert_rules"
  resource_group_name = var.resource_group_name
  account_name        = azurerm_cosmosdb_account.main.name
  database_name       = azurerm_cosmosdb_sql_database.main.name
  partition_key_paths = ["/projectId"]

  indexing_policy {
    indexing_mode = "consistent"

    included_path {
      path = "/*"
    }
  }
}

# ---------------------
# RBAC: Managed identity gets Cosmos DB Built-in Data Contributor
# ---------------------

resource "azurerm_cosmosdb_sql_role_assignment" "app_data_contributor" {
  for_each = local.cosmos_contributor_principal_ids

  resource_group_name = var.resource_group_name
  account_name        = azurerm_cosmosdb_account.main.name
  role_definition_id  = "${azurerm_cosmosdb_account.main.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002"
  principal_id        = each.value
  scope               = azurerm_cosmosdb_account.main.id
}

# ---------------------
# Azure Cache for Redis
# ---------------------

resource "azurerm_redis_cache" "main" {
  name                 = "redis-${var.project_name}-${var.environment}"
  location             = var.location
  resource_group_name  = var.resource_group_name
  capacity             = var.redis_capacity
  family               = var.redis_family
  sku_name             = var.redis_sku
  non_ssl_port_enabled = false
  minimum_tls_version  = "1.2"

  redis_configuration {}

  tags = var.tags
}

# ---------------------
# Immutable tenant evidence + audit storage
# ---------------------

resource "azurerm_storage_account" "tenant_evidence" {
  name                            = "stev${var.project_name}${var.environment}"
  location                        = var.location
  resource_group_name             = var.resource_group_name
  account_tier                    = "Standard"
  account_replication_type        = "ZRS"
  account_kind                    = "StorageV2"
  access_tier                     = "Hot"
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false
  shared_access_key_enabled       = true
  public_network_access_enabled   = var.tenant_evidence_storage_public_network_access_enabled

  blob_properties {
    versioning_enabled       = true
    change_feed_enabled      = true
    last_access_time_enabled = true

    delete_retention_policy {
      days = var.tenant_evidence_blob_delete_retention_days
    }

    container_delete_retention_policy {
      days = var.tenant_evidence_container_delete_retention_days
    }
  }

  immutable_storage_with_versioning {
    enabled = true
  }

  network_rules {
    default_action             = local.tenant_evidence_storage_default_action
    bypass                     = var.tenant_evidence_storage_allow_trusted_azure_services ? ["AzureServices"] : []
    ip_rules                   = var.tenant_evidence_storage_allowed_ip_ranges
    virtual_network_subnet_ids = var.tenant_evidence_storage_allowed_subnet_ids
  }

  tags = var.tags
}

resource "azurerm_storage_container" "access_snapshots" {
  name                  = "access-snapshots"
  storage_account_name  = azurerm_storage_account.tenant_evidence.name
  container_access_type = "private"
}

resource "azurerm_storage_container" "audit_archive" {
  name                  = "audit-archive"
  storage_account_name  = azurerm_storage_account.tenant_evidence.name
  container_access_type = "private"
}

resource "azurerm_storage_container" "tenant_evidence" {
  name                  = "tenant-evidence"
  storage_account_name  = azurerm_storage_account.tenant_evidence.name
  container_access_type = "private"
}

resource "azurerm_storage_queue" "tenant_evidence" {
  for_each             = local.tenant_evidence_queue_names
  name                 = each.value
  storage_account_name = azurerm_storage_account.tenant_evidence.name
}

resource "azurerm_role_assignment" "tenant_evidence_blob_contributor" {
  for_each = local.evidence_storage_principal_ids

  scope                = azurerm_storage_account.tenant_evidence.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = each.value
}

resource "azurerm_role_assignment" "tenant_evidence_queue_contributor" {
  for_each = local.evidence_storage_principal_ids

  scope                = azurerm_storage_account.tenant_evidence.id
  role_definition_name = "Storage Queue Data Contributor"
  principal_id         = each.value
}
