param(
    [ValidatePattern("^\d+\.\d+\.\d+$")]
    [string]$Version = "0.2.0"
)

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$applicationBuild = Join-Path $PSScriptRoot "build-windows.ps1"
$installerScript = Join-Path $projectRoot "packaging\leave-planner.iss"

$prerequisiteDirectory = Join-Path `
    $projectRoot `
    "packaging\prerequisites"

$webViewBootstrapper = Join-Path `
    $prerequisiteDirectory `
    "MicrosoftEdgeWebview2Setup.exe"

$webViewDownload = `
    "https://go.microsoft.com/fwlink/p/?LinkId=2124703"

Write-Host "Building the packaged application..."
& $applicationBuild

if ($LASTEXITCODE -ne 0) {
    throw "The packaged application build failed."
}

New-Item `
    -ItemType Directory `
    -Path $prerequisiteDirectory `
    -Force | Out-Null

if (-not (Test-Path -LiteralPath $webViewBootstrapper)) {
    Write-Host "Downloading the Microsoft WebView2 bootstrapper..."

    Invoke-WebRequest `
        -Uri $webViewDownload `
        -OutFile $webViewBootstrapper
}

Write-Host "Verifying the WebView2 bootstrapper signature..."

$webViewSignature = Get-AuthenticodeSignature `
    -LiteralPath $webViewBootstrapper

if (
    $webViewSignature.Status -ne "Valid" `
    -or $webViewSignature.SignerCertificate.Subject `
        -notmatch "Microsoft Corporation"
) {
    throw "The WebView2 bootstrapper does not have a valid Microsoft signature."
}

$compilerCandidates = @(
    (Join-Path `
        $env:LOCALAPPDATA `
        "Programs\Inno Setup 6\ISCC.exe"),
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)

$innoCompiler = Get-Command `
    "ISCC.exe" `
    -ErrorAction SilentlyContinue

if ($null -ne $innoCompiler) {
    $compilerPath = $innoCompiler.Source
}
else {
    $compilerPath = $compilerCandidates |
        Where-Object { Test-Path -LiteralPath $_ } |
        Select-Object -First 1
}

if (-not $compilerPath) {
    throw "Inno Setup 6 was not found. Install it before building the installer."
}

Write-Host "Building the Leave Planner installer..."

$fileVersion = "$Version.0"

& $compilerPath `
    "/DAppVersion=$Version" `
    "/DAppFileVersion=$fileVersion" `
    $installerScript

if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup could not build the installer."
}

$installer = Join-Path `
    $projectRoot `
    "dist\installer\Leave-Planner-Setup-$Version.exe"

if (-not (Test-Path -LiteralPath $installer)) {
    throw "The expected installer was not produced."
}

Write-Host ""
Write-Host "Installer complete:"
Write-Host $installer
