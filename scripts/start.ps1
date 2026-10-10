[CmdletBinding()]
param(
    [int]$ApiPort = 8765,
    [int]$AgentPort = 8766
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$backendRoot = Join-Path $projectRoot "backend"
$agentExecutable = Join-Path $projectRoot "agent\dist\quantumgenie-agent.exe"
$venvPython = Join-Path $backendRoot ".venv\Scripts\python.exe"
$frontendIndex = Join-Path $projectRoot "frontend\dist\index.html"

if (-not (Test-Path $venvPython)) {
    throw "Backend environment is missing. Run .\scripts\setup.ps1 first."
}
if (-not (Test-Path $frontendIndex)) {
    throw "Frontend build is missing. Run .\scripts\setup.ps1 first."
}
if (-not (Test-Path $agentExecutable)) {
    & (Join-Path $PSScriptRoot "build-agent.ps1")
}

if (-not $env:QG_AGENT_TOKEN) {
    $env:QG_AGENT_TOKEN = [Guid]::NewGuid().ToString("N")
}
$env:QG_API_HOST = "127.0.0.1"
$env:QG_API_PORT = $ApiPort.ToString()
$env:QG_AGENT_URL = "http://127.0.0.1:$AgentPort"
if (-not $env:QG_DATABASE_PATH) {
    $env:QG_DATABASE_PATH = Join-Path $projectRoot "data\quantumgenie.db"
}

$agentArguments = @(
    "--listen", "127.0.0.1:$AgentPort",
    "--backend", "http://127.0.0.1:$ApiPort"
)
$agentProcess = Start-Process -FilePath $agentExecutable -ArgumentList $agentArguments -PassThru -NoNewWindow

Write-Host "QuantumGenie Discovery: http://127.0.0.1:$ApiPort" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop the API and agent." -ForegroundColor DarkGray

Push-Location $backendRoot
try {
    & $venvPython -m uvicorn app.main:app --host 127.0.0.1 --port $ApiPort
}
finally {
    Pop-Location
    if ($agentProcess -and -not $agentProcess.HasExited) {
        Stop-Process -Id $agentProcess.Id -Force
        $agentProcess.WaitForExit()
    }
}