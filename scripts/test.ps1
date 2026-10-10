[CmdletBinding()]
param([switch]$SkipBuild)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$backendPython = Join-Path $projectRoot "backend\.venv\Scripts\python.exe"

Push-Location (Join-Path $projectRoot "agent")
try {
    & go test ./... -count=1
    if ($LASTEXITCODE -ne 0) { throw "Agent tests failed." }
}
finally { Pop-Location }

Push-Location (Join-Path $projectRoot "backend")
try {
    & $backendPython -m ruff check app tests
    if ($LASTEXITCODE -ne 0) { throw "Backend lint failed." }
    & $backendPython -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "Backend tests failed." }
}
finally { Pop-Location }

Push-Location (Join-Path $projectRoot "frontend")
try {
    & npm run lint
    if ($LASTEXITCODE -ne 0) { throw "Frontend lint failed." }
    if (-not $SkipBuild) {
        & npm run build
        if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
    }
}
finally { Pop-Location }

Write-Host "All checks passed." -ForegroundColor Green