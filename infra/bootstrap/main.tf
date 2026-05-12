# -----------------------------------------------------------------------------
# Bootstrap: Remote state backend for Terraform
# Run once manually: terraform init && terraform apply
# This creates the Azure Storage Account used by all environment configs.
# -----------------------------------------------------------------------------

terraform {
  required_version = ">= 1.5.0"

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

provider "azurerm" {
  features {}
}

# ---------------------
# Variables
# ---------------------

variable "project_name" {
  description = "Short project name used in resource naming"
  type        = string
  default     = "entraperm"
}

variable "location" {
  description = "Azure region for bootstrap resources"
  type        = string
  default     = "eastus2"
}

variable "tags" {
  description = "Tags applied to all bootstrap resources"
  type        = map(string)
  default = {
    project    = "entra-permissions-analyzer"
    managed_by = "terraform"
    purpose    = "tfstate-backend"
  }
}

# ---------------------
# Resource Group
# ---------------------

resource "azurerm_resource_group" "tfstate" {
  name     = "rg-${var.project_name}-tfstate"
  location = var.location
  tags     = var.tags
}

# ---------------------
# Storage Account for remote state
# ---------------------

resource "azurerm_storage_account" "tfstate" {
  name                            = "${var.project_name}tfstate"
  resource_group_name             = azurerm_resource_group.tfstate.name
  location                        = azurerm_resource_group.tfstate.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false

  blob_properties {
    versioning_enabled = true
  }

  tags = var.tags
}

resource "azurerm_storage_container" "tfstate" {
  name                  = "tfstate"
  storage_account_name  = azurerm_storage_account.tfstate.name
  container_access_type = "private"
}

# ---------------------
# Outputs
# ---------------------

output "resource_group_name" {
  description = "Resource group containing the state backend"
  value       = azurerm_resource_group.tfstate.name
}

output "storage_account_name" {
  description = "Storage account name for terraform backend config"
  value       = azurerm_storage_account.tfstate.name
}

output "container_name" {
  description = "Blob container name for terraform backend config"
  value       = azurerm_storage_container.tfstate.name
}
