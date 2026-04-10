param(
    [string]$PythonExe = "",
    [int]$Epochs = 800,
    [int]$BatchSize = 256,
    [string]$Device = "",
    [double]$LearningRate = 0.001,
    [int]$HiddenDim = 512,
    [int]$NumLayers = 4,
    [double]$Dropout = 0.1,
    [int]$NumWorkers = 0,
    [double]$MaxHours = 0.0,
    [int]$EarlyStopPatience = 40,
    [double]$EarlyStopMinDelta = 1.0,
    [string]$Checkpoint = "",
    [string]$BestCheckpoint = "",
    [string]$ArtifactsDir = ""
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $preferred = Join-Path $env:LOCALAPPDATA "Programs\Python\Python310\python.exe"
    $PythonExe = if (Test-Path -LiteralPath $preferred) { $preferred } else { "python" }
}

if ([string]::IsNullOrWhiteSpace($Checkpoint)) {
    $Checkpoint = Join-Path $repoRoot "model_3d\artifacts\checkpoints\fitness_pose_lifter_latest.pt"
}

if ([string]::IsNullOrWhiteSpace($ArtifactsDir)) {
    $ArtifactsDir = Join-Path $repoRoot "model_3d\artifacts\training\fitness_full"
}

if ([string]::IsNullOrWhiteSpace($BestCheckpoint)) {
    $checkpointItem = Get-Item -LiteralPath (Split-Path -Parent $Checkpoint) -ErrorAction SilentlyContinue
    $checkpointDir = if ($checkpointItem) { $checkpointItem.FullName } else { Split-Path -Parent $Checkpoint }
    $checkpointName = [System.IO.Path]::GetFileNameWithoutExtension($Checkpoint)
    $checkpointExt = [System.IO.Path]::GetExtension($Checkpoint)
    $BestCheckpoint = Join-Path $checkpointDir ($checkpointName + "_best" + $checkpointExt)
}

$args = @(
    "-m", "model_3d.train_fitness_lifter",
    "--epochs", "$Epochs",
    "--batch-size", "$BatchSize",
    "--lr", "$LearningRate",
    "--hidden-dim", "$HiddenDim",
    "--num-layers", "$NumLayers",
    "--dropout", "$Dropout",
    "--max-files", "0",
    "--eval-max-files", "0",
    "--num-workers", "$NumWorkers",
    "--max-hours", "$MaxHours",
    "--early-stop-patience", "$EarlyStopPatience",
    "--early-stop-min-delta", "$EarlyStopMinDelta",
    "--checkpoint", "$Checkpoint",
    "--best-checkpoint", "$BestCheckpoint",
    "--artifacts-dir", "$ArtifactsDir"
)

if (-not [string]::IsNullOrWhiteSpace($Device)) {
    $args += @("--device", $Device)
}

Push-Location $repoRoot
try {
    & $PythonExe @args
}
finally {
    Pop-Location
}
