[CmdletBinding()]
param(
    [string]$GoExecutable = "go",
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$agentRoot = Join-Path $projectRoot "agent"
$distRoot = Join-Path $agentRoot "dist"
$executablePath = Join-Path $distRoot "quantumgenie-agent.exe"
$packagePath = Join-Path $distRoot "quantumgenie-agent-windows-amd64.zip"
$maximumPackageBytes = 5MB

Push-Location $agentRoot
try {
    if (-not $SkipTests) {
        & $GoExecutable test ./... -count=1
        if ($LASTEXITCODE -ne 0) { throw "Agent tests failed." }
    }

    New-Item -ItemType Directory -Path $distRoot -Force | Out-Null
    & $GoExecutable build -trimpath -ldflags "-s -w" -o $executablePath ./cmd/quantumgenie-agent
    if ($LASTEXITCODE -ne 0) { throw "Agent build failed." }

    Remove-Item $packagePath -Force -ErrorAction SilentlyContinue
    Compress-Archive -Path $executablePath -DestinationPath $packagePath -CompressionLevel Optimal

    $executable = Get-Item $executablePath
    $package = Get-Item $packagePath
    if ($package.Length -gt $maximumPackageBytes) {
        throw "Agent package is $($package.Length) bytes; the assignment limit is $maximumPackageBytes bytes."
    }

    [PSCustomObject]@{
        Executable = $executable.FullName
        ExecutableBytes = $executable.Length
        Package = $package.FullName
        PackageBytes = $package.Length
        PackageMiB = [Math]::Round($package.Length / 1MB, 2)
        LimitMiB = 5
        Status = "PASS"
    } | Format-List
}
finally {
    Pop-Location
}