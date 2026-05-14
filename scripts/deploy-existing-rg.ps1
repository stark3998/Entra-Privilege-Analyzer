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
    if (-not $frontendAsset.Body.Contains($BackendUrl)) {
        throw "Frontend bundle does not contain backend URL $BackendUrl"
    }
    if (-not $frontendAsset.Body.Contains($ClientId)) {
        throw "Frontend bundle does not contain client ID $ClientId"
    }

    $healthResult = Get-HttpResult -Uri ($BackendUrl.TrimEnd('/') + '/healthz')
    if ($healthResult.StatusCode -ne 200) {
        throw "Backend /healthz check failed with status $($healthResult.StatusCode). Body: $($healthResult.Body)"
    }

    $projectsResult = Get-HttpResult -Uri ($BackendUrl.TrimEnd('/') + '/api/projects')
    if ($LocalModeEnabled) {
        if ($projectsResult.StatusCode -ne 200) {
            throw "Backend /api/projects local-mode check expected 200 but got $($projectsResult.StatusCode). Body: $($projectsResult.Body)"
        }
    }
    elseif ($projectsResult.StatusCode -ne 401) {
        throw "Backend /api/projects unauthenticated check expected 401 but got $($projectsResult.StatusCode). Body: $($projectsResult.Body)"
    }

    $preflightHeaders = curl.exe -k -sS -D - -o NUL -X OPTIONS ($BackendUrl.TrimEnd('/') + '/api/projects') -H "Origin: $FrontendUrl" -H "Access-Control-Request-Method: GET" -H "Access-Control-Request-Headers: authorization,content-type"
    if (-not $preflightHeaders.Contains("Access-Control-Allow-Origin: $FrontendUrl")) {
        throw "Backend preflight response does not allow frontend origin $FrontendUrl"
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
Remove-Item (Join-Path $tfWorkDir "backend.tf") -Force

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

Write-Step "Initializing Terraform"
Invoke-Terraform -WorkingDirectory $tfWorkDir -Arguments @("init")

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

$acrName = (& terraform -chdir=$tfWorkDir output -raw acr_name).Trim()
$tenantId = (& terraform -chdir=$tfWorkDir output -raw tenant_id).Trim()
$backendAppName = "ca-$ProjectName-backend-$Environment"
$frontendAppName = "ca-$ProjectName-frontend-$Environment"
$frontendTag = if ($FrontendImageTag) { $FrontendImageTag } else { "prod-" + (Get-Date -Format "yyyyMMddHHmmss") }

if (-not $SkipBootstrapBuild) {
    Write-Step "Building bootstrap backend image in ACR"
    & az acr build --registry $acrName --image "$ProjectName-backend:initial" --file (Join-Path $repoRoot "backend/Dockerfile") --target prod (Join-Path $repoRoot "backend")
    if ($LASTEXITCODE -ne 0) {
        throw "Backend bootstrap image build failed"
    }

    Write-Step "Building bootstrap frontend image in ACR"
    & az acr build --registry $acrName --image "$ProjectName-frontend:initial" --file (Join-Path $repoRoot "frontend/Dockerfile") --target prod --build-arg "VITE_APP_CLIENT_ID=$ExistingApplicationClientId" --build-arg "VITE_TENANT_ID=$tenantId" --build-arg "VITE_API_BASE_URL=https://placeholder.invalid" (Join-Path $repoRoot "frontend")
    if ($LASTEXITCODE -ne 0) {
        throw "Frontend bootstrap image build failed"
    }
}

Write-Step "Creating Container Apps and jobs"
Invoke-Terraform -WorkingDirectory $tfWorkDir -Arguments @("apply", "-auto-approve")

if (-not $SkipFrontendRedeploy) {
    $backendUrl = "https://$((& terraform -chdir=$tfWorkDir output -raw backend_fqdn).Trim())"

    Write-Step "Building frontend image with live backend URL"
    & az acr build --registry $acrName --image "$ProjectName-frontend:$frontendTag" --file (Join-Path $repoRoot "frontend/Dockerfile") --target prod --build-arg "VITE_APP_CLIENT_ID=$ExistingApplicationClientId" --build-arg "VITE_TENANT_ID=$tenantId" --build-arg "VITE_API_BASE_URL=$backendUrl" (Join-Path $repoRoot "frontend")
    if ($LASTEXITCODE -ne 0) {
        throw "Frontend live image build failed"
    }

    Write-Step "Updating frontend Container App"
    & az containerapp update --name $frontendAppName --resource-group $ResourceGroupName --image "$acrName.azurecr.io/$ProjectName-frontend:$frontendTag" | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Frontend container app update failed"
    }
}

$backendFqdn = (& terraform -chdir=$tfWorkDir output -raw backend_fqdn).Trim()
$frontendFqdn = (& terraform -chdir=$tfWorkDir output -raw frontend_fqdn).Trim()
$backendUrl = "https://$backendFqdn"
$frontendUrl = "https://$frontendFqdn"

Write-Step "Updating backend runtime settings"
$localModeValue = if ($EnableLocalMode) { "true" } else { "false" }
& az containerapp update --name $backendAppName --resource-group $ResourceGroupName --set-env-vars "LOCAL_MODE=$localModeValue" "CORS_ORIGINS=$frontendUrl" "CORS_ORIGIN_REGEX=" | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Backend container app runtime setting update failed"
}

if (-not $SkipSmokeTests) {
    Invoke-SmokeTests -FrontendUrl $frontendUrl -BackendUrl $backendUrl -ClientId $ExistingApplicationClientId -LocalModeEnabled:$EnableLocalMode
}

Write-Step "Deployment complete"
Write-Host "Backend:  $backendUrl"
Write-Host "Frontend: $frontendUrl"
Write-Host "Temp Terraform state: $tfWorkDir"