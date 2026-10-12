param(
    [string]$PythonExe = ""
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
    @'
import os
import sys
from pathlib import Path

print(f"python_executable={sys.executable}")
print(f"python_version={sys.version.split()[0]}")

try:
    import torch
except Exception as exc:
    print(f"torch_status=ERROR {type(exc).__name__}: {exc}")
    raise SystemExit(1)

print(f"torch_version={torch.__version__}")
print(f"cuda_available={torch.cuda.is_available()}")
print(f"cuda_device_count={torch.cuda.device_count()}")
if torch.cuda.is_available():
    print(f"cuda_device_name={torch.cuda.get_device_name(0)}")

dataset_root = None
for name in sorted(os.listdir(".")):
    if name.startswith("013."):
        candidate = Path(name) / "prepared_train_eval_body01_compact"
        if candidate.exists():
            dataset_root = candidate.resolve()
            break

if dataset_root is None:
    print("dataset_status=ERROR prepared_train_eval_body01_compact not found")
    raise SystemExit(1)

print(f"dataset_root={dataset_root}")

from model_3d.lifter_model import FitnessLabelDataset

train = FitnessLabelDataset(dataset_root, split="train", max_files=None)
val = FitnessLabelDataset(dataset_root, split="val", max_files=None)
print(f"train_samples={len(train)}")
print(f"val_samples={len(val)}")
print(f"input_shape={tuple(train[0]['input'].shape)}")
print(f"target_shape={tuple(train[0]['target'].shape)}")
print("status=OK")
'@ | & $PythonExe -
}
finally {
    Pop-Location
}
