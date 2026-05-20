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

# ---------------------
# Storage Account (Durable Functions Task Hub)
# ---------------------

resource "azurerm_storage_account" "functions" {
  name                     = "stfunc${var.project_name}${var.environment}"
  location                 = var.location
  resource_group_name      = var.resource_group_name
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"

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
    identity_ids = [var.managed_identity_id]
  }

  body = jsonencode({
    kind = "functionapp,linux"
    properties = {
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
      httpsOnly = false
    }
  })

  response_export_values = ["id", "name", "properties.defaultHostName"]
}

resource "azapi_update_resource" "scan_appsettings" {
  type      = "Microsoft.Web/sites/config@2023-12-01"
  name      = "appsettings"
  parent_id = azapi_resource.scan.id

  body = jsonencode({
    properties = {
      DEPLOYMENT_STORAGE_CONNECTION_STRING           = azurerm_storage_account.functions.primary_connection_string
      COSMOS_ENDPOINT                                = "@Microsoft.KeyVault(SecretUri=${var.secret_uris["cosmos_endpoint"]})"
      COSMOS_KEY                                     = "@Microsoft.KeyVault(SecretUri=${var.secret_uris["cosmos_key"]})"
      COSMOS_DATABASE                                = var.cosmos_database_name
      APPLICATIONINSIGHTS_CONNECTION_STRING          = var.application_insights_connection_string
      AzureWebJobsFeatureFlags                       = "EnableWorkerIndexing"
      WEBSITE_FLEXCONSUMPTION_ALWAYS_READY_INSTANCES = tostring(var.always_ready_instances)
    }
  })

  depends_on = [azapi_resource.scan]
}
