# -----------------------------------------------------------------------------
# Module: security
# Azure Key Vault with RBAC authorization + secret storage
# -----------------------------------------------------------------------------

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.116.0"
    }
  }
}

data "azurerm_client_config" "current" {}

locals {
  key_vault_default_action = var.public_network_access_enabled && length(var.allowed_ip_ranges) == 0 && length(var.allowed_subnet_ids) == 0 ? "Allow" : "Deny"
  key_vault_secrets_user_principal_ids = toset(compact(concat(
    [var.managed_identity_principal_id],
    var.additional_secrets_user_principal_ids,
  )))
}

# ---------------------
# Key Vault
# ---------------------

resource "azurerm_key_vault" "main" {
  name                       = "kv-${var.project_name}-${var.environment}"
  location                   = var.location
  resource_group_name        = var.resource_group_name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  enable_rbac_authorization  = true
  soft_delete_retention_days = var.soft_delete_retention_days
  purge_protection_enabled   = var.purge_protection_enabled
  public_network_access_enabled = var.public_network_access_enabled

  network_acls {
    bypass                     = var.allow_trusted_azure_services ? "AzureServices" : "None"
    default_action             = local.key_vault_default_action
    ip_rules                   = var.allowed_ip_ranges
    virtual_network_subnet_ids = var.allowed_subnet_ids
  }

  tags = var.tags
}

# ---------------------
# RBAC: Terraform deployer gets Key Vault Administrator
# ---------------------

resource "azurerm_role_assignment" "deployer_kv_admin" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Administrator"
  principal_id         = data.azurerm_client_config.current.object_id
}

# ---------------------
# RBAC: Managed identity gets Key Vault Secrets User (read-only)
# ---------------------

resource "azurerm_role_assignment" "app_kv_secrets_user" {
  for_each = local.key_vault_secrets_user_principal_ids

  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = each.value
}

# ---------------------
# Secrets
# ---------------------

resource "azurerm_key_vault_secret" "app_client_secret" {
  name         = "app-client-secret"
  value        = var.app_client_secret
  key_vault_id = azurerm_key_vault.main.id

  depends_on = [azurerm_role_assignment.deployer_kv_admin]
}

resource "azurerm_key_vault_secret" "cosmos_key" {
  name         = "cosmos-key"
  value        = var.cosmos_primary_key
  key_vault_id = azurerm_key_vault.main.id

  depends_on = [azurerm_role_assignment.deployer_kv_admin]
}

resource "azurerm_key_vault_secret" "cosmos_endpoint" {
  name         = "cosmos-endpoint"
  value        = var.cosmos_endpoint
  key_vault_id = azurerm_key_vault.main.id

  depends_on = [azurerm_role_assignment.deployer_kv_admin]
}

resource "azurerm_key_vault_secret" "redis_password" {
  name         = "redis-password"
  value        = var.redis_primary_key
  key_vault_id = azurerm_key_vault.main.id

  depends_on = [azurerm_role_assignment.deployer_kv_admin]
}

resource "azurerm_key_vault_secret" "foundry_key" {
  name         = "foundry-key"
  value        = var.foundry_key
  key_vault_id = azurerm_key_vault.main.id

  depends_on = [azurerm_role_assignment.deployer_kv_admin]
}

resource "azurerm_key_vault_secret" "appinsights_connection_string" {
  name         = "appinsights-connection-string"
  value        = var.appinsights_connection_string
  key_vault_id = azurerm_key_vault.main.id

  depends_on = [azurerm_role_assignment.deployer_kv_admin]
}

resource "azurerm_key_vault_secret" "encryption_key" {
  name         = "encryption-key"
  value        = var.encryption_key
  key_vault_id = azurerm_key_vault.main.id

  depends_on = [azurerm_role_assignment.deployer_kv_admin]
}

resource "azurerm_key_vault_secret" "scan_function_key" {
  name         = "scan-function-key"
  value        = var.scan_function_key
  key_vault_id = azurerm_key_vault.main.id

  depends_on = [azurerm_role_assignment.deployer_kv_admin]
}

resource "azurerm_key_vault_secret" "agent_function_key" {
  name         = "agent-function-key"
  value        = var.agent_function_key
  key_vault_id = azurerm_key_vault.main.id

  depends_on = [azurerm_role_assignment.deployer_kv_admin]
}

resource "azurerm_key_vault_secret" "collection_app_client_secret" {
  name         = "collection-app-client-secret"
  value        = var.collection_app_client_secret
  key_vault_id = azurerm_key_vault.main.id

  depends_on = [azurerm_role_assignment.deployer_kv_admin]
}

resource "azurerm_key_vault_secret" "mutation_app_client_secret" {
  name         = "mutation-app-client-secret"
  value        = var.mutation_app_client_secret
  key_vault_id = azurerm_key_vault.main.id

  depends_on = [azurerm_role_assignment.deployer_kv_admin]
}
