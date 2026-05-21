param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$TenantId = $(if ($env:GRAPH_APP_TENANT_ID) { $env:GRAPH_APP_TENANT_ID } else { $env:AZURE_TENANT_ID }),
    [string]$TenantName = $(if ($env:GRAPH_APP_TENANT_NAME) { $env:GRAPH_APP_TENANT_NAME } else { "Local Tenant" }),
    [string]$ClientId = $(if ($env:GRAPH_APP_CLIENT_ID) { $env:GRAPH_APP_CLIENT_ID } else { $env:AZURE_CLIENT_ID }),
    [string]$ClientSecret = $(if ($env:GRAPH_APP_CLIENT_SECRET) { $env:GRAPH_APP_CLIENT_SECRET } else { $env:AZURE_CLIENT_SECRET }),
    [int]$PollSeconds = 10,
    [int]$TimeoutMinutes = 20,
    [switch]$ShowContainerLogTail,
    [int]$ContainerLogTailLines = 25
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$logsDir = Join-Path $repoRoot "logs"
if (-not (Test-Path $logsDir)) {
    New-Item -Path $logsDir -ItemType Directory | Out-Null
}
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$logFile = Join-Path $logsDir "e2e-scan-$stamp.log"

function Write-Log {
    param(
        [string]$Message,
        [ValidateSet("INFO", "WARN", "ERROR", "STEP", "PASS")]
        [string]$Level = "INFO"
    )

    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] [$Level] $Message"
    Write-Host $line
    Add-Content -Path $logFile -Value $line
}

function Invoke-Api {
    param(
        [ValidateSet("GET", "POST", "PUT", "PATCH", "DELETE")]
        [string]$Method,
        [string]$Url,
        [object]$Body = $null
    )

    $reqBody = $null
    if ($null -ne $Body) {
        $reqBody = $Body | ConvertTo-Json -Depth 20 -Compress
    }

    $resp = if ($null -ne $reqBody) {
        Invoke-WebRequest -Method $Method -Uri $Url -Body $reqBody -ContentType "application/json" -SkipHttpErrorCheck -TimeoutSec 120
    }
    else {
        Invoke-WebRequest -Method $Method -Uri $Url -SkipHttpErrorCheck -TimeoutSec 120
    }

    $json = $null
    if (-not [string]::IsNullOrWhiteSpace($resp.Content)) {
        try {
            $json = $resp.Content | ConvertFrom-Json -Depth 50
        }
        catch {
            # Non-JSON content is expected for some errors.
        }
    }

    [pscustomobject]@{
        Status = [int]$resp.StatusCode
        Text   = $resp.Content
        Json   = $json
    }
}

function Get-FirstPresent {
    param(
        [object]$Object,
        [string[]]$Names
    )

    if ($null -eq $Object) {
        return $null
    }

    foreach ($name in $Names) {
        if ($Object.PSObject.Properties.Name -contains $name) {
            return $Object.$name
        }
    }

    return $null
}

function Show-Container-Tail {
    if (-not $ShowContainerLogTail) {
        return
    }

    Write-Log "Last $ContainerLogTailLines lines from backend/functions containers:" "STEP"
    try {
        $tail = & docker compose logs --tail $ContainerLogTailLines backend functions 2>&1
        foreach ($line in $tail) {
            Write-Log $line "INFO"
        }
    }
    catch {
        Write-Log "Failed to read container logs: $($_.Exception.Message)" "WARN"
    }
}

$globalStart = Get-Date
Write-Log "E2E scan test started. Log file: $logFile" "STEP"
Write-Log "Configuration: BaseUrl=$BaseUrl PollSeconds=$PollSeconds TimeoutMinutes=$TimeoutMinutes" "INFO"

if ([string]::IsNullOrWhiteSpace($TenantId) -or [string]::IsNullOrWhiteSpace($ClientId) -or [string]::IsNullOrWhiteSpace($ClientSecret)) {
    Write-Log "Missing required credentials. TenantId/ClientId/ClientSecret must be set via params or env vars." "ERROR"
    exit 2
}

Write-Log "Checking backend health endpoint..." "STEP"
$health = Invoke-Api -Method GET -Url "$BaseUrl/healthz"
Write-Log "healthz status=$($health.Status) body=$($health.Text)" "INFO"
if ($health.Status -ne 200) {
    Write-Log "Backend is not healthy. Aborting." "ERROR"
    exit 3
}

