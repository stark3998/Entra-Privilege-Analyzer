# -----------------------------------------------------------------------------
# Root module: prod environment
# Composes all modules into a complete deployment.
# -----------------------------------------------------------------------------

locals {
  common_tags = merge(var.tags, {
    project     = "entra-permissions-analyzer"
    environment = var.environment
    managed_by  = "terraform"
  })

  resource_group_name = coalesce(var.existing_resource_group_name, try(azurerm_resource_group.main[0].name, null))
  agent_function_app_url = "https://${module.functions.function_app_hostname}"
}

# ---------------------
# Resource Group
# ---------------------

data "azurerm_resource_group" "existing" {
  count = var.existing_resource_group_name != null ? 1 : 0
  name  = var.existing_resource_group_name
}

resource "azurerm_resource_group" "main" {
  count    = var.existing_resource_group_name == null ? 1 : 0
  name     = "rg-${var.project_name}-${var.environment}"
  location = var.location
  tags     = local.common_tags
}

# ---------------------
# Observability (Log Analytics + App Insights)
# Created first — other modules depend on workspace ID and connection string.
# ---------------------

module "observability" {
  source = "../../modules/observability"

  project_name        = var.project_name
  environment         = var.environment
  location            = var.location
  resource_group_name = local.resource_group_name
  log_retention_days  = 90
  monthly_budget_amount = var.monthly_budget_amount
  budget_contact_emails = var.budget_contact_emails
  tags                = local.common_tags
}

# ---------------------
# Identity (Entra ID app + managed identity + OIDC federation)
# ---------------------

module "identity" {
  source = "../../modules/identity"

  project_name        = var.project_name
  environment         = var.environment
  location            = var.location
  resource_group_name = local.resource_group_name
  github_repository   = var.github_repository
  existing_application_client_id     = var.existing_application_client_id
  existing_application_client_secret = var.existing_application_client_secret

  spa_redirect_uris = [
    "http://localhost:5173",
    "https://access.jatinmadan.com",
  ]

  tags = local.common_tags
}

# ---------------------
# Data (Cosmos DB + Redis)
# ---------------------

module "data" {
  source = "../../modules/data"

  project_name                  = var.project_name
  environment                   = var.environment
  location                      = var.location
  resource_group_name           = local.resource_group_name
  managed_identity_principal_id = module.identity.managed_identity_principal_id
  collection_managed_identity_principal_id = module.identity.collection_managed_identity_principal_id
  mutation_managed_identity_principal_id   = module.identity.mutation_managed_identity_principal_id

  # Prod: Standard C1 Redis
  redis_sku      = "Standard"
  redis_family   = "C"
  redis_capacity = 1

  tenant_evidence_storage_public_network_access_enabled = var.tenant_evidence_storage_public_network_access_enabled
  tenant_evidence_storage_allowed_ip_ranges             = var.platform_allowed_ip_ranges
  tenant_evidence_storage_allowed_subnet_ids            = var.platform_allowed_subnet_ids
  tenant_evidence_storage_allow_trusted_azure_services  = var.allow_trusted_azure_services

  tags = local.common_tags
}

# ---------------------
# Security (Key Vault + secrets)
# ---------------------

module "security" {
  source = "../../modules/security"

  project_name                  = var.project_name
  environment                   = var.environment
  location                      = var.location
  resource_group_name           = local.resource_group_name
  managed_identity_principal_id = module.identity.managed_identity_principal_id
  additional_secrets_user_principal_ids = [
    module.identity.collection_managed_identity_principal_id,
    module.identity.mutation_managed_identity_principal_id,
  ]

  # Secrets to store
  app_client_secret             = module.identity.client_secret
  collection_app_client_secret  = module.identity.collection_client_secret
  mutation_app_client_secret    = module.identity.mutation_client_secret
  cosmos_primary_key            = module.data.cosmos_primary_key
  cosmos_endpoint               = module.data.cosmos_endpoint
  redis_primary_key             = module.data.redis_primary_key
  foundry_key                   = var.foundry_key
  appinsights_connection_string = module.observability.app_insights_connection_string
  encryption_key                = var.encryption_key
  scan_function_key             = var.scan_function_key
  agent_function_key            = var.agent_function_key
  purge_protection_enabled      = true
  soft_delete_retention_days    = 90
  public_network_access_enabled = var.key_vault_public_network_access_enabled
  allowed_ip_ranges             = var.platform_allowed_ip_ranges
  allowed_subnet_ids            = var.platform_allowed_subnet_ids
  allow_trusted_azure_services  = var.allow_trusted_azure_services

  tags = local.common_tags
}

# ---------------------
# Compute (ACR + Container Apps + Jobs)
# ---------------------

module "compute" {
  source = "../../modules/compute"

  project_name                  = var.project_name
  environment                   = var.environment
  location                      = var.location
  resource_group_name           = local.resource_group_name
  log_analytics_workspace_id    = module.observability.log_analytics_workspace_id
  managed_identity_id           = module.identity.managed_identity_id
  managed_identity_principal_id = module.identity.managed_identity_principal_id
  managed_identity_client_id    = module.identity.managed_identity_client_id
  collection_managed_identity_id        = module.identity.collection_managed_identity_id
  collection_managed_identity_client_id = module.identity.collection_managed_identity_client_id
  mutation_managed_identity_id          = module.identity.mutation_managed_identity_id
  mutation_managed_identity_client_id   = module.identity.mutation_managed_identity_client_id

