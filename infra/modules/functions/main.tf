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
  }
}

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
# Service Plan (Flex Consumption)
# ---------------------

resource "azurerm_service_plan" "functions" {
  name                = "asp-${var.project_name}-func-${var.environment}"
  location            = var.location
  resource_group_name = var.resource_group_name
  os_type             = "Linux"
  sku_name            = "FC1"

  tags = var.tags
}

# ---------------------
# Function App: Scan Orchestrator
# ---------------------

resource "azurerm_linux_function_app" "scan" {
  name                       = "func-${var.project_name}-scan-${var.environment}"
  location                   = var.location
  resource_group_name        = var.resource_group_name
  service_plan_id            = azurerm_service_plan.functions.id
  storage_account_name       = azurerm_storage_account.functions.name
  storage_account_access_key = azurerm_storage_account.functions.primary_access_key

  identity {
    type         = "UserAssigned"
    identity_ids = [var.managed_identity_id]
  }

  key_vault_reference_identity_id = var.managed_identity_id

  site_config {
    application_stack {
      python_version = "3.12"
    }

    # Flex Consumption scaling settings
    app_scale_limit = var.maximum_instance_count
  }

  app_settings = {
    # --- Storage (required by Functions runtime) ---
    AzureWebJobsStorage = azurerm_storage_account.functions.primary_connection_string

    # --- Cosmos DB (Key Vault references) ---
    COSMOS_ENDPOINT = "@Microsoft.KeyVault(SecretUri=${var.secret_uris["cosmos_endpoint"]})"
    COSMOS_KEY      = "@Microsoft.KeyVault(SecretUri=${var.secret_uris["cosmos_key"]})"

    # --- Cosmos DB (plain) ---
    COSMOS_DATABASE = var.cosmos_database_name

    # --- Observability ---
    APPLICATIONINSIGHTS_CONNECTION_STRING = var.application_insights_connection_string

    # --- Functions runtime ---
    FUNCTIONS_WORKER_RUNTIME   = "python"
    AzureWebJobsFeatureFlags   = "EnableWorkerIndexing"

    # --- Flex Consumption: always-ready instances to avoid cold starts ---
    WEBSITE_FLEXCONSUMPTION_ALWAYS_READY_INSTANCES = tostring(var.always_ready_instances)
  }

  tags = var.tags

  lifecycle {
    ignore_changes = [
      # App settings may be updated by deployment scripts outside Terraform
      app_settings["WEBSITE_RUN_FROM_PACKAGE"],
    ]
  }
}
