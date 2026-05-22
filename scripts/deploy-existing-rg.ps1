[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ResourceGroupName,

    [Parameter(Mandatory = $true)]
    [string]$ExistingApplicationClientId,

    [Parameter(Mandatory = $true)]
    [string]$ExistingApplicationClientSecret,

    [Parameter(Mandatory = $true)]
    [string]$FoundryEndpoint,

    [Parameter(Mandatory = $true)]
    [string]$FoundryKey,

    [Parameter(Mandatory = $true)]
    [string]$GitHubRepository,

    [string]$Location = "eastus",
    [string]$ProjectName = "entraperm",
    [string]$Environment = "prod",
    [string]$FoundryModel = "gpt-4.1-mini",
    [string]$FrontendImageTag,
    [string]$EncryptionKey,
    [switch]$BootstrapAdoption,
    [switch]$EnableLocalMode,
    [switch]$SkipBootstrapBuild,
    [switch]$SkipFrontendRedeploy,
    [switch]$SkipSmokeTests
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Invoke-Terraform {
    param(
        [string]$WorkingDirectory,
        [string[]]$Arguments
    )

    Push-Location $WorkingDirectory
    try {
        & terraform @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "terraform $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }
}

function Get-TerraformOutputValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$WorkingDirectory,

        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    Push-Location $WorkingDirectory
    try {
        $output = & terraform output -raw $Name
        if ($LASTEXITCODE -ne 0) {
            throw "terraform output -raw $Name failed with exit code $LASTEXITCODE"
        }

        return ($output | Out-String).Trim()
    }
    finally {
        Pop-Location
    }
}

function Get-TerraformStateList {
    param([Parameter(Mandatory = $true)][string]$WorkingDirectory)

    Push-Location $WorkingDirectory
    try {
        $output = & terraform state list 2>$null
        if ($LASTEXITCODE -ne 0) {
            return @()
        }

        return @($output | Where-Object { $_ -and $_.Trim() })
    }
    finally {
        Pop-Location
    }
}

function Test-TerraformStateAddress {
    param(
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [Parameter(Mandatory = $true)][string]$Address
    )

    return (Get-TerraformStateList -WorkingDirectory $WorkingDirectory) -contains $Address
}

function Invoke-AzCli {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [switch]$AllowFailure
    )

    $output = & az @Arguments 2>$null
    if ($LASTEXITCODE -ne 0) {
        if ($AllowFailure) {
            return $null
        }

        throw "az $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
    }

    if ($null -eq $output) {
        return $null
    }

    $text = ($output | Out-String).Trim()
    if ([string]::IsNullOrWhiteSpace($text)) {
        return $null
    }

    return $text
}

function Update-ContainerAppEnvVars {
    param(
        [Parameter(Mandatory = $true)][string]$AppName,
        [Parameter(Mandatory = $true)][string]$ResourceGroupName,
        [Parameter(Mandatory = $true)][string[]]$EnvVars
    )

    if (-not $EnvVars -or $EnvVars.Count -eq 0) {
        return
    }

    & az containerapp update --name $AppName --resource-group $ResourceGroupName --set-env-vars @EnvVars | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Container App runtime env var update failed for $AppName"
    }
}

function Import-TerraformResource {
    param(
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [Parameter(Mandatory = $true)][string]$Address,
        [Parameter(Mandatory = $true)][string]$ResourceId,
        [System.Collections.Generic.HashSet[string]]$KnownAddresses
    )

    if ($KnownAddresses) {
        if ($KnownAddresses.Contains($Address)) {
            return
        }
    }
    elseif (Test-TerraformStateAddress -WorkingDirectory $WorkingDirectory -Address $Address) {
        return
    }

    Write-Host "Importing $Address" -ForegroundColor DarkCyan
    Invoke-Terraform -WorkingDirectory $WorkingDirectory -Arguments @("import", "-input=false", $Address, $ResourceId)
    if ($KnownAddresses) {
        [void]$KnownAddresses.Add($Address)
    }
}

function Import-TerraformResourceIfIdPresent {
    param(
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [Parameter(Mandatory = $true)][string]$Address,
        [string]$ResourceId,
        [System.Collections.Generic.HashSet[string]]$KnownAddresses
    )

    if ([string]::IsNullOrWhiteSpace($ResourceId)) {
        Write-Host "Skipping $Address (resource not found in Azure)" -ForegroundColor DarkYellow
        return
    }

    Import-TerraformResource -WorkingDirectory $WorkingDirectory -Address $Address -ResourceId $ResourceId -KnownAddresses $KnownAddresses
}