$projectName = "E2E Scan Validation $stamp"
Write-Log "Creating project '$projectName'..." "STEP"
$createPayload = @{
    name               = $projectName
    target_tenant_id   = $TenantId
    target_tenant_name = $TenantName
    client_id          = $ClientId
    client_secret      = $ClientSecret
}
$create = Invoke-Api -Method POST -Url "$BaseUrl/api/projects" -Body $createPayload
Write-Log "create-project status=$($create.Status)" "INFO"
if ($create.Status -lt 200 -or $create.Status -gt 299) {
    Write-Log "Project creation failed. Body: $($create.Text)" "ERROR"
    exit 4
}

$projectId = Get-FirstPresent -Object $create.Json -Names @("id", "project_id", "projectId")
if (-not $projectId) {
    $inner = Get-FirstPresent -Object $create.Json -Names @("project", "data")
    $projectId = Get-FirstPresent -Object $inner -Names @("id", "project_id", "projectId")
}

if (-not $projectId) {
    Write-Log "Could not extract project id from response: $($create.Text)" "ERROR"
    exit 5
}

Write-Log "Project created: id=$projectId" "PASS"

Write-Log "Triggering FULL scan for project $projectId..." "STEP"
$trigger = Invoke-Api -Method POST -Url "$BaseUrl/api/projects/$projectId/scans/trigger?full=true"
Write-Log "trigger status=$($trigger.Status) body=$($trigger.Text)" "INFO"
if ($trigger.Status -ne 202) {
    Write-Log "Trigger failed with status $($trigger.Status)." "ERROR"
    Show-Container-Tail
    exit 6
}

$scanId = Get-FirstPresent -Object $trigger.Json -Names @("scan_id", "scanId", "id")
if (-not $scanId) {
    Write-Log "Could not extract scan id from trigger response." "ERROR"
    exit 7
}
Write-Log "Scan triggered: scan_id=$scanId" "PASS"

$deadline = (Get-Date).AddMinutes($TimeoutMinutes)
$latest = $null
$terminal = @("completed", "failed", "cancelled")
$pollIndex = 0

Write-Log "Polling latest scan status every $PollSeconds seconds until terminal state..." "STEP"
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds $PollSeconds
    $pollIndex++

    $latest = Invoke-Api -Method GET -Url "$BaseUrl/api/projects/$projectId/scans/latest"
    if ($latest.Status -ne 200 -or $null -eq $latest.Json) {
        Write-Log "poll#$pollIndex latest-scan returned status=$($latest.Status)" "WARN"
        Show-Container-Tail
        continue
    }

    $status = ("" + (Get-FirstPresent -Object $latest.Json -Names @("status"))).ToLowerInvariant()
    $phaseText = ""
    if ($latest.Json.phases) {
        $phaseText = ($latest.Json.phases | ForEach-Object {
                $items = if ($_.PSObject.Properties.Name -contains "items_processed") { $_.items_processed } else { "?" }
                "{0}:{1}({2})" -f $_.name, $_.status, $items
            }) -join ", "
    }

    $elapsed = [int]((Get-Date) - $globalStart).TotalSeconds
    Write-Log "poll#$pollIndex elapsed=${elapsed}s status=$status phases=[$phaseText]" "INFO"

    if ($terminal -contains $status) {
        break
    }

    if (($pollIndex % 6) -eq 0) {
        Show-Container-Tail
    }
}

if ($null -eq $latest -or $latest.Status -ne 200 -or $null -eq $latest.Json) {
    Write-Log "Did not retrieve latest scan status successfully." "ERROR"
    exit 8
}

$finalStatus = ("" + (Get-FirstPresent -Object $latest.Json -Names @("status"))).ToLowerInvariant()
$scanDuration = [int]((Get-Date) - $globalStart).TotalSeconds
Write-Log "Scan terminal status=$finalStatus after ${scanDuration}s" "STEP"

if ($finalStatus -ne "completed") {
    Write-Log "Scan did not complete successfully. Fetching scan logs..." "WARN"
    $scanLogs = Invoke-Api -Method GET -Url "$BaseUrl/api/projects/$projectId/scans/$scanId/logs"
    Write-Log "scan-logs status=$($scanLogs.Status)" "INFO"
    if ($scanLogs.Status -eq 200 -and $scanLogs.Json -and $scanLogs.Json.events) {
        $errors = @($scanLogs.Json.events | Where-Object {
                ($_.PSObject.Properties.Name -contains "level" -and $_.level -match "error|critical") -or
                ($_.PSObject.Properties.Name -contains "message" -and $_.message -match "(?i)error|exception|failed|traceback")
            })
        if ($errors.Count -gt 0) {
            Write-Log ("Last error: " + $errors[-1].message) "ERROR"
        }
    }
    Show-Container-Tail
    exit 9
}

