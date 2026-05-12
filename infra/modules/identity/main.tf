# -----------------------------------------------------------------------------
# Module: identity
# Entra ID app registration (multi-tenant) + managed identity for Container Apps
# -----------------------------------------------------------------------------

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.116.0"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 2.53.0"
    }
  }
}

# ---------------------
# Data sources
# ---------------------

data "azuread_client_config" "current" {}

# Microsoft Graph well-known app ID
data "azuread_application_published_app_ids" "well_known" {}

data "azuread_service_principal" "msgraph" {
  client_id = data.azuread_application_published_app_ids.well_known.result["MicrosoftGraph"]
}

# ---------------------
# Entra ID Application (multi-tenant)
# ---------------------

resource "azuread_application" "app" {
  display_name     = "${var.project_name}-${var.environment}"
  sign_in_audience = "AzureADMultipleOrgs"

  owners = [data.azuread_client_config.current.object_id]

  # App roles for RBAC
  app_role {
    allowed_member_types = ["User"]
    description          = "Security engineers — drift alerts, identity deep-dive, action timeline"
    display_name         = "SecurityEngineer"
    enabled              = true
    id                   = "a1b2c3d4-e5f6-7890-abcd-100000000001"
    value                = "SecurityEngineer"
  }

  app_role {
    allowed_member_types = ["User"]
    description          = "IAM administrators — recommendations, exports, best practices, settings"
    display_name         = "IAMAdmin"
    enabled              = true
    id                   = "a1b2c3d4-e5f6-7890-abcd-100000000002"
    value                = "IAMAdmin"
  }

  app_role {
    allowed_member_types = ["User"]
    description          = "Executives — dashboard, summary views, reports"
    display_name         = "Executive"
    enabled              = true
    id                   = "a1b2c3d4-e5f6-7890-abcd-100000000003"
    value                = "Executive"
  }

  # Required Microsoft Graph API permissions (delegated + application)
  required_resource_access {
    resource_app_id = data.azuread_application_published_app_ids.well_known.result["MicrosoftGraph"]

    # Delegated: User.Read (sign-in)
    resource_access {
      id   = data.azuread_service_principal.msgraph.oauth2_permission_scope_ids["User.Read"]
      type = "Scope"
    }

    # Application: User.Read.All
    resource_access {
      id   = data.azuread_service_principal.msgraph.app_role_ids["User.Read.All"]
      type = "Role"
    }

    # Application: Directory.Read.All
    resource_access {
      id   = data.azuread_service_principal.msgraph.app_role_ids["Directory.Read.All"]
      type = "Role"
    }

    # Application: AuditLog.Read.All
    resource_access {
      id   = data.azuread_service_principal.msgraph.app_role_ids["AuditLog.Read.All"]
      type = "Role"
    }

    # Application: RoleManagement.Read.All
    resource_access {
      id   = data.azuread_service_principal.msgraph.app_role_ids["RoleManagement.Read.All"]
      type = "Role"
    }

    # Application: Application.Read.All
    resource_access {
      id   = data.azuread_service_principal.msgraph.app_role_ids["Application.Read.All"]
      type = "Role"
    }
  }

  web {
    redirect_uris = var.redirect_uris

    implicit_grant {
      access_token_issuance_enabled = false
      id_token_issuance_enabled     = true
    }
  }

  single_page_application {
    redirect_uris = var.spa_redirect_uris
  }

  lifecycle {
    ignore_changes = [
      # Owners may change outside Terraform when admins are added
      owners,
    ]
  }
}

# ---------------------
# Service Principal
# ---------------------

resource "azuread_service_principal" "app" {
  client_id                    = azuread_application.app.client_id
  app_role_assignment_required = false

  owners = [data.azuread_client_config.current.object_id]
}

# ---------------------
# Client Secret (stored in Key Vault by the security module)
# ---------------------

resource "azuread_application_password" "app" {
  application_id = azuread_application.app.id
  display_name   = "terraform-managed-${var.environment}"
  end_date       = timeadd(timestamp(), "8760h") # 1 year

  lifecycle {
    ignore_changes = [end_date]
  }
}

# ---------------------
# User-Assigned Managed Identity (for Container Apps)
# ---------------------

resource "azurerm_user_assigned_identity" "app" {
  name                = "id-${var.project_name}-${var.environment}"
  location            = var.location
  resource_group_name = var.resource_group_name

  tags = var.tags
}

# ---------------------
# Federated credential for GitHub Actions OIDC
# ---------------------

resource "azuread_application_federated_identity_credential" "github_main" {
  application_id = azuread_application.app.id
  display_name   = "github-actions-main"
  description    = "GitHub Actions OIDC for main branch deployments"
  audiences      = ["api://AzureADTokenExchange"]
  issuer         = "https://token.actions.githubusercontent.com"
  subject        = "repo:${var.github_repository}:ref:refs/heads/main"
}

resource "azuread_application_federated_identity_credential" "github_pr" {
  application_id = azuread_application.app.id
  display_name   = "github-actions-pr"
  description    = "GitHub Actions OIDC for pull request workflows"
  audiences      = ["api://AzureADTokenExchange"]
  issuer         = "https://token.actions.githubusercontent.com"
  subject        = "repo:${var.github_repository}:environment:prod"
}
