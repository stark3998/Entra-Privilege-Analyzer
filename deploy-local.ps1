#Requires -Version 5.1
<#
.SYNOPSIS
    Deploy Entra Permissions Analyzer locally via Docker.
.DESCRIPTION
    Builds and starts all services (backend, frontend, functions, Cosmos DB emulator, Redis, Azurite).
.PARAMETER Command
    Action to perform: up (default), down, restart, logs, status
.EXAMPLE
    .\deploy-local.ps1
    .\deploy-local.ps1 down
    .\deploy-local.ps1 restart
#>
param(
    [ValidateSet("up", "down", "restart", "logs", "status", "help")]
    [string]$Command = "up"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
function Write-Log   { param([string]$Msg) Write-Host "[deploy] $Msg" -ForegroundColor Cyan }
function Write-Warn  { param([string]$Msg) Write-Host "[warn]   $Msg" -ForegroundColor Yellow }
function Write-Err   { param([string]$Msg) Write-Host "[error]  $Msg" -ForegroundColor Red }
function Write-Ok    { param([string]$Msg) Write-Host "[ok]     $Msg" -ForegroundColor Green }

function Invoke-Compose {
    $composeArgs = $args
    $v2 = $null
    try { $v2 = docker compose version 2>$null } catch {}
    if ($v2) {
        & docker compose @composeArgs
    } else {
        & docker-compose @composeArgs
    }
    if ($LASTEXITCODE -ne 0) { throw "docker compose exited with code $LASTEXITCODE" }
}

# ---------------------------------------------------------------------------
# Prerequisites
# ---------------------------------------------------------------------------
function Test-Prerequisites {
    $missing = $false

    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Err "docker is not installed or not in PATH"
        $missing = $true
    }

    $v2 = $null
    try { $v2 = docker compose version 2>$null } catch {}
    $v1 = $null
    try { $v1 = docker-compose version 2>$null } catch {}
    if (-not $v2 -and -not $v1) {
        Write-Err "docker compose (v2) or docker-compose (v1) is required"
        $missing = $true
    }

    try {
        $info = docker info 2>$null
        if ($LASTEXITCODE -ne 0) { throw }
    } catch {
        Write-Err "Docker daemon is not running - start Docker Desktop first"
        $missing = $true
    }

    if ($missing) { exit 1 }
    Write-Ok "Prerequisites satisfied"
}

# ---------------------------------------------------------------------------
# .env setup
# ---------------------------------------------------------------------------
function Set-EnvFile {
    if (-not (Test-Path .env)) {
        if (Test-Path .env.example) {
            Copy-Item .env.example .env
            Write-Log "Created .env from .env.example"
        } else {
            Write-Err ".env.example not found - cannot create .env"
            exit 1
        }
    }

    Set-EnvDefault "LOCAL_MODE"        "true"
    Set-EnvDefault "VITE_LOCAL_MODE"   "true"
    Set-EnvDefault "VITE_API_BASE_URL" "http://localhost:8000"
    Set-EnvDefault "CORS_ORIGINS"      "http://localhost:5173"
    Set-EnvDefault "REDIS_SSL"         "false"
    Set-EnvDefault "REDIS_PASSWORD"    ""
    Set-EnvDefault "SCAN_FUNCTION_KEY" "local-dev-function-key"

    Write-Ok ".env is configured for local Docker deployment"
}

function Set-EnvDefault {
    param([string]$Key, [string]$Value)
    $content = Get-Content .env -Raw
    if ($content -match "(?m)^${Key}=") { return }
    Add-Content .env "${Key}=${Value}"
}

# ---------------------------------------------------------------------------
# Build & start
# ---------------------------------------------------------------------------
function Start-Stack {
    Write-Log "Building images..."
    Invoke-Compose build

    Write-Log "Starting services..."
    Invoke-Compose up -d

    Write-Ok "All containers started"
}

