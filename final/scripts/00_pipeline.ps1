param(
    [switch]$Install,
    [switch]$SkipVerify,
    [switch]$NoServer,
    [string]$HostName = "0.0.0.0",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")

Set-Location $Root

if ($Install) {
    & (Join-Path $PSScriptRoot "01_install.ps1")
}

if (-not $SkipVerify) {
    & (Join-Path $PSScriptRoot "05_verify.ps1")
} else {
    & (Join-Path $PSScriptRoot "02_build_app.ps1")
}

Write-Host ""
Write-Host "Final pipeline ready."
Write-Host "App:    http://127.0.0.1:$Port/app/"
Write-Host "Viewer: http://127.0.0.1:$Port/viewer/"
Write-Host "Health: http://127.0.0.1:$Port/api/health"
Write-Host ""
if ($NoServer) {
    Write-Host "NoServer was set, so the server was not started."
    exit 0
}

Write-Host "Starting server. Keep this PowerShell window open."

python -m uvicorn final.s02_backend.server:app --host $HostName --port $Port
