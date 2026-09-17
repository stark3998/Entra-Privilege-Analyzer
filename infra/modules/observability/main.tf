# -----------------------------------------------------------------------------
# Module: observability
# Log Analytics workspace + Application Insights
# -----------------------------------------------------------------------------

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.116.0"
    }
  }
}

data "azurerm_resource_group" "main" {
  name = var.resource_group_name
}

locals {
  budget_start_date = "${formatdate("YYYY-MM", timestamp())}-01T00:00:00Z"
}

# ---------------------
# Log Analytics Workspace
# ---------------------

resource "azurerm_log_analytics_workspace" "main" {
  name                = "log-${var.project_name}-${var.environment}"
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = "PerGB2018"
  retention_in_days   = var.log_retention_days

  tags = var.tags
}

# ---------------------
# Application Insights (workspace-based)
# ---------------------

resource "azurerm_application_insights" "main" {
  name                = "appi-${var.project_name}-${var.environment}"
  location            = var.location
  resource_group_name = var.resource_group_name
  workspace_id        = azurerm_log_analytics_workspace.main.id
  application_type    = "web"

  tags = var.tags
}

resource "azurerm_consumption_budget_resource_group" "main" {
  count = var.monthly_budget_amount == null ? 0 : 1

  name              = "budget-${var.project_name}-${var.environment}"
  resource_group_id = data.azurerm_resource_group.main.id
  amount            = var.monthly_budget_amount
  time_grain        = "Monthly"

  time_period {
    start_date = local.budget_start_date
  }

  notification {
    enabled        = true
    threshold      = 80
    operator       = "GreaterThan"
    threshold_type = "Actual"
    contact_emails = var.budget_contact_emails
    contact_roles  = ["Owner"]
  }

  notification {
    enabled        = true
    threshold      = 100
    operator       = "GreaterThan"
    threshold_type = "Forecasted"
    contact_emails = var.budget_contact_emails
    contact_roles  = ["Owner"]
  }
}
