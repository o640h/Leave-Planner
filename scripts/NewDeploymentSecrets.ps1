param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$secretDirectory = [System.IO.Path]::GetFullPath(
    (Join-Path $repositoryRoot "deploy\secrets")
)

if (-not $secretDirectory.StartsWith($repositoryRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to write secrets outside the repository."
}

$secretFiles = @(
    "postgres_superuser_password.txt",
    "migration_database_password.txt",
    "application_database_password.txt",
    "migration_database_url.txt",
    "application_database_url.txt"
)

$existing = @(
    $secretFiles |
        ForEach-Object { Join-Path $secretDirectory $_ } |
        Where-Object { Test-Path -LiteralPath $_ }
)

if ($existing.Count -gt 0 -and -not $Force) {
    throw "Deployment secrets already exist. Re-run with -Force only when intentionally replacing an unused deployment."
}

[System.IO.Directory]::CreateDirectory($secretDirectory) | Out-Null
$utf8WithoutBom = [System.Text.UTF8Encoding]::new($false)

function New-DeploymentPassword {
    $bytes = [byte[]]::new(32)
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($bytes)
    }
    finally {
        $generator.Dispose()
    }
    return [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
}

function Write-SecretFile([string]$Name, [string]$Value) {
    $path = Join-Path $secretDirectory $Name
    [System.IO.File]::WriteAllText($path, $Value, $utf8WithoutBom)
}

$postgresPassword = New-DeploymentPassword
$migrationPassword = New-DeploymentPassword
$applicationPassword = New-DeploymentPassword

Write-SecretFile "postgres_superuser_password.txt" $postgresPassword
Write-SecretFile "migration_database_password.txt" $migrationPassword
Write-SecretFile "application_database_password.txt" $applicationPassword
Write-SecretFile "migration_database_url.txt" (
    "postgresql+psycopg://leave_planner_migrator:{0}@database:5432/leave_planner" -f $migrationPassword
)
Write-SecretFile "application_database_url.txt" (
    "postgresql+psycopg://leave_planner_application:{0}@database:5432/leave_planner" -f $applicationPassword
)

Write-Output "Created five ignored deployment secret files in $secretDirectory"
Write-Output "Do not commit, display, or send these files."
