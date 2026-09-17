# -----------------------------------------------------------------------------
# Module: functions
# Azure Functions (Flex Consumption, Python 3.12) for Durable Functions scan
# orchestrations.
#
# NOTE: The scan_staging Cosmos container (PK /scanId, TTL 24h) is NOT created
# here -- it belongs in the data module alongside the other Cosmos containers.
#
# NOTE: Key Vault Secrets User RBAC for the managed identity is already granted
# in the security module (azurerm_role_assignment.app_kv_secrets_user). The same
# identity is shared with the backend Container App, so no additional role
# assignment is needed here.
# -----------------------------------------------------------------------------

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.116.0"
    }
    azapi = {
      source  = "Azure/azapi"
      version = "~> 1.14.0"
    }
  }
}

data "azurerm_client_config" "current" {}

locals {
  assigned_identity_ids = compact([
    var.managed_identity_id,
    var.collection_managed_identity_id,
    var.mutation_managed_identity_id,
  ])
  storage_default_action = var.public_network_access_enabled && length(var.allowed_ip_ranges) == 0 && length(var.allowed_subnet_ids) == 0 ? "Allow" : "Deny"
  telemetry_resource_attributes = join(",", [
    "service.namespace=entra-privilege-analyzer",
    "cloud.provider=azure",
    "deployment.environment=${var.environment}",
    "service.instance.id=func-${var.project_name}-scan-${var.environment}",
  ])
}

# ---------------------
# Storage Account (Durable Functions Task Hub)
# ---------------------

resource "azurerm_storage_account" "functions" {
  name                            = "stfunc${var.project_name}${var.environment}"
  location                        = var.location
  resource_group_name             = var.resource_group_name
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  account_kind                    = "StorageV2"
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false
  public_network_access_enabled   = var.public_network_access_enabled

  blob_properties {
    versioning_enabled = true
  }

  network_rules {
    default_action             = local.storage_default_action
    bypass                     = var.allow_trusted_azure_services ? ["AzureServices"] : []
    ip_rules                   = var.allowed_ip_ranges
    virtual_network_subnet_ids = var.allowed_subnet_ids
  }

  # Durable Functions stores orchestration state, history, and work items here.
  # LRS is sufficient -- orchestration state is transient and can be rebuilt.

  tags = var.tags
}

# ---------------------
# Flex deployment container for zip packages
# ---------------------

resource "azurerm_storage_container" "deployment" {
  name                 = "app-package-func${var.project_name}scan${var.environment}"
  storage_account_name = azurerm_storage_account.functions.name
  container_access_type = "private"
}

# Flex Consumption still requires a dedicated FC1 Linux plan id at creation.
resource "azurerm_service_plan" "functions" {
  name                = "asp-${var.project_name}-functions-${var.environment}"
  location            = var.location
  resource_group_name = var.resource_group_name
  os_type             = "Linux"
  sku_name            = "FC1"

  tags = var.tags
}

# ---------------------
# Function App: Scan Orchestrator (Flex Consumption)
# ---------------------

resource "azapi_resource" "scan" {
  type      = "Microsoft.Web/sites@2023-12-01"
  name      = "func-${var.project_name}-scan-${var.environment}"
  location  = var.location
  parent_id = "/subscriptions/${data.azurerm_client_config.current.subscription_id}/resourceGroups/${var.resource_group_name}"

  identity {
    type         = "UserAssigned"
    identity_ids = local.assigned_identity_ids
  }

  body = jsonencode({
    kind = "functionapp,linux"
    properties = {
      serverFarmId = replace(azurerm_service_plan.functions.id, "serverFarms", "serverfarms")
      keyVaultReferenceIdentity = var.managed_identity_id
      functionAppConfig = {
        deployment = {
          storage = {
            type  = "blobContainer"
            value = "${azurerm_storage_account.functions.primary_blob_endpoint}${azurerm_storage_container.deployment.name}"
            authentication = {
              type                               = "StorageAccountConnectionString"
              storageAccountConnectionStringName = "DEPLOYMENT_STORAGE_CONNECTION_STRING"
            }
          }
        }
        runtime = {
          name    = "python"
          version = "3.12"
        }
        scaleAndConcurrency = {
          instanceMemoryMB     = 2048
          maximumInstanceCount = var.maximum_instance_count
          alwaysReady          = []
        }
      }
      httpsOnly = true
    }
  })

}

