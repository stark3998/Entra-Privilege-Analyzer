# -----------------------------------------------------------------------------
# Module: compute
# ACR + Container App Environment + Container Apps (backend, frontend) + Jobs
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
# Azure Container Registry
# ---------------------

resource "azurerm_container_registry" "main" {
  name                = "${var.project_name}${var.environment}acr"
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = "Basic"
  admin_enabled       = false

  tags = var.tags
}

# RBAC: Managed identity can pull images from ACR
resource "azurerm_role_assignment" "acr_pull" {
  scope                = azurerm_container_registry.main.id
  role_definition_name = "AcrPull"
  principal_id         = var.managed_identity_principal_id
}

# ---------------------
# Container App Environment
# ---------------------

resource "azurerm_container_app_environment" "main" {
  name                       = "cae-${var.project_name}-${var.environment}"
  location                   = var.location
  resource_group_name        = var.resource_group_name
  log_analytics_workspace_id = var.log_analytics_workspace_id

  tags = var.tags

  lifecycle {
    ignore_changes = [
      log_analytics_workspace_id,
    ]
  }
}

# ---------------------
# Container App: Backend
# ---------------------

resource "azurerm_container_app" "backend" {
  name                         = "ca-${var.project_name}-backend-${var.environment}"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = var.resource_group_name
  revision_mode                = "Single"

  identity {
    type         = "UserAssigned"
    identity_ids = [var.managed_identity_id]
  }

  registry {
    server   = azurerm_container_registry.main.login_server
    identity = var.managed_identity_id
  }

  # Secrets sourced from Key Vault via managed identity
  secret {
    name                = "cosmos-key"
    key_vault_secret_id = var.secret_uris.cosmos_key
    identity            = var.managed_identity_id
  }

  secret {
    name                = "cosmos-endpoint"
    key_vault_secret_id = var.secret_uris.cosmos_endpoint
    identity            = var.managed_identity_id
  }

  secret {
    name                = "redis-password"
    key_vault_secret_id = var.secret_uris.redis_password
    identity            = var.managed_identity_id
  }

  secret {
    name                = "foundry-key"
    key_vault_secret_id = var.secret_uris.foundry_key
    identity            = var.managed_identity_id
  }

  secret {
    name                = "app-client-secret"
    key_vault_secret_id = var.secret_uris.app_client_secret
    identity            = var.managed_identity_id
  }

  secret {
    name                = "appinsights-connection-string"
    key_vault_secret_id = var.secret_uris.appinsights_conn_string
    identity            = var.managed_identity_id
  }

  secret {
    name                = "encryption-key"
    key_vault_secret_id = var.secret_uris.encryption_key
    identity            = var.managed_identity_id
  }

  secret {
    name                = "scan-function-key"
    key_vault_secret_id = var.secret_uris.scan_function_key
    identity            = var.managed_identity_id
  }

  template {
    min_replicas = 1
    max_replicas = 10

    container {
      name   = "backend"
      image  = "${azurerm_container_registry.main.login_server}/${var.project_name}-backend:${var.backend_image_tag}"
      cpu    = 0.5
      memory = "1Gi"

      # Plain env vars
      env {
        name  = "COSMOS_MASTER_DATABASE"
        value = var.cosmos_database_name
      }

      env {
        name  = "REDIS_HOST"
        value = var.redis_hostname
      }

      env {
        name  = "REDIS_PORT"
        value = tostring(var.redis_port)
      }

      env {
        name  = "REDIS_SSL"
        value = "true"
      }

      env {
        name  = "AZURE_CLIENT_ID"
        value = var.application_client_id
      }

      env {
        name  = "AZURE_TENANT_ID"
        value = var.tenant_id
      }

      env {
        name  = "CORS_ORIGIN_REGEX"
        value = var.cors_origin_regex
      }

      env {
        name  = "AZURE_FOUNDRY_ENDPOINT"
        value = var.foundry_endpoint
      }

      env {
        name  = "AZURE_FOUNDRY_MODEL"
        value = var.foundry_model
      }

      env {
        name  = "KEYVAULT_URL"
        value = var.key_vault_uri
      }

      # Secret env vars (references to Key Vault via Container App secrets)
      env {
        name        = "COSMOS_KEY"
        secret_name = "cosmos-key"
      }

      env {
        name        = "COSMOS_ENDPOINT"
        secret_name = "cosmos-endpoint"
      }

      env {
        name        = "REDIS_PASSWORD"
        secret_name = "redis-password"
      }

      env {
        name        = "AZURE_FOUNDRY_KEY"
        secret_name = "foundry-key"
      }

      env {
        name        = "AZURE_CLIENT_SECRET"
        secret_name = "app-client-secret"
      }

      env {
        name        = "APPLICATIONINSIGHTS_CONNECTION_STRING"
        secret_name = "appinsights-connection-string"
      }

      env {
        name        = "ENCRYPTION_KEY"
        secret_name = "encryption-key"
      }

      env {
        name        = "SCAN_FUNCTION_KEY"
        secret_name = "scan-function-key"
      }

      env {
        name  = "SCAN_FUNCTION_APP_URL"
        value = var.scan_function_app_url
      }

      env {
        name  = "LOG_FORMAT"
        value = "json"
      }

      # Liveness probe
      liveness_probe {
        transport = "HTTP"
        port      = 8000
        path      = "/healthz"
      }

      # Readiness probe
      readiness_probe {
        transport = "HTTP"
        port      = 8000
        path      = "/readyz"
      }
    }

    # HTTP scaling rule
    http_scale_rule {
      name                = "http-scaling"
      concurrent_requests = "50"
    }
  }

  ingress {
    external_enabled = true
    target_port      = 8000
    transport        = "http"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  tags = var.tags

  lifecycle {
    ignore_changes = [
      # Image tag is updated by CD pipeline, not Terraform
      template[0].container[0].image,
    ]
  }
}

# ---------------------
# Container App: Frontend
# ---------------------

resource "azurerm_container_app" "frontend" {
  name                         = "ca-${var.project_name}-frontend-${var.environment}"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = var.resource_group_name
  revision_mode                = "Single"

  identity {
    type         = "UserAssigned"
    identity_ids = [var.managed_identity_id]
  }

  registry {
    server   = azurerm_container_registry.main.login_server
    identity = var.managed_identity_id
  }

  template {
    min_replicas = 1
    max_replicas = 5

    container {
      name   = "frontend"
      image  = "${azurerm_container_registry.main.login_server}/${var.project_name}-frontend:${var.frontend_image_tag}"
      cpu    = 0.25
      memory = "0.5Gi"

      env {
        name  = "BACKEND_URL"
        value = "https://${azurerm_container_app.backend.ingress[0].fqdn}"
      }
    }

    # HTTP scaling rule
    http_scale_rule {
      name                = "http-scaling"
      concurrent_requests = "100"
    }
  }

  ingress {
    external_enabled = true
    target_port      = 80
    transport        = "http"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  tags = var.tags

  lifecycle {
    ignore_changes = [
      # Image tag is updated by CD pipeline, not Terraform
      template[0].container[0].image,
    ]
  }
}

# ---------------------
# Container App Jobs (scheduled)
# All jobs share the backend image with different commands.
# ---------------------

locals {
  scheduled_jobs = {
    sync-tenant = {
      schedule = "0 */6 * * *"
      command  = ["python", "-m", "jobs.sync_tenant"]
      name     = "sync-ten"
    }
    compute-baselines = {
      schedule = "0 2 * * *"
      command  = ["python", "-m", "jobs.compute_baselines"]
      name     = "comp-base"
    }
    detect-drift = {
      schedule = "0 3 * * *"
      command  = ["python", "-m", "jobs.detect_drift"]
      name     = "det-drift"
    }
    generate-recommendations = {
      schedule = "0 4 * * *"
      command  = ["python", "-m", "jobs.generate_recommendations"]
      name     = "gen-reco"
    }
    generate-narratives = {
      schedule = "0 5 * * *"
      command  = ["python", "-m", "jobs.generate_narratives"]
      name     = "gen-narr"
    }
  }
}

resource "azurerm_container_app_job" "scheduled" {
  for_each = local.scheduled_jobs

  name                         = "job-${var.project_name}-${each.value.name}-${var.environment}"
  location                     = var.location
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = var.resource_group_name
  replica_timeout_in_seconds   = 1800
  replica_retry_limit          = 1

  identity {
    type         = "UserAssigned"
    identity_ids = [var.managed_identity_id]
  }

  registry {
    server   = azurerm_container_registry.main.login_server
    identity = var.managed_identity_id
  }

  # Secrets (same as backend — jobs need the same data access)
  secret {
    name                = "cosmos-key"
    key_vault_secret_id = var.secret_uris.cosmos_key
    identity            = var.managed_identity_id
  }

  secret {
    name                = "cosmos-endpoint"
    key_vault_secret_id = var.secret_uris.cosmos_endpoint
    identity            = var.managed_identity_id
  }

  secret {
    name                = "redis-password"
    key_vault_secret_id = var.secret_uris.redis_password
    identity            = var.managed_identity_id
  }

  secret {
    name                = "foundry-key"
    key_vault_secret_id = var.secret_uris.foundry_key
    identity            = var.managed_identity_id
  }

  secret {
    name                = "appinsights-connection-string"
    key_vault_secret_id = var.secret_uris.appinsights_conn_string
    identity            = var.managed_identity_id
  }

  secret {
    name                = "encryption-key"
    key_vault_secret_id = var.secret_uris.encryption_key
    identity            = var.managed_identity_id
  }

  schedule_trigger_config {
    cron_expression          = each.value.schedule
    parallelism              = 1
    replica_completion_count = 1
  }

  template {
    container {
      name    = each.key
      image   = "${azurerm_container_registry.main.login_server}/${var.project_name}-backend:${var.backend_image_tag}"
      cpu     = 0.5
      memory  = "1Gi"
      command = each.value.command

      env {
        name  = "COSMOS_MASTER_DATABASE"
        value = var.cosmos_database_name
      }

      env {
        name  = "REDIS_HOST"
        value = var.redis_hostname
      }

      env {
        name  = "REDIS_PORT"
        value = tostring(var.redis_port)
      }

      env {
        name  = "REDIS_SSL"
        value = "true"
      }

      env {
        name  = "AZURE_FOUNDRY_ENDPOINT"
        value = var.foundry_endpoint
      }

      env {
        name  = "AZURE_FOUNDRY_MODEL"
        value = var.foundry_model
      }

      env {
        name        = "COSMOS_KEY"
        secret_name = "cosmos-key"
      }

      env {
        name        = "COSMOS_ENDPOINT"
        secret_name = "cosmos-endpoint"
      }

      env {
        name        = "REDIS_PASSWORD"
        secret_name = "redis-password"
      }

      env {
        name        = "AZURE_FOUNDRY_KEY"
        secret_name = "foundry-key"
      }

      env {
        name        = "APPLICATIONINSIGHTS_CONNECTION_STRING"
        secret_name = "appinsights-connection-string"
      }

      env {
        name        = "ENCRYPTION_KEY"
        secret_name = "encryption-key"
      }
    }
  }

  tags = var.tags

  lifecycle {
    ignore_changes = [
      # Image tag is updated by CD pipeline
      template[0].container[0].image,
    ]
  }
}