Write-Log "Verifying persisted data via analytics/identities/drift-alerts..." "STEP"
$analytics = Invoke-Api -Method GET -Url "$BaseUrl/api/projects/$projectId/analytics"
$identities = Invoke-Api -Method GET -Url "$BaseUrl/api/projects/$projectId/identities"
$driftBefore = Invoke-Api -Method GET -Url "$BaseUrl/api/projects/$projectId/drift-alerts"

Write-Log "analytics status=$($analytics.Status)" "INFO"
Write-Log "identities status=$($identities.Status)" "INFO"
Write-Log "drift-alerts (before detect) status=$($driftBefore.Status)" "INFO"

$identitiesCount = 0
if ($identities.Json) {
    if ($identities.Json.items) {
        $identitiesCount = @($identities.Json.items).Count
    }
    elseif ($identities.Json -is [System.Array]) {
        $identitiesCount = @($identities.Json).Count
    }
    elseif ($identities.Json.id) {
        $identitiesCount = 1
    }
}
Write-Log "identities_count=$identitiesCount" "INFO"

Write-Log "Running analysis endpoints..." "STEP"
$recoCompute = Invoke-Api -Method POST -Url "$BaseUrl/api/projects/$projectId/recommendations/compute"
$bpEval = Invoke-Api -Method POST -Url "$BaseUrl/api/projects/$projectId/best-practices/evaluate"
$driftDetect = Invoke-Api -Method POST -Url "$BaseUrl/api/projects/$projectId/drift-alerts/detect"

Write-Log "recommendations/compute status=$($recoCompute.Status)" "INFO"
Write-Log "best-practices/evaluate status=$($bpEval.Status)" "INFO"
Write-Log "drift-alerts/detect status=$($driftDetect.Status)" "INFO"

Start-Sleep -Seconds 20

$recoList = Invoke-Api -Method GET -Url "$BaseUrl/api/projects/$projectId/recommendations"
$bpSummary = Invoke-Api -Method GET -Url "$BaseUrl/api/projects/$projectId/best-practices/summary"
$driftAfter = Invoke-Api -Method GET -Url "$BaseUrl/api/projects/$projectId/drift-alerts"

$recoCount = 0
if ($recoList.Json) {
    if ($recoList.Json.items) {
        $recoCount = @($recoList.Json.items).Count
    }
    elseif ($recoList.Json -is [System.Array]) {
        $recoCount = @($recoList.Json).Count
    }
    elseif ($recoList.Json.identity_id) {
        $recoCount = 1
    }
}

$driftCount = 0
if ($driftAfter.Json) {
    if ($driftAfter.Json.items) {
        $driftCount = @($driftAfter.Json.items).Count
    }
    elseif ($driftAfter.Json -is [System.Array]) {
        $driftCount = @($driftAfter.Json).Count
    }
    elseif ($driftAfter.Json.id) {
        $driftCount = 1
    }
}

$bpTotal = Get-FirstPresent -Object $bpSummary.Json -Names @("total_violations")
$bpScore = Get-FirstPresent -Object $bpSummary.Json -Names @("compliance_score")

$logsFetchedPass = if ($analytics.Status -eq 200) { "YES" } else { "NO" }
$storedPass = if ($identities.Status -eq 200) { "YES" } else { "NO" }
$analysisPass = if ((@($recoCompute.Status, $bpEval.Status, $driftDetect.Status) | Where-Object { $_ -lt 200 -or $_ -gt 299 }).Count -eq 0 -and $recoList.Status -eq 200 -and $bpSummary.Status -eq 200 -and $driftAfter.Status -eq 200) { "YES" } else { "NO" }

Write-Log "--- FINAL REPORT ---" "STEP"
Write-Log "project_id=$projectId" "INFO"
Write-Log "project_name=$projectName" "INFO"
Write-Log "scan_id=$scanId" "INFO"
Write-Log "scan_status=$finalStatus" "INFO"
Write-Log "scan_duration_seconds=$scanDuration" "INFO"
Write-Log "recommendations_count=$recoCount" "INFO"
Write-Log "drift_alerts_count=$driftCount" "INFO"
Write-Log "best_practices_total_violations=$bpTotal" "INFO"
Write-Log "best_practices_compliance_score=$bpScore" "INFO"
Write-Log "PASS_logs_fetched=$logsFetchedPass" "PASS"
Write-Log "PASS_stored_in_cosmos=$storedPass" "PASS"
Write-Log "PASS_analysis_completed=$analysisPass" "PASS"

Write-Log "E2E scan test completed. Full transcript: $logFile" "STEP"
