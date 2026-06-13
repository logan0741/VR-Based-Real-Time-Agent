$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$Final = Resolve-Path (Join-Path $PSScriptRoot "..")

Set-Location $Root
python -m pip install -r (Join-Path $Final "requirements.txt")
npm --prefix $Final install
