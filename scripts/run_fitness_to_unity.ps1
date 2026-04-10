param(
    [string]$PythonExe = "",
    [int]$Epochs = 800,
    [int]$BatchSize = 256,
    [string]$Device = "cuda",
    [int]$EarlyStopPatience = 40,
    [double]$EarlyStopMinDelta = 1.0,
    [int]$UnityLimit = 0,
    [string]$UnityView = "view1"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $preferred = Join-Path $env:LOCALAPPDATA "Programs\Python\Python310\python.exe"
    $PythonExe = if (Test-Path -LiteralPath $preferred) { $preferred } else { "python" }
}

Push-Location $repoRoot
try {
    & $PythonExe -m model_3d.workflow_fitness_to_unity `
        --epochs $Epochs `
        --batch-size $BatchSize `
        --device $Device `
        --early-stop-patience $EarlyStopPatience `
        --early-stop-min-delta $EarlyStopMinDelta `
        --unity-limit $UnityLimit `
        --unity-view $UnityView
}
finally {
    Pop-Location
}
