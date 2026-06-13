$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")

Set-Location $Root
python -m uvicorn final.s02_backend.server:app --host 0.0.0.0 --port 8000
