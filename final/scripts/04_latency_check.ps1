$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")

Set-Location $Root
python final\latency_lab\run_latency_suite.py --frames 90 --fps 30 --exercise squat
