[CmdletBinding()]
param(
    [string]$PythonExecutable = "python",
    [string]$GoExecutable = "go",
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$backendRoot = Join-Path $projectRoot "backend"
$frontendRoot = Join-Path $projectRoot "frontend"
$venvPython = Join-Path $backendRoot ".venv\Scripts\python.exe"

foreach ($command in @($PythonExecutable, $GoExecutable, "npm")) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
        throw "Required command '$command' was not found on PATH."
    }
}

if (-not (Test-Path $venvPython)) {
    & $PythonExecutable -m venv (Join-Path $backendRoot ".venv")
    if ($LASTEXITCODE -ne 0) { throw "Python virtual environment creation failed." }
}

& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }
& $venvPython -m pip install -e "${backendRoot}[dev]"
if ($LASTEXITCODE -ne 0) { throw "Backend dependency installation failed." }

Push-Location $frontendRoot
try {
    & npm ci
    if ($LASTEXITCODE -ne 0) { throw "Frontend dependency installation failed." }
    & npm run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend production build failed." }
}
finally {
    Pop-Location
}

& (Join-Path $PSScriptRoot "build-agent.ps1") -GoExecutable $GoExecutable -SkipTests:$SkipTests

if (-not $SkipTests) {
    & (Join-Path $PSScriptRoot "test.ps1") -SkipBuild
}

New-Item -ItemType Directory -Path (Join-Path $projectRoot "data") -Force | Out-Null
Write-Host "Setup complete. Start the application with .\scripts\start.ps1" -ForegroundColor Green
