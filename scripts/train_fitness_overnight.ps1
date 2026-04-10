param(
    [string]$PythonExe = "",
    [string]$Device = "cuda",
    [int]$Epochs = 800,
    [int]$BatchSize = 256,
    [double]$MaxHours = 0.0,
    [int]$EarlyStopPatience = 40,
    [double]$EarlyStopMinDelta = 1.0
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $preferred = Join-Path $env:LOCALAPPDATA "Programs\Python\Python310\python.exe"
    $PythonExe = if (Test-Path -LiteralPath $preferred) { $preferred } else { "python" }
}

$checkpoint = Join-Path $repoRoot "model_3d\artifacts\checkpoints\fitness_pose_lifter_overnight.pt"
$artifactsDir = Join-Path $repoRoot "model_3d\artifacts\training\fitness_overnight"

powershell -ExecutionPolicy Bypass -File (Join-Path $scriptDir "train_fitness_full.ps1") `
    -PythonExe $PythonExe `
    -Epochs $Epochs `
    -BatchSize $BatchSize `
    -Device $Device `
    -MaxHours $MaxHours `
    -EarlyStopPatience $EarlyStopPatience `
    -EarlyStopMinDelta $EarlyStopMinDelta `
    -Checkpoint $checkpoint `
    -ArtifactsDir $artifactsDir
