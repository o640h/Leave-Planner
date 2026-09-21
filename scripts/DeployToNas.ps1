<#
.SYNOPSIS
Checks, packages, uploads, and deploys a versioned Leave Planner release to the Synology NAS.

.EXAMPLE
.\scripts\DeployToNas.ps1 -Version 0.2.2

.NOTES
The archive excludes deployment secrets and local generated files. Use a new semantic version for
every release. SkipChecks is intended only for retrying identical source after checks already passed.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?$')]
    [string]$Version,

    [ValidatePattern('^[A-Za-z0-9.-]+$')]
    [string]$NasHost = '192.168.1.253',

    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$NasUser = 'Ollie',

    [ValidatePattern('^/volume[0-9]+/.+$')]
    [string]$RemoteRoot = '/volume1/docker/leave-planner',

    [ValidatePattern('^/volume[0-9]+/.+$')]
    [string]$BackupDirectory = '/volume1/leave-planner-backups',

    [ValidatePattern('^https://[^/]+$')]
    [string]$PublicOrigin = 'https://app.merydio.co.uk',

    [switch]$SkipChecks
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Command failed with exit code $LASTEXITCODE."
    }
}

function ConvertTo-ShellArgument {
    param([Parameter(Mandatory = $true)][string]$Value)

    return "'" + $Value.Replace("'", "'`"'`"'") + "'"
}

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$projectEnvironment = Join-Path $repositoryRoot '.venv'
$temporaryDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ("leave-planner-release-" + [guid]::NewGuid().ToString('N'))
$archiveName = "leave-planner-$Version.tgz"
$archivePath = Join-Path $temporaryDirectory $archiveName
$remoteArchive = "/tmp/$archiveName"
$remoteScript = '/tmp/DeployRelease.sh'
$sshTarget = "$NasUser@$NasHost"

New-Item -ItemType Directory -Path $temporaryDirectory | Out-Null

try {
    if (-not $SkipChecks) {
        $projectPython = Join-Path $projectEnvironment 'Scripts\python.exe'
        if (-not (Test-Path -LiteralPath $projectPython)) {
            throw 'The project-root .venv is missing. Create it and install the locked backend development dependencies before deploying.'
        }
        $env:VIRTUAL_ENV = $projectEnvironment
        $env:PATH = (Join-Path $projectEnvironment 'Scripts') + [System.IO.Path]::PathSeparator + $env:PATH

        Write-Host 'Running backend release checks...'
        Push-Location (Join-Path $repositoryRoot 'backend')
        try {
            Invoke-CheckedCommand 'uv' @('run', '--active', '--no-sync', 'ruff', 'check', 'src', 'tests', 'migrations')
            Invoke-CheckedCommand 'uv' @('run', '--active', '--no-sync', 'mypy')
            Invoke-CheckedCommand 'uv' @('run', '--active', '--no-sync', 'pyright', '--project', '../pyrightconfig.json')
            Invoke-CheckedCommand 'uv' @('run', '--active', '--no-sync', 'pytest')
        }
        finally {
            Pop-Location
        }

        Write-Host 'Running frontend release checks...'
        Push-Location (Join-Path $repositoryRoot 'frontend')
        try {
            Invoke-CheckedCommand 'npm.cmd' @('run', 'lint')
            Invoke-CheckedCommand 'npm.cmd' @('run', 'format:check')
            Invoke-CheckedCommand 'npm.cmd' @('test')
            Invoke-CheckedCommand 'npm.cmd' @('run', 'build')
        }
        finally {
            Pop-Location
        }
    }

    Write-Host "Packaging release $Version without local secrets or generated files..."
    Push-Location $repositoryRoot
    try {
        $tarArguments = @(
            '-czf', $archivePath,
            '--exclude=.git',
            '--exclude=.venv',
            '--exclude=.dev',
            '--exclude=.tmp',
            '--exclude=**/__pycache__',
            '--exclude=**/.pytest_cache',
            '--exclude=**/.mypy_cache',
            '--exclude=**/.ruff_cache',
            '--exclude=frontend/node_modules',
            '--exclude=frontend/dist',
            '--exclude=frontend/coverage',
            '--exclude=.env',
            '--exclude=**/.env',
            '--exclude=deploy/secrets',
            '--exclude=*.log',
            '.dockerignore',
            'Dockerfile',
            'backend',
            'frontend',
            'deploy',
            'scripts',
            'docs/reference/HR78_Medical_Dental_Annual_Leave_Policy_v3_2025-07.pdf',
            'docs/reference/HRS09_Medical_Dental_Annual_Leave_Guidance_v1_2025-07.pdf'
        )
        Invoke-CheckedCommand 'tar.exe' $tarArguments
    }
    finally {
        Pop-Location
    }

    Write-Host "Uploading release source to $NasHost..."
    Invoke-CheckedCommand 'scp.exe' @('-O', $archivePath, (Join-Path $PSScriptRoot 'DeployRelease.sh'), "${sshTarget}:/tmp/")

    Write-Host 'Starting the controlled NAS release. SSH and sudo may request your password.'
    $releaseCommand = @(
        'sudo sh',
        (ConvertTo-ShellArgument $remoteScript),
        (ConvertTo-ShellArgument $Version),
        (ConvertTo-ShellArgument $remoteArchive),
        (ConvertTo-ShellArgument $RemoteRoot),
        (ConvertTo-ShellArgument $BackupDirectory)
    ) -join ' '
    Invoke-CheckedCommand 'ssh.exe' @('-t', $sshTarget, $releaseCommand)

    Write-Host "Checking the public health endpoint at $PublicOrigin..."
    $health = Invoke-RestMethod -Uri "$PublicOrigin/api/health" -Method Get -TimeoutSec 30
    if ($health.status -ne 'ok' -or $health.environment -ne 'production') {
        throw 'The public health endpoint returned an unexpected response.'
    }

    Write-Host 'Checking an ordinary public endpoint through the trusted edge...'
    $registration = Invoke-RestMethod -Uri "$PublicOrigin/api/auth/registration" -Method Get -TimeoutSec 30
    if ($registration.mode -notin @('open', 'invitation_only', 'closed')) {
        throw 'The public registration endpoint returned an unexpected response.'
    }

    Write-Host "Release $Version is live and healthy at $PublicOrigin."
}
finally {
    if (Test-Path -LiteralPath $temporaryDirectory) {
        Remove-Item -LiteralPath $temporaryDirectory -Recurse -Force
    }
}
