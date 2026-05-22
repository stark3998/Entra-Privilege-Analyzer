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

  # Prod: Standard C1 Redis
  redis_sku      = "Standard"
  redis_family   = "C"
  redis_capacity = 1

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

  # Secrets to store
  app_client_secret             = module.identity.client_secret
  cosmos_primary_key            = module.data.cosmos_primary_key
  cosmos_endpoint               = module.data.cosmos_endpoint
  redis_primary_key             = module.data.redis_primary_key
  foundry_key                   = var.foundry_key
  appinsights_connection_string = module.observability.app_insights_connection_string
  encryption_key                = var.encryption_key
  scan_function_key             = var.scan_function_key

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
  scan_function_app_url = "https://${module.functions.function_app_hostname}"

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

  key_vault_uri        = module.security.key_vault_uri
  cosmos_database_name = module.data.cosmos_database_name

  secret_uris = {
    cosmos_endpoint = module.security.secret_uris.cosmos_endpoint
    cosmos_key      = module.security.secret_uris.cosmos_key
  }

  application_insights_connection_string = module.observability.app_insights_connection_string

  tags = local.common_tags
}