  # Key Vault secret URIs for Container App secretRef
  secret_uris   = module.security.secret_uris
  key_vault_uri = module.security.key_vault_uri

  # App configuration
  application_client_id = module.identity.application_client_id
  tenant_id             = module.identity.tenant_id
  cors_origin_regex     = var.cors_origin_regex
  cosmos_database_name  = module.data.cosmos_database_name
  redis_hostname        = module.data.redis_hostname
  redis_port            = module.data.redis_port
  foundry_endpoint      = var.foundry_endpoint
  foundry_model         = var.foundry_model
  collection_application_client_id = module.identity.collection_application_client_id
  collection_credential_reference  = module.security.secret_uris.collection_app_secret
  mutation_application_client_id   = module.identity.mutation_application_client_id
  mutation_credential_reference    = module.security.secret_uris.mutation_app_secret
  tenant_evidence_raw_ttl_seconds  = var.tenant_evidence_raw_ttl_seconds
  tenant_evidence_storage_account_name    = module.data.tenant_evidence_storage_account_name
  tenant_evidence_blob_endpoint           = module.data.tenant_evidence_blob_endpoint
  tenant_evidence_queue_endpoint          = module.data.tenant_evidence_queue_endpoint
  tenant_evidence_snapshot_container_name = module.data.tenant_evidence_snapshot_container_name
  tenant_evidence_audit_container_name    = module.data.tenant_evidence_audit_container_name
  tenant_evidence_raw_container_name      = module.data.tenant_evidence_raw_container_name
  tenant_evidence_queue_names             = module.data.tenant_evidence_queue_names
  scan_function_app_url = "https://${module.functions.function_app_hostname}"
  agent_function_app_url = local.agent_function_app_url

  tags = local.common_tags
}

# ---------------------
# Functions (Durable Functions scan orchestration)
# ---------------------

module "functions" {
  source = "../../modules/functions"

  project_name        = var.project_name
  environment         = var.environment
  location            = var.location
  resource_group_name = local.resource_group_name

  managed_identity_id           = module.identity.managed_identity_id
  managed_identity_principal_id = module.identity.managed_identity_principal_id
  managed_identity_client_id    = module.identity.managed_identity_client_id
  collection_managed_identity_id        = module.identity.collection_managed_identity_id
  collection_managed_identity_client_id = module.identity.collection_managed_identity_client_id
  mutation_managed_identity_id          = module.identity.mutation_managed_identity_id
  mutation_managed_identity_client_id   = module.identity.mutation_managed_identity_client_id

  key_vault_uri        = module.security.key_vault_uri
  cosmos_database_name = module.data.cosmos_database_name

  secret_uris = {
    cosmos_endpoint = module.security.secret_uris.cosmos_endpoint
    cosmos_key      = module.security.secret_uris.cosmos_key
    encryption_key  = module.security.secret_uris.encryption_key
  }

  application_insights_connection_string = module.observability.app_insights_connection_string
  tenant_evidence_raw_ttl_seconds        = var.tenant_evidence_raw_ttl_seconds
  tenant_evidence_storage_account_name    = module.data.tenant_evidence_storage_account_name
  tenant_evidence_blob_endpoint           = module.data.tenant_evidence_blob_endpoint
  tenant_evidence_queue_endpoint          = module.data.tenant_evidence_queue_endpoint
  tenant_evidence_snapshot_container_name = module.data.tenant_evidence_snapshot_container_name
  tenant_evidence_audit_container_name    = module.data.tenant_evidence_audit_container_name
  tenant_evidence_raw_container_name      = module.data.tenant_evidence_raw_container_name
  tenant_evidence_queue_names             = module.data.tenant_evidence_queue_names
  durable_task_hub_name                   = "EntraPermScanHub"
  agent_runtime_enabled                   = true
  foundry_project_endpoint                = var.foundry_endpoint
  public_network_access_enabled           = var.functions_storage_public_network_access_enabled
  allowed_ip_ranges                       = var.platform_allowed_ip_ranges
  allowed_subnet_ids                      = var.platform_allowed_subnet_ids
  allow_trusted_azure_services            = var.allow_trusted_azure_services

  tags = local.common_tags
}

locals {
  diagnostic_targets = {
    acr               = module.compute.acr_id
    backend           = module.compute.backend_container_app_id
    frontend          = module.compute.frontend_container_app_id
    "container-env"   = module.compute.container_app_environment_id
    cosmos            = module.data.cosmos_account_id
    "function-app"    = module.functions.function_app_id
    "function-store"  = module.functions.storage_account_id
    "key-vault"       = module.security.key_vault_id
    "tenant-evidence" = module.data.tenant_evidence_storage_account_id
  }
}

resource "azurerm_monitor_diagnostic_setting" "resource_logs" {
  for_each = local.diagnostic_targets

  name                       = "diag-${each.key}"
  target_resource_id         = each.value
  log_analytics_workspace_id = module.observability.log_analytics_workspace_id

  enabled_log {
    category_group = "allLogs"
  }

  metric {
    category = "AllMetrics"
    enabled  = true
  }
}
