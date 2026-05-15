# Remote state stored in Azure Blob Storage.
# The storage account is created by infra/bootstrap/main.tf.
terraform {
  backend "azurerm" {
    resource_group_name  = "rg-entraperm-tfstate"
    storage_account_name = "entrapermtfstate"
    container_name       = "tfstate"
    key                  = "prod.terraform.tfstate"
    use_azuread_auth     = true
    use_oidc             = true
  }
}
