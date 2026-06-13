$ErrorActionPreference = "Stop"
$Final = Resolve-Path (Join-Path $PSScriptRoot "..")

npm --prefix $Final run build