resource "azapi_update_resource" "scan_appsettings" {
  type      = "Microsoft.Web/sites/config@2023-12-01"
  name      = "appsettings"
  parent_id = azapi_resource.scan.id

  body = jsonencode({
    properties = {
      DEPLOYMENT_STORAGE_CONNECTION_STRING           = azurerm_storage_account.functions.primary_connection_string
      AzureWebJobsStorage                            = azurerm_storage_account.functions.primary_connection_string
      COSMOS_ENDPOINT                                = "@Microsoft.KeyVault(SecretUri=${var.secret_uris["cosmos_endpoint"]})"
      COSMOS_KEY                                     = "@Microsoft.KeyVault(SecretUri=${var.secret_uris["cosmos_key"]})"
      COSMOS_DATABASE                                = var.cosmos_database_name
      COSMOS_MASTER_DATABASE                         = var.cosmos_database_name
      ENCRYPTION_KEY                                 = "@Microsoft.KeyVault(SecretUri=${var.secret_uris["encryption_key"]})"
      APPLICATIONINSIGHTS_CONNECTION_STRING          = var.application_insights_connection_string
      FUNCTIONS_WORKER_RUNTIME                       = "python"
      AzureWebJobsFeatureFlags                       = "EnableWorkerIndexing"
      AGENT_RUNTIME_ENABLED                          = tostring(var.agent_runtime_enabled)
      FOUNDRY_PROJECT_ENDPOINT                       = var.foundry_project_endpoint
      DURABLE_TASK_HUB_NAME                          = var.durable_task_hub_name
      AzureFunctionsJobHost__extensions__durableTask__hubName = var.durable_task_hub_name
      AzureFunctionsJobHost__extensions__durableTask__maxConcurrentActivityFunctions = tostring(var.maximum_instance_count)
      AzureFunctionsJobHost__extensions__durableTask__maxConcurrentOrchestratorFunctions = tostring(max(1, floor(var.maximum_instance_count / 2)))
      WEBSITE_FLEXCONSUMPTION_ALWAYS_READY_INSTANCES = tostring(var.always_ready_instances)
      MANAGED_IDENTITY_CLIENT_ID                     = var.managed_identity_client_id
      COLLECTION_MANAGED_IDENTITY_CLIENT_ID          = coalesce(var.collection_managed_identity_client_id, "")
      MUTATION_MANAGED_IDENTITY_CLIENT_ID            = coalesce(var.mutation_managed_identity_client_id, "")
      TENANT_EVIDENCE_RAW_TTL_SECONDS                = tostring(var.tenant_evidence_raw_ttl_seconds)
      TENANT_EVIDENCE_STORAGE_ACCOUNT                = var.tenant_evidence_storage_account_name
      TENANT_EVIDENCE_BLOB_ENDPOINT                  = var.tenant_evidence_blob_endpoint
      TENANT_EVIDENCE_QUEUE_ENDPOINT                 = var.tenant_evidence_queue_endpoint
      ACCESS_SNAPSHOT_CONTAINER                      = var.tenant_evidence_snapshot_container_name
      AUDIT_ARCHIVE_CONTAINER                        = var.tenant_evidence_audit_container_name
      TENANT_EVIDENCE_CONTAINER                      = var.tenant_evidence_raw_container_name
      TENANT_EVIDENCE_QUEUE                          = var.tenant_evidence_queue_names.collection
      TENANT_EVIDENCE_DEAD_LETTER_QUEUE              = var.tenant_evidence_queue_names.collection_deadletter
      MUTATION_QUEUE                                 = var.tenant_evidence_queue_names.mutation
      MUTATION_DEAD_LETTER_QUEUE                     = var.tenant_evidence_queue_names.mutation_deadletter
      AGENT_WORK_QUEUE                               = var.tenant_evidence_queue_names.agent
      AGENT_WORK_DEAD_LETTER_QUEUE                   = var.tenant_evidence_queue_names.agent_deadletter
      OTEL_SERVICE_NAME                              = "entra-permissions-analyzer-functions"
      OTEL_RESOURCE_ATTRIBUTES                       = local.telemetry_resource_attributes
    }
  })

  depends_on = [azapi_resource.scan]
}
