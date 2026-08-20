<#
.SYNOPSIS
Runs the backend tests against the disposable PostgreSQL database on the Synology NAS.

.DESCRIPTION
Prompts securely for the database password, targets only the leave_planner_test database,
and removes the temporary connection settings when the test run finishes.

.PARAMETER Focused
Runs the PostgreSQL runtime and SQLite-import proofs without project-wide coverage.
#>

[CmdletBinding()]
param(
    [switch]$Focused,
    [string]$DatabaseHost = "192.168.1.253",
    [ValidateRange(1, 65535)]
    [int]$DatabasePort = 55432
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$workspace = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $workspace "backend"
$virtualEnvironment = Join-Path $workspace ".venv"
$python = Join-Path $virtualEnvironment "Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "The project-root .venv was not found. Create it before running PostgreSQL tests."
}

$null = Get-Command uv -ErrorAction Stop

$hadTestUrl = Test-Path Env:LEAVE_PLANNER_TEST_POSTGRES_URL
$previousTestUrl = $env:LEAVE_PLANNER_TEST_POSTGRES_URL
$hadDatabasePassword = Test-Path Env:PGPASSWORD
$previousDatabasePassword = $env:PGPASSWORD
$hadVirtualEnvironment = Test-Path Env:VIRTUAL_ENV
$previousVirtualEnvironment = $env:VIRTUAL_ENV
$originalLocation = Get-Location
$exitCode = 1
$securePassword = $null
$credential = $null
$databasePassword = $null

try {
    Write-Host "Target: disposable leave_planner_test database at ${DatabaseHost}:$DatabasePort"
    Write-Host "The test fixture will repeatedly reset this database's public schema."

    $securePassword = Read-Host "PostgreSQL password" -AsSecureString
    $credential = [System.Management.Automation.PSCredential]::new("leave_planner_test", $securePassword)
    $databasePassword = $credential.GetNetworkCredential().Password

    $env:VIRTUAL_ENV = $virtualEnvironment
    $env:PGPASSWORD = $databasePassword
    $env:LEAVE_PLANNER_TEST_POSTGRES_URL = (
        "postgresql+psycopg://leave_planner_test@${DatabaseHost}:$DatabasePort/leave_planner_test"
    )

    Set-Location -LiteralPath $backend

    if ($Focused) {
        & uv run --active --no-sync pytest `
            tests/test_postgresql_runtime.py `
            tests/test_sqlite_import.py `
            --no-cov `
            --tb=short
    }
    else {
        & uv run --active --no-sync pytest --tb=short
    }
    $exitCode = $LASTEXITCODE
}
finally {
    Set-Location -LiteralPath $originalLocation

    if ($hadTestUrl) {
        $env:LEAVE_PLANNER_TEST_POSTGRES_URL = $previousTestUrl
    }
    else {
        Remove-Item Env:LEAVE_PLANNER_TEST_POSTGRES_URL -ErrorAction SilentlyContinue
    }

    if ($hadDatabasePassword) {
        $env:PGPASSWORD = $previousDatabasePassword
    }
    else {
        Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
    }

    if ($hadVirtualEnvironment) {
        $env:VIRTUAL_ENV = $previousVirtualEnvironment
    }
    else {
        Remove-Item Env:VIRTUAL_ENV -ErrorAction SilentlyContinue
    }

    $databasePassword = $null
    $credential = $null
    $securePassword = $null
}

exit $exitCode
