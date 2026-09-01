terraform {
  required_version = ">= 1.5.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.90.0"
    }
  }
}

provider "azurerm" {
  features {}
}

resource "azurerm_resource_group" "rg" {
  name     = "rg-claimsinsight-ai-prod"
  location = "australiaeast"
}

# 1. Azure Data Lake Gen2
resource "azurerm_storage_account" "datalake" {
  name                     = "stclaimsinsightlake"
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  is_hns_enabled           = true
}

resource "azurerm_storage_data_lake_gen2_filesystem" "containers" {
  for_each           = toset(["raw", "bronze", "silver", "gold"])
  name               = each.key
  storage_account_id = azurerm_storage_account.datalake.id
}

# 2. Azure Databricks Workspace
resource "azurerm_databricks_workspace" "databricks" {
  name                = "dbw-claimsinsight-prod"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  sku                 = "premium"
}

# 3. Azure AI Search Service
resource "azurerm_search_service" "search" {
  name                = "search-claimsinsight-prod"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  sku                 = "standard"
}

# 4. Azure Container Registry
resource "azurerm_container_registry" "acr" {
  name                = "claimsinsightcr"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  sku                 = "Standard"
  admin_enabled       = true
}

# 5. Azure Kubernetes Service (AKS)
resource "azurerm_kubernetes_cluster" "aks" {
  name                = "aks-claimsinsight-prod"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  dns_prefix          = "claimsinsight-aks"

  default_node_pool {
    name       = "systempool"
    node_count = 2
    vm_size    = "Standard_D2s_v5"
  }

  identity {
    type = "SystemAssigned"
  }
}