# ---------------------------------------------------------------------------
# Wait for health
# ---------------------------------------------------------------------------
function Wait-ForService {
    param(
        [string]$Name,
        [string]$Url,
        [int]$MaxWait = 120,
        [switch]$SkipCertCheck
    )

    Write-Log "Waiting for $Name at $Url (up to ${MaxWait}s)..."
    $elapsed = 0

    while ($elapsed -lt $MaxWait) {
        try {
            $params = @{ Uri = $Url; UseBasicParsing = $true; TimeoutSec = 5; ErrorAction = "Stop" }
            if ($SkipCertCheck -and $PSVersionTable.PSVersion.Major -ge 7) {
                $params["SkipCertificateCheck"] = $true
            }
            if ($SkipCertCheck -and $PSVersionTable.PSVersion.Major -lt 7) {
                [System.Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }
            }
            $null = Invoke-WebRequest @params
            if ($SkipCertCheck -and $PSVersionTable.PSVersion.Major -lt 7) {
                [System.Net.ServicePointManager]::ServerCertificateValidationCallback = $null
            }
            Write-Ok "$Name is ready (${elapsed}s)"
            return $true
        } catch {
            Start-Sleep -Seconds 3
            $elapsed += 3
        }
    }

    if ($SkipCertCheck -and $PSVersionTable.PSVersion.Major -lt 7) {
        [System.Net.ServicePointManager]::ServerCertificateValidationCallback = $null
    }
    Write-Warn "$Name did not become ready within ${MaxWait}s - check logs with: docker compose logs $($Name.ToLower())"
    return $false
}

function Wait-ForHealth {
    Wait-ForService -Name "Cosmos DB Emulator" -Url "https://localhost:8081/_explorer/emulator.pem" -MaxWait 180 -SkipCertCheck | Out-Null
    Wait-ForService -Name "Redis" -Url "http://localhost:6379" -MaxWait 30 | Out-Null
    Wait-ForService -Name "Azurite" -Url "http://localhost:10000" -MaxWait 30 | Out-Null
    Wait-ForService -Name "Backend" -Url "http://localhost:8000/healthz" -MaxWait 60 | Out-Null
    Wait-ForService -Name "Frontend" -Url "http://localhost:5173" -MaxWait 60 | Out-Null
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
function Write-Summary {
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Green
    Write-Host "  Local deployment is running!" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Frontend:          " -NoNewline; Write-Host "http://localhost:5173" -ForegroundColor Cyan
    Write-Host "  Backend API:       " -NoNewline; Write-Host "http://localhost:8000" -ForegroundColor Cyan
    Write-Host "  API docs:          " -NoNewline; Write-Host "http://localhost:8000/docs" -ForegroundColor Cyan
    Write-Host "  Functions:         " -NoNewline; Write-Host "http://localhost:7071" -ForegroundColor Cyan
    Write-Host "  Cosmos Explorer:   " -NoNewline; Write-Host "https://localhost:8081/_explorer/index.html" -ForegroundColor Cyan
    Write-Host "  Redis:             " -NoNewline; Write-Host "localhost:6379" -ForegroundColor Cyan
    Write-Host "  Azurite (blob):    " -NoNewline; Write-Host "localhost:10000" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Auth mode:         " -NoNewline; Write-Host "LOCAL_MODE=true (no Entra ID required)" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Useful commands:"
    Write-Host "    docker compose logs -f backend     # tail backend logs"
    Write-Host "    docker compose logs -f frontend    # tail frontend logs"
    Write-Host "    docker compose logs -f functions   # tail functions logs"
    Write-Host "    docker compose ps                  # service status"
    Write-Host "    docker compose down                # stop everything"
    Write-Host "    docker compose down -v             # stop + remove volumes"
    Write-Host ""
}

# ---------------------------------------------------------------------------
# Teardown
# ---------------------------------------------------------------------------
function Stop-Stack {
    Write-Log "Stopping all services..."
    Invoke-Compose down
    Write-Ok "All services stopped"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
switch ($Command) {
    "up" {
        Test-Prerequisites
        Set-EnvFile
        Start-Stack
        Wait-ForHealth
        Write-Summary
    }
    "down" {
        Stop-Stack
    }
    "restart" {
        Stop-Stack
        Test-Prerequisites
        Set-EnvFile
        Start-Stack
        Wait-ForHealth
        Write-Summary
    }
    "logs" {
        Invoke-Compose logs -f
    }
    "status" {
        Invoke-Compose ps
    }
    "help" {
        Write-Host @"
Usage: .\deploy-local.ps1 [Command]

Commands:
  up        Build and start all services (default)
  down      Stop all services
  restart   Stop then start all services
  logs      Tail all service logs
  status    Show container status
"@
    }
}
