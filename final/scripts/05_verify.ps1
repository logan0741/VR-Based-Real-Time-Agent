$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$Final = Resolve-Path (Join-Path $PSScriptRoot "..")

Set-Location $Root
python -m py_compile final\s02_backend\server.py final\latency_lab\measure_latency.py final\latency_lab\run_latency_suite.py
npm --prefix $Final run build
