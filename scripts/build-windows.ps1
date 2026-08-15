$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$backendRoot = Join-Path $projectRoot "backend"
$frontendRoot = Join-Path $projectRoot "frontend"
$specFile = Join-Path $projectRoot "packaging\leave-planner.spec"
$distRoot = Join-Path $projectRoot "dist"
$buildRoot = Join-Path $projectRoot "build"
$pyinstaller = Join-Path $projectRoot ".venv\Scripts\pyinstaller.exe"

Write-Host "Building the React frontend..."
Push-Location $frontendRoot

try {
    npm ci

    if ($LASTEXITCODE -ne 0) {
        throw "The frontend dependencies could not be installed."
    }

    npm run build

    if ($LASTEXITCODE -ne 0) {
        throw "The frontend production build failed."
    }
}
finally {
    Pop-Location
}

Write-Host "Synchronising the locked Python environment..."
uv sync --active --project $backendRoot --locked --group dev

if ($LASTEXITCODE -ne 0) {
    throw "The Python environment could not be synchronised."
}

if (-not (Test-Path -LiteralPath $pyinstaller)) {
    throw "PyInstaller was not found in the project-root virtual environment."
}

Write-Host "Building the Windows application..."
& $pyinstaller `
    --clean `
    --noconfirm `
    --distpath $distRoot `
    --workpath $buildRoot `
    $specFile

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller could not build Leave Planner."
}

$application = Join-Path $distRoot "Leave Planner\Leave Planner.exe"

if (-not (Test-Path -LiteralPath $application)) {
    throw "The expected Leave Planner executable was not produced."
}

Write-Host ""
Write-Host "Build complete:"
Write-Host $application