function Resolve-AzureResourceId {
    param([string]$ResourceId)

    if ([string]::IsNullOrWhiteSpace($ResourceId)) {
        return $ResourceId
    }

    $normalized = $ResourceId
    $providerNamespaces = @(
        'Microsoft.Insights',
        'Microsoft.OperationalInsights',
        'Microsoft.ManagedIdentity',
        'Microsoft.DocumentDB',
        'Microsoft.Cache',
        'Microsoft.KeyVault',
        'Microsoft.ContainerRegistry',
        'Microsoft.App'
    )

    foreach ($namespace in $providerNamespaces) {
        $pattern = '/providers/' + [regex]::Escape($namespace)
        $normalized = [regex]::Replace($normalized, $pattern, "/providers/$namespace", [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    }

    $normalized = [regex]::Replace(
        $normalized,
        '/resourcegroups/',
        '/resourceGroups/',
        [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
    )

    $segmentMappings = @{
        '/containerapps/'       = '/containerApps/'
        '/managedenvironments/' = '/managedEnvironments/'
        '/sqldatabases/'        = '/sqlDatabases/'
        '/redis/'               = '/redis/'
    }

    foreach ($segment in $segmentMappings.Keys) {
        $normalized = [regex]::Replace($normalized, [regex]::Escape($segment), $segmentMappings[$segment], [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    }

    return $normalized
}

function Get-AzResourceId {
    param(
        [Parameter(Mandatory = $true)][string]$ResourceGroupName,
        [Parameter(Mandatory = $true)][string]$ResourceType,
        [Parameter(Mandatory = $true)][string]$Name
    )

    Write-Host "Lookup resource: $ResourceType :: $Name" -ForegroundColor DarkGray
    $resourceId = Invoke-AzCli -Arguments @("resource", "show", "--resource-group", $ResourceGroupName, "--resource-type", $ResourceType, "--name", $Name, "--query", "id", "--output", "tsv") -AllowFailure
    return Resolve-AzureResourceId -ResourceId $resourceId
}

function Get-RoleAssignmentId {
    param(
        [string]$Scope,
        [string]$PrincipalId,
        [Parameter(Mandatory = $true)][string]$RoleDefinitionName
    )

    if ([string]::IsNullOrWhiteSpace($Scope) -or [string]::IsNullOrWhiteSpace($PrincipalId)) {
        return $null
    }

    Write-Host "Lookup role assignment: $RoleDefinitionName" -ForegroundColor DarkGray
    return Invoke-AzCli -Arguments @(
        "role", "assignment", "list",
        "--scope", $Scope,
        "--assignee-object-id", $PrincipalId,
        "--role", $RoleDefinitionName,
        "--query", "[0].id",
        "--output", "tsv"
    ) -AllowFailure
}

function Get-KeyVaultSecretId {
    param(
        [Parameter(Mandatory = $true)][string]$VaultName,
        [Parameter(Mandatory = $true)][string]$SecretName
    )

    Write-Host "Lookup key vault secret: $SecretName" -ForegroundColor DarkGray
    $secretId = Invoke-AzCli -Arguments @("keyvault", "secret", "show", "--vault-name", $VaultName, "--name", $SecretName, "--query", "id", "--output", "tsv") -AllowFailure
    return Resolve-AzureResourceId -ResourceId $secretId
}

function Get-CosmosSqlRoleAssignmentId {
    param(
        [string]$ResourceGroupName,
        [string]$AccountName,
        [string]$PrincipalId
    )

    if ([string]::IsNullOrWhiteSpace($ResourceGroupName) -or [string]::IsNullOrWhiteSpace($AccountName) -or [string]::IsNullOrWhiteSpace($PrincipalId)) {
        return $null
    }

    Write-Host "Lookup Cosmos SQL role assignment" -ForegroundColor DarkGray
    return Invoke-AzCli -Arguments @(
        "cosmosdb", "sql", "role", "assignment", "list",
        "--resource-group", $ResourceGroupName,
        "--account-name", $AccountName,
        "--query", "[?principalId=='$PrincipalId' && contains(roleDefinitionId, '00000000-0000-0000-0000-000000000002')].id | [0]",
        "--output", "tsv"
    ) -AllowFailure
}

function Get-CosmosSqlDatabaseId {
    param(
        [string]$ResourceGroupName,
        [string]$AccountName,
        [string]$DatabaseName
    )

    if ([string]::IsNullOrWhiteSpace($ResourceGroupName) -or [string]::IsNullOrWhiteSpace($AccountName) -or [string]::IsNullOrWhiteSpace($DatabaseName)) {
        return $null
    }

    Write-Host "Lookup Cosmos SQL database: $DatabaseName" -ForegroundColor DarkGray
    $resourceId = Invoke-AzCli -Arguments @(
        "cosmosdb", "sql", "database", "show",
        "--resource-group", $ResourceGroupName,
        "--account-name", $AccountName,
        "--name", $DatabaseName,
        "--query", "id",
        "--output", "tsv"
    ) -AllowFailure

    return Resolve-AzureResourceId -ResourceId $resourceId
}

function Get-CosmosSqlContainerId {
    param(
        [string]$ResourceGroupName,
        [string]$AccountName,
        [string]$DatabaseName,
        [string]$ContainerName
    )

    if ([string]::IsNullOrWhiteSpace($ResourceGroupName) -or [string]::IsNullOrWhiteSpace($AccountName) -or [string]::IsNullOrWhiteSpace($DatabaseName) -or [string]::IsNullOrWhiteSpace($ContainerName)) {
        return $null
    }

    Write-Host "Lookup Cosmos SQL container: $ContainerName" -ForegroundColor DarkGray
    $resourceId = Invoke-AzCli -Arguments @(
        "cosmosdb", "sql", "container", "show",
        "--resource-group", $ResourceGroupName,
        "--account-name", $AccountName,
        "--database-name", $DatabaseName,
        "--name", $ContainerName,
        "--query", "id",
        "--output", "tsv"
    ) -AllowFailure

    return Resolve-AzureResourceId -ResourceId $resourceId
}

function Initialize-TerraformExistingResourceState {
    param(
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [Parameter(Mandatory = $true)][string]$ResourceGroupName,
        [Parameter(Mandatory = $true)][string]$ProjectName,
        [Parameter(Mandatory = $true)][string]$Environment
    )

    Write-Step "Adopting existing Azure resources into Terraform state"

    $knownAddresses = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    foreach ($address in (Get-TerraformStateList -WorkingDirectory $WorkingDirectory)) {
        [void]$knownAddresses.Add($address)
    }

    $logAnalyticsName = "log-$ProjectName-$Environment"
    $appInsightsName = "appi-$ProjectName-$Environment"
    $managedIdentityName = "id-$ProjectName-$Environment"
    $cosmosName = "cosmos-$ProjectName-$Environment"
    $cosmosDatabaseName = "entra-analyzer"
    $redisName = "redis-$ProjectName-$Environment"
    $keyVaultName = "kv-$ProjectName-$Environment"
    $acrName = "${ProjectName}${Environment}acr"
    $containerEnvName = "cae-$ProjectName-$Environment"
    $backendAppName = "ca-$ProjectName-backend-$Environment"
    $frontendAppName = "ca-$ProjectName-frontend-$Environment"

    $resourceIds = @{
        "module.observability.azurerm_log_analytics_workspace.main" = Get-AzResourceId -ResourceGroupName $ResourceGroupName -ResourceType "Microsoft.OperationalInsights/workspaces" -Name $logAnalyticsName
        "module.observability.azurerm_application_insights.main"     = Get-AzResourceId -ResourceGroupName $ResourceGroupName -ResourceType "Microsoft.Insights/components" -Name $appInsightsName
        "module.identity.azurerm_user_assigned_identity.app"         = Get-AzResourceId -ResourceGroupName $ResourceGroupName -ResourceType "Microsoft.ManagedIdentity/userAssignedIdentities" -Name $managedIdentityName
        "module.data.azurerm_cosmosdb_account.main"                  = Get-AzResourceId -ResourceGroupName $ResourceGroupName -ResourceType "Microsoft.DocumentDB/databaseAccounts" -Name $cosmosName
        "module.data.azurerm_cosmosdb_sql_database.main"             = Get-CosmosSqlDatabaseId -ResourceGroupName $ResourceGroupName -AccountName $cosmosName -DatabaseName $cosmosDatabaseName
        "module.data.azurerm_redis_cache.main"                       = Get-AzResourceId -ResourceGroupName $ResourceGroupName -ResourceType "Microsoft.Cache/Redis" -Name $redisName
        "module.security.azurerm_key_vault.main"                     = Get-AzResourceId -ResourceGroupName $ResourceGroupName -ResourceType "Microsoft.KeyVault/vaults" -Name $keyVaultName
        "module.compute.azurerm_container_registry.main"             = Get-AzResourceId -ResourceGroupName $ResourceGroupName -ResourceType "Microsoft.ContainerRegistry/registries" -Name $acrName
        "module.compute.azurerm_container_app_environment.main"      = Get-AzResourceId -ResourceGroupName $ResourceGroupName -ResourceType "Microsoft.App/managedEnvironments" -Name $containerEnvName
        "module.compute.azurerm_container_app.backend"               = Get-AzResourceId -ResourceGroupName $ResourceGroupName -ResourceType "Microsoft.App/containerApps" -Name $backendAppName
        "module.compute.azurerm_container_app.frontend"              = Get-AzResourceId -ResourceGroupName $ResourceGroupName -ResourceType "Microsoft.App/containerApps" -Name $frontendAppName
    }

    foreach ($containerName in @("tenant_configs", "identity_profiles", "action_events", "sync_state", "role_recommendations", "drift_alerts", "baselines", "best_practice_violations", "narratives")) {
        $address = "module.data.azurerm_cosmosdb_sql_container.$containerName"
        $resourceIds[$address] = Get-CosmosSqlContainerId -ResourceGroupName $ResourceGroupName -AccountName $cosmosName -DatabaseName $cosmosDatabaseName -ContainerName $containerName
    }

    $scheduledJobs = @{
        "sync-tenant"              = "sync-ten"
        "compute-baselines"        = "comp-base"
        "detect-drift"             = "det-drift"
        "generate-recommendations" = "gen-reco"
        "generate-narratives"      = "gen-narr"
    }
    foreach ($jobKey in $scheduledJobs.Keys) {
        $jobName = "job-$ProjectName-$($scheduledJobs[$jobKey])-$Environment"
        $address = "module.compute.azurerm_container_app_job.scheduled[`"$jobKey`"]"
        $resourceIds[$address] = Get-AzResourceId -ResourceGroupName $ResourceGroupName -ResourceType "Microsoft.App/jobs" -Name $jobName
    }

    foreach ($address in $resourceIds.Keys) {
        Write-Host "Adoption check: $address" -ForegroundColor DarkGray
        Import-TerraformResourceIfIdPresent -WorkingDirectory $WorkingDirectory -Address $Address -ResourceId $resourceIds[$address] -KnownAddresses $knownAddresses
    }

    $managedIdentityPrincipalId = Invoke-AzCli -Arguments @("identity", "show", "--resource-group", $ResourceGroupName, "--name", $managedIdentityName, "--query", "principalId", "--output", "tsv") -AllowFailure
    $signedInObjectId = Invoke-AzCli -Arguments @("ad", "signed-in-user", "show", "--query", "id", "--output", "tsv") -AllowFailure

    Write-Host "Adoption check: module.compute.azurerm_role_assignment.acr_pull" -ForegroundColor DarkGray
    Import-TerraformResourceIfIdPresent -WorkingDirectory $WorkingDirectory -Address "module.compute.azurerm_role_assignment.acr_pull" -ResourceId (Get-RoleAssignmentId -Scope $resourceIds["module.compute.azurerm_container_registry.main"] -PrincipalId $managedIdentityPrincipalId -RoleDefinitionName "AcrPull") -KnownAddresses $knownAddresses
    Write-Host "Adoption check: module.security.azurerm_role_assignment.deployer_kv_admin" -ForegroundColor DarkGray
    Import-TerraformResourceIfIdPresent -WorkingDirectory $WorkingDirectory -Address "module.security.azurerm_role_assignment.deployer_kv_admin" -ResourceId (Get-RoleAssignmentId -Scope $resourceIds["module.security.azurerm_key_vault.main"] -PrincipalId $signedInObjectId -RoleDefinitionName "Key Vault Administrator") -KnownAddresses $knownAddresses
    Write-Host "Adoption check: module.security.azurerm_role_assignment.app_kv_secrets_user" -ForegroundColor DarkGray
    Import-TerraformResourceIfIdPresent -WorkingDirectory $WorkingDirectory -Address "module.security.azurerm_role_assignment.app_kv_secrets_user" -ResourceId (Get-RoleAssignmentId -Scope $resourceIds["module.security.azurerm_key_vault.main"] -PrincipalId $managedIdentityPrincipalId -RoleDefinitionName "Key Vault Secrets User") -KnownAddresses $knownAddresses
    Write-Host "Adoption check: module.data.azurerm_cosmosdb_sql_role_assignment.app_data_contributor" -ForegroundColor DarkGray
    Import-TerraformResourceIfIdPresent -WorkingDirectory $WorkingDirectory -Address "module.data.azurerm_cosmosdb_sql_role_assignment.app_data_contributor" -ResourceId (Get-CosmosSqlRoleAssignmentId -ResourceGroupName $ResourceGroupName -AccountName $cosmosName -PrincipalId $managedIdentityPrincipalId) -KnownAddresses $knownAddresses

    $keyVaultSecrets = @{
        "module.security.azurerm_key_vault_secret.app_client_secret"             = "app-client-secret"
        "module.security.azurerm_key_vault_secret.cosmos_key"                    = "cosmos-key"
        "module.security.azurerm_key_vault_secret.cosmos_endpoint"               = "cosmos-endpoint"
        "module.security.azurerm_key_vault_secret.redis_password"                = "redis-password"
        "module.security.azurerm_key_vault_secret.foundry_key"                   = "foundry-key"
        "module.security.azurerm_key_vault_secret.appinsights_connection_string" = "appinsights-connection-string"
        "module.security.azurerm_key_vault_secret.encryption_key"                = "encryption-key"
        "module.security.azurerm_key_vault_secret.scan_function_key"             = "scan-function-key"
    }
    foreach ($address in $keyVaultSecrets.Keys) {
        Write-Host "Adoption check: $address" -ForegroundColor DarkGray
        Import-TerraformResourceIfIdPresent -WorkingDirectory $WorkingDirectory -Address $address -ResourceId (Get-KeyVaultSecretId -VaultName $keyVaultName -SecretName $keyVaultSecrets[$address]) -KnownAddresses $knownAddresses
    }
}

function Get-HttpResult {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Uri
    )

    try {
        $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 60
        return [pscustomobject]@{
            StatusCode = [int]$response.StatusCode
            Body       = [string]$response.Content
        }
    }
    catch {
        $statusCode = 0
        $body = ""

        if ($_.Exception.Response) {
            $statusCode = [int]$_.Exception.Response.StatusCode.value__
        }

        if ($_.ErrorDetails -and $_.ErrorDetails.Message) {
            $body = [string]$_.ErrorDetails.Message
        }
        elseif ($_.Exception.Message) {
            $body = [string]$_.Exception.Message
        }

        return [pscustomobject]@{
            StatusCode = $statusCode
            Body       = $body
        }
    }
}

function Invoke-SmokeTests {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FrontendUrl,

        [Parameter(Mandatory = $true)]
        [string]$BackendUrl,

        [Parameter(Mandatory = $true)]
        [string]$ClientId,

        [Parameter(Mandatory = $true)]
        [bool]$LocalModeEnabled
    )

    Write-Step "Running post-deploy smoke tests"

    $frontendRoot = Get-HttpResult -Uri $FrontendUrl
    if ($frontendRoot.StatusCode -ne 200) {
        throw "Frontend root check failed with status $($frontendRoot.StatusCode)"
    }

    $assetMatch = [regex]::Match($frontendRoot.Body, 'assets/index-[^"'']+\.js')
    if (-not $assetMatch.Success) {
        throw "Frontend bundle asset reference not found in HTML"
    }

    $assetPath = $assetMatch.Value
    $assetUrl = [System.Uri]::new([System.Uri]::new($FrontendUrl.TrimEnd('/') + '/'), $assetPath).AbsoluteUri
    $frontendAsset = Get-HttpResult -Uri $assetUrl
    if ($frontendAsset.StatusCode -ne 200) {
        throw "Frontend bundle check failed with status $($frontendAsset.StatusCode)"
    }
    if (-not $frontendAsset.Body.Contains($ClientId)) {
        throw "Frontend bundle does not contain client ID $ClientId"
    }

    $frontendApiHealth = $null
    for ($attempt = 1; $attempt -le 12; $attempt++) {
        $frontendApiHealth = Get-HttpResult -Uri ($FrontendUrl.TrimEnd('/') + '/api/healthz')
        if ($frontendApiHealth.StatusCode -eq 200) {
            break
        }

        if ($attempt -lt 12) {
            Write-Host "Waiting for frontend reverse proxy /api/healthz to return 200 (attempt $attempt of 12)"
            Start-Sleep -Seconds 10
        }
    }

    if ($frontendApiHealth.StatusCode -ne 200) {
        throw "Frontend reverse proxy /api/healthz check failed with status $($frontendApiHealth.StatusCode). Body: $($frontendApiHealth.Body)"
    }

    $healthResult = Get-HttpResult -Uri ($BackendUrl.TrimEnd('/') + '/healthz')
    if ($healthResult.StatusCode -ne 200) {
        throw "Backend /healthz check failed with status $($healthResult.StatusCode). Body: $($healthResult.Body)"
    }

    $expectedProjectsStatus = if ($LocalModeEnabled) { 200 } else { 401 }
    $projectsExpectationLabel = if ($LocalModeEnabled) { "local-mode" } else { "unauthenticated" }
    $projectsResult = $null
    for ($attempt = 1; $attempt -le 12; $attempt++) {
        $projectsResult = Get-HttpResult -Uri ($BackendUrl.TrimEnd('/') + '/api/projects')
        if ($projectsResult.StatusCode -eq $expectedProjectsStatus) {
            break
        }

        if ($attempt -lt 12) {
            Write-Host "Waiting for backend /api/projects to return $expectedProjectsStatus for $projectsExpectationLabel mode (attempt $attempt of 12)"
            Start-Sleep -Seconds 10
        }
    }

    if ($projectsResult.StatusCode -ne $expectedProjectsStatus) {
        throw "Backend /api/projects $projectsExpectationLabel check expected $expectedProjectsStatus but got $($projectsResult.StatusCode). Body: $($projectsResult.Body)"
    }

    $normalizedFrontendOrigin = $FrontendUrl.TrimEnd('/').ToLowerInvariant()
    $preflightAllowed = $false
    $lastPreflightHeaderText = ""
    for ($attempt = 1; $attempt -le 12; $attempt++) {
        $preflightHeaders = curl.exe -k -sS -D - -o NUL -X OPTIONS ($BackendUrl.TrimEnd('/') + '/api/projects') -H "Origin: $FrontendUrl" -H "Access-Control-Request-Method: GET" -H "Access-Control-Request-Headers: authorization,content-type"
        $lastPreflightHeaderText = ($preflightHeaders | Out-String)

        $originHeaderMatches = [regex]::Matches($lastPreflightHeaderText, "(?im)^access-control-allow-origin:\s*(.+?)\s*$")
        foreach ($match in $originHeaderMatches) {
            $allowedOrigin = $match.Groups[1].Value.Trim().TrimEnd('/').ToLowerInvariant()
            if ($allowedOrigin -eq $normalizedFrontendOrigin) {
                $preflightAllowed = $true
                break
            }
        }

        if ($preflightAllowed) {
            break
        }

        if ($attempt -lt 12) {
            Write-Host "Waiting for backend preflight to allow frontend origin (attempt $attempt of 12)"
            Start-Sleep -Seconds 10
        }
    }

    if (-not $preflightAllowed) {
        throw "Backend preflight response does not allow frontend origin $FrontendUrl. Last headers: $lastPreflightHeaderText"
    }

    $readyResult = Get-HttpResult -Uri ($BackendUrl.TrimEnd('/') + '/readyz')
    $readyMessage = if ($readyResult.StatusCode -eq 200) {
        "Backend /readyz: 200"
    }
    elseif ($readyResult.StatusCode -eq 503) {
        "Backend /readyz: 503 readiness gate not yet satisfied. Body: $($readyResult.Body)"
    }
    else {
        "Backend /readyz: unexpected status $($readyResult.StatusCode). Body: $($readyResult.Body)"
    }

    Write-Host "Smoke tests passed"
    Write-Host "  Frontend root: 200"
    Write-Host "  Frontend bundle contains backend URL and client ID"
    Write-Host "  Backend /healthz: 200"
    if ($LocalModeEnabled) {
        Write-Host "  Backend /api/projects local mode: 200"
    }
    else {
        Write-Host "  Backend /api/projects without token: 401"
    }
    Write-Host "  Backend preflight allows frontend origin"
    Write-Host "  $readyMessage"

    if ($readyResult.StatusCode -ne 200) {
        Write-Warning "Readiness gate is not yet healthy. Deployment succeeded, but the backend is not fully ready for dependency-backed requests."
    }
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$tempRoot = Join-Path $env:TEMP "entraperm-existing-rg-deploy"
$infraRoot = Join-Path $tempRoot "infra"
$tfWorkDir = Join-Path $infraRoot "envs/prod"

if (Test-Path $tempRoot) {
    Remove-Item -Recurse -Force $tempRoot
}

Write-Step "Preparing temporary Terraform workspace"
New-Item -ItemType Directory -Path $tempRoot | Out-Null
Copy-Item -Recurse -Force (Join-Path $repoRoot "infra") $infraRoot

$env:TF_VAR_existing_resource_group_name = $ResourceGroupName
$env:TF_VAR_existing_application_client_id = $ExistingApplicationClientId
$env:TF_VAR_existing_application_client_secret = $ExistingApplicationClientSecret
$env:TF_VAR_foundry_endpoint = $FoundryEndpoint
$env:TF_VAR_foundry_key = $FoundryKey
$env:TF_VAR_foundry_model = $FoundryModel
$env:TF_VAR_github_repository = $GitHubRepository
$env:TF_VAR_location = $Location
$env:TF_VAR_project_name = $ProjectName
$env:TF_VAR_environment = $Environment

# Generate encryption key if not provided
if (-not $EncryptionKey) {
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    $EncryptionKey = [Convert]::ToBase64String($bytes)
    Write-Warning "Generated ENCRYPTION_KEY. Pass -EncryptionKey to persist across redeploys."
}
$env:TF_VAR_encryption_key = $EncryptionKey

# scan_function_key has a default of "" in variables.tf — Terraform creates the KV secret;
# the actual Function App host key is populated after first deployment.
$env:TF_VAR_scan_function_key = "placeholder-replaced-after-first-deploy"

$localModeValue = if ($EnableLocalMode) { "true" } else { "false" }

Write-Step "Initializing Terraform"
Invoke-Terraform -WorkingDirectory $tfWorkDir -Arguments @("init", "-reconfigure")

$stateAddresses = Get-TerraformStateList -WorkingDirectory $tfWorkDir
if ($BootstrapAdoption) {
    Write-Step "Bootstrapping Terraform state from existing Azure resources"
    Initialize-TerraformExistingResourceState -WorkingDirectory $tfWorkDir -ResourceGroupName $ResourceGroupName -ProjectName $ProjectName -Environment $Environment
}
elseif ($stateAddresses.Count -eq 0) {
    throw "The Azure Storage Terraform backend is empty. Run the script once with -BootstrapAdoption so it imports the existing rg-dmig resources from Azure."
}

Write-Step "Provisioning shared infrastructure"
Invoke-Terraform -WorkingDirectory $tfWorkDir -Arguments @(
    "apply",
    "-auto-approve",
    "-target=module.observability",
    "-target=module.identity",
    "-target=module.data",
    "-target=module.security",
    "-target=module.compute.azurerm_container_registry.main",
    "-target=module.compute.azurerm_role_assignment.acr_pull",
    "-target=module.compute.azurerm_container_app_environment.main"
)

$acrName = Get-TerraformOutputValue -WorkingDirectory $tfWorkDir -Name "acr_name"
$tenantId = Get-TerraformOutputValue -WorkingDirectory $tfWorkDir -Name "tenant_id"
$backendAppName = "ca-$ProjectName-backend-$Environment"
$frontendAppName = "ca-$ProjectName-frontend-$Environment"
$backendTag = if ($FrontendImageTag) { $FrontendImageTag } else { "prod-" + (Get-Date -Format "yyyyMMddHHmmss") }
$backendImage = "$acrName.azurecr.io/$ProjectName-backend:$backendTag"
$frontendTag = if ($FrontendImageTag) { $FrontendImageTag } else { "prod-" + (Get-Date -Format "yyyyMMddHHmmss") }
$frontendImage = "$acrName.azurecr.io/$ProjectName-frontend:$frontendTag"

if (-not $SkipBootstrapBuild) {
    Write-Step "Building bootstrap backend image in ACR"
    & az acr build --registry $acrName --image "$ProjectName-backend:initial" --file (Join-Path $repoRoot "backend/Dockerfile") --target prod (Join-Path $repoRoot "backend")
    if ($LASTEXITCODE -ne 0) {
        throw "Backend bootstrap image build failed"
    }

    Write-Step "Building bootstrap frontend image in ACR"
    & az acr build --registry $acrName --image "$ProjectName-frontend:initial" --file (Join-Path $repoRoot "frontend/Dockerfile") --target prod --build-arg "VITE_APP_CLIENT_ID=$ExistingApplicationClientId" --build-arg "VITE_TENANT_ID=$tenantId" --build-arg "VITE_API_BASE_URL=" --build-arg "BACKEND_URL=http://backend:8000" (Join-Path $repoRoot "frontend")
    if ($LASTEXITCODE -ne 0) {
        throw "Frontend bootstrap image build failed"
    }
}

Write-Step "Creating Container Apps and jobs"
Invoke-Terraform -WorkingDirectory $tfWorkDir -Arguments @("apply", "-auto-approve")

Write-Step "Building live backend image in ACR"
& az acr build --registry $acrName --image "$ProjectName-backend:$backendTag" --file (Join-Path $repoRoot "backend/Dockerfile") --target prod (Join-Path $repoRoot "backend")
if ($LASTEXITCODE -ne 0) {
    throw "Backend live image build failed"
}

Write-Step "Updating backend Container App"
& az containerapp update --name $backendAppName --resource-group $ResourceGroupName --image $backendImage | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Backend container app image update failed"
}

Write-Step "Updating Container App jobs"
$jobDefinitions = @(
    "job-$ProjectName-sync-ten-$Environment",
    "job-$ProjectName-comp-base-$Environment",
    "job-$ProjectName-det-drift-$Environment",
    "job-$ProjectName-gen-reco-$Environment",
    "job-$ProjectName-gen-narr-$Environment"
)
foreach ($jobName in $jobDefinitions) {
    & az containerapp job update --name $jobName --resource-group $ResourceGroupName --image $backendImage | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Container App job image update failed for $jobName"
    }
}

Write-Step "Verifying Container App job images"
$staleJobs = @()
foreach ($jobName in $jobDefinitions) {
    $jobImage = Invoke-AzCli -Arguments @(
        "containerapp", "job", "show",
        "--name", $jobName,
        "--resource-group", $ResourceGroupName,
        "--query", "properties.template.containers[0].image",
        "--output", "tsv"
    )

    if ($jobImage -ne $backendImage) {
        $staleJobs += "${jobName}: $jobImage"
    }
}

if ($staleJobs.Count -gt 0) {
    throw "Container App job image verification failed. Expected $backendImage. Actual: $($staleJobs -join '; ')"
}

if (-not $SkipFrontendRedeploy) {
    $backendUrl = "https://$(Get-TerraformOutputValue -WorkingDirectory $tfWorkDir -Name 'backend_fqdn')"

    Write-Step "Building frontend image with same-origin backend proxy"
    & az acr build --registry $acrName --image "$ProjectName-frontend:$frontendTag" --file (Join-Path $repoRoot "frontend/Dockerfile") --target prod --build-arg "VITE_APP_CLIENT_ID=$ExistingApplicationClientId" --build-arg "VITE_TENANT_ID=$tenantId" --build-arg "VITE_LOCAL_MODE=$localModeValue" --build-arg "VITE_API_BASE_URL=" --build-arg "BACKEND_URL=$backendUrl" (Join-Path $repoRoot "frontend")
    if ($LASTEXITCODE -ne 0) {
        throw "Frontend live image build failed"
    }

    Write-Step "Updating frontend Container App"
    & az containerapp update --name $frontendAppName --resource-group $ResourceGroupName --image $frontendImage | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Frontend container app update failed"
    }
}

$backendFqdn = Get-TerraformOutputValue -WorkingDirectory $tfWorkDir -Name "backend_fqdn"
$frontendFqdn = Get-TerraformOutputValue -WorkingDirectory $tfWorkDir -Name "frontend_fqdn"
$keyVaultName = Get-TerraformOutputValue -WorkingDirectory $tfWorkDir -Name "key_vault_name"
$cosmosDatabaseName = Get-TerraformOutputValue -WorkingDirectory $tfWorkDir -Name "cosmos_database_name"
$functionAppHostname = Get-TerraformOutputValue -WorkingDirectory $tfWorkDir -Name "function_app_hostname"
$backendUrl = "https://$backendFqdn"
$frontendUrl = "https://$frontendFqdn"
$keyVaultUrl = "https://$keyVaultName.vault.azure.net/"
$scanFunctionAppUrl = "https://$functionAppHostname"
$logAnalyticsWorkspaceId = Get-TerraformOutputValue -WorkingDirectory $tfWorkDir -Name "log_analytics_workspace_id"

Write-Step "Updating backend runtime settings"
$envVars = @(
    "LOCAL_MODE=$localModeValue",
    "CORS_ORIGINS=$frontendUrl",
    "CORS_ORIGIN_REGEX=",
    "AZURE_CLIENT_ID=$ExistingApplicationClientId",
    "AZURE_TENANT_ID=$tenantId",
    "COSMOS_MASTER_DATABASE=$cosmosDatabaseName",
    "AZURE_FOUNDRY_ENDPOINT=$FoundryEndpoint",
    "AZURE_FOUNDRY_MODEL=$FoundryModel",
    "KEYVAULT_URL=$keyVaultUrl",
    "ENCRYPTION_KEY=$EncryptionKey",
    "SCAN_FUNCTION_APP_URL=$scanFunctionAppUrl",
    "LOG_ANALYTICS_WORKSPACE_ID=$logAnalyticsWorkspaceId"
)
# AZURE_CLIENT_SECRET, AZURE_FOUNDRY_KEY, COSMOS_KEY, COSMOS_ENDPOINT,
# REDIS_PASSWORD, SCAN_FUNCTION_KEY, APPLICATIONINSIGHTS_CONNECTION_STRING,
# and ENCRYPTION_KEY (Key Vault ref) are set by Terraform via Container App
# secret blocks. The plain ENCRYPTION_KEY above is a runtime override until
# the next terraform apply wires the Key Vault reference.

Update-ContainerAppEnvVars -AppName $backendAppName -ResourceGroupName $ResourceGroupName -EnvVars $envVars

Write-Step "Updating frontend runtime settings"
$frontendEnvVars = @(
    "BACKEND_URL=$backendUrl",
    "VITE_APP_CLIENT_ID=$ExistingApplicationClientId",
    "VITE_TENANT_ID=$tenantId",
    "VITE_API_BASE_URL=",
    "VITE_LOCAL_MODE=$localModeValue"
)
Update-ContainerAppEnvVars -AppName $frontendAppName -ResourceGroupName $ResourceGroupName -EnvVars $frontendEnvVars

if (-not $SkipSmokeTests) {
    Invoke-SmokeTests -FrontendUrl $frontendUrl -BackendUrl $backendUrl -ClientId $ExistingApplicationClientId -LocalModeEnabled:$EnableLocalMode
}

Write-Step "Deployment complete"
Write-Host "Backend:  $backendUrl"
Write-Host "Frontend: $frontendUrl"
Write-Host "Terraform state: Azure Storage backend in infra/envs/prod/backend.tf"
Write-Host "Temp Terraform workspace: $tfWorkDir"