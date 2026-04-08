# 3D Pose Model Pipeline

This package owns the 3D pose fitting path for the VR real-time agent. It takes
MoveNet/COCO 17 2D keypoints from the VR client, fits SMPL-X 3D joints, returns
squat feedback, and writes QA images/graphs for intermediate checks.

## File Layout

```text
model_3d/
  __init__.py
  analyzer.py        # Squat knee angle and feedback from 3D joints
  camera.py          # 640x480 perspective camera projection
  config.py          # Environment and project path helpers
  diagnostics.py     # QA images, fitting checks, metrics, and graphs
  fitter.py          # Phase 1 SMPL-X optimization and Phase 2 interface
  joint_mapper.py    # SMPL-X to COCO 17 joint mapper
  run_pipeline.py    # Standalone pipeline runner without FastAPI
  smplx_coordinate_fitter.py # Coordinate -> SMPL-X fitting feasibility path
  pipeline.py        # One-frame processing pipeline
  preprocessing.py   # MoveNet keypoint validation and pixel conversion
  schemas.py         # FitResult, SquatFeedback, and COCO constants
```

`server.py` only handles FastAPI, ngrok, and WebSocket transport. Model
execution is routed through `PosePipeline`. If you do not want to start the
server, run the pipeline directly with `python -m model_3d`.

## Run

```powershell
$env:SMPLX_MODEL_PATH="C:\Project\VR-Based-Real-Time-Agent\smplx_locked_head\neutral\model.npz"
$env:COCO_J_REGRESSOR_PATH="C:\path\to\coco_j_regressor.npy"
$env:NGROK_AUTHTOKEN="your-ngrok-token"
python server.py
```

For local testing without ngrok:

```powershell
$env:ENABLE_NGROK="false"
python server.py
```

## Run Pipeline Without Server

Run all available checks from the pipeline runner:

```powershell
cd C:\Project\VR-Based-Real-Time-Agent\model_3d
C:\Users\logan\AppData\Local\Programs\Python\Python310\python.exe run_pipeline.py
```

This checks:

- Dummy pipeline wiring and diagnostics generation.
- `pose_3d_v3` direct 3D-label path if the dataset exists.
- SMPL-X coordinate fitting availability. If `smplx` is missing, the report says unavailable instead of crashing.
- Trained 2D-to-3D lifter inference if `artifacts\model_3d\checkpoints\pose_lifter_latest.pt` or `pose_lifter_smoke.pt` exists.
- If no lifter checkpoint exists, a small smoke checkpoint is trained automatically under `model_3d\artifacts\checkpoints`.

The same command also works from the repository root:

```powershell
python model_3d\run_pipeline.py
```

The summary is written inside this folder:

```text
model_3d/artifacts/model_3d_check_all.json
```

Smoke-test only the pipeline and diagnostics without SMPL-X assets:

```powershell
python run_pipeline.py --dummy --frame-id smoke-test
```

Run the real SMPL-X pipeline from a keypoint JSON file. Prefer `.npz` SMPL-X
assets on Python 3.10; the local `model.pkl` can require deprecated `chumpy`.

```powershell
$env:SMPLX_MODEL_PATH="C:\Project\VR-Based-Real-Time-Agent\smplx_locked_head\neutral\model.npz"
$env:COCO_J_REGRESSOR_PATH="C:\path\to\coco_j_regressor.npy"
python run_pipeline.py --input sample_keypoints.json --output artifacts\last_response.json
```

Run the analyzer and diagnostics directly from existing `pose_3d_v3` 3D labels:

```powershell
python run_pipeline.py --pose3d-path pose_3d_v3 --pose3d-split train --max-frames 3 --output artifacts\pose3d_response.json
```

This mode uses `data_label` as 3D joints and `data_input` as the 2D diagnostic
overlay source. It bypasses SMPL-X optimization so it does not need
`SMPLX_MODEL_PATH`.

## Core Feasibility Test: Coordinates to SMPL-X

The main project question is whether SMPL-X can receive pose coordinates and fit
a 3D body model. Use this command for that exact test:

```powershell
cd C:\Project\VR-Based-Real-Time-Agent\model_3d
C:\Users\logan\AppData\Local\Programs\Python\Python310\python.exe run_pipeline.py --smplx-fit-pose3d --pose3d-path pose_3d_v3 --pose3d-split train --max-frames 1 --output artifacts\smplx_coordinate_fit_response.json
```

This mode:

- Loads `pose_3d_v3/frame_81/train/*.pkl`.
- Uses `data_label` as the target 3D joints.
- Optimizes SMPL-X `global_orient`, `body_pose`, scale, and translation.
- Writes step images under `model_3d/artifacts/pose_debug/...`.
- Returns `backend=smplx_coordinate_fit` if fitting succeeds.
- Writes the JSON response to `model_3d/artifacts/smplx_coordinate_fit_response.json`.

Expected QA files for one fitted frame:

```text
model_3d/artifacts/pose_debug/YYYYMMDD_HHMMSS/
  metrics.jsonl
  frames/
    frame_000001_00000000_000_preprocessed_keypoints.png
    frame_000001_00000000_000_reprojection_check.png
    frame_000001_00000000_000_joints_3d_check.png
    frame_000001_00000000_000_smplx_mesh_preview.png
    frame_000001_00000000_000_optimization_loss.png
  graphs/
    performance_graph.png
```

If it fails with `No module named 'smplx'`, install `smplx` into the same Python
interpreter you use to run the script:

```powershell
C:\Users\logan\AppData\Local\Programs\Python\Python310\python.exe -m pip install smplx
```

The local SMPL-X asset already exists at:

```text
C:\Project\VR-Based-Real-Time-Agent\smplx_locked_head\neutral\model.npz
```

`model_3d` now searches that `.npz` first. If `SMPLX_MODEL_PATH` points to the
sibling `model.pkl`, the code automatically uses `model.npz` unless
`SMPLX_ALLOW_PKL=true` is set.

The local locked-head `.npz` has the body model fields but not the hand PCA and
face landmark metadata expected by the installed `smplx` package. The runner
therefore creates a local compatibility cache under:

```text
model_3d/artifacts/smplx_cache/
```

This cache is generated data and does not leave the `model_3d` folder.

## Train the Actual 2D-to-3D Model

Train a real PyTorch pose lifting model from `pose_3d_v3/data_input` to
`pose_3d_v3/data_label`:

```powershell
python train_lifter.py --data pose_3d_v3 --epochs 5 --max-files 500 --eval-max-files 100 --checkpoint artifacts\checkpoints\pose_lifter_latest.pt
```

Train from the prepared fitness subset built under `013.피트니스자세`:

```powershell
python train_lifter.py --data ..\013.피트니스자세\prepared_train_eval_body01_compact --dataset-format fitness_json --epochs 5 --max-files 240 --eval-max-files 120 --checkpoint artifacts\checkpoints\fitness_pose_lifter_latest.pt
```

This path reads `labels\train` for training and `labels\val` for evaluation,
and it normalizes 2D keypoints using the source image size from the extracted
fitness frames.

Full end-to-end check after training:

```powershell
python train_lifter.py --data pose_3d_v3 --epochs 5 --max-files 500 --eval-max-files 100 --checkpoint artifacts\checkpoints\pose_lifter_latest.pt
python run_pipeline.py --lifter-checkpoint artifacts\checkpoints\pose_lifter_latest.pt --input sample_keypoints.json --output artifacts\lifter_response.json
python run_pipeline.py
```

For a quick smoke test:

```powershell
python train_lifter.py --data pose_3d_v3 --epochs 1 --max-files 2 --eval-max-files 1 --batch-size 64 --checkpoint artifacts\checkpoints\pose_lifter_smoke.pt
```

Run inference with the trained checkpoint:

```powershell
python run_pipeline.py --lifter-checkpoint artifacts\checkpoints\pose_lifter_latest.pt --input sample_keypoints.json --output artifacts\lifter_response.json
```

Use the trained lifter in the FastAPI server:

```powershell
$env:LIFTER_CHECKPOINT="model_3d\artifacts\checkpoints\pose_lifter_latest.pt"
python server.py
```

Training artifacts:

```text
model_3d/artifacts/
  checkpoints/pose_lifter_latest.pt
  pose_lifter_metrics.json
  pose_lifter_training_curve.png
```

The file can be either raw 17x3 keypoints or an object:

```json
{
  "frame_id": "local-test-001",
  "payload": [[0.52, 0.48, 0.91]]
}
```

## WebSocket Input

Endpoint:

```text
/ws/pose
```

Phase 1 keypoint payload:

```json
{
  "frame_id": "optional-frame-id",
  "data_type": "keypoints",
  "payload": [[0.52, 0.48, 0.91]]
}
```

The real payload must contain 17 keypoints. The default keypoint format is
MoveNet normalized `[y, x, score]`. If the VR client sends `[x, y, score]`, set:

```powershell
$env:KEYPOINT_FORMAT="xy"
```

Phase 2 image payload is reserved:

```json
{
  "data_type": "image",
  "payload": "base64_string"
}
```

## Automatic QA Artifacts

By default, every processed frame writes diagnostics under:

```text
model_3d/artifacts/pose_debug/YYYYMMDD_HHMMSS/
  metrics.jsonl
  frames/
    frame_000001_preprocessed_keypoints.png
    frame_000001_reprojection_check.png
    frame_000001_joints_3d_check.png
    frame_000001_smplx_mesh_preview.png
    frame_000001_optimization_loss.png
  graphs/
    performance_graph.png
```

Artifact meanings:

- `preprocessed_keypoints.png`: 2D input keypoints after pixel conversion.
- `reprojection_check.png`: target 2D keypoints versus projected 3D SMPL-X joints.
- `joints_3d_check.png`: fitted COCO 17 joint skeleton in 3D.
- `smplx_mesh_preview.png`: fitted SMPL-X vertices preview when vertices are returned.
- `optimization_loss.png`: per-iteration SMPL-X optimization loss for the frame.
- `performance_graph.png`: recent model latency, reprojection loss, and knee angle.
- `metrics.jsonl`: frame-level latency, FPS estimate, loss, knee angle, and feedback.

The WebSocket response includes generated artifact paths:

```json
{
  "diagnostics": {
    "enabled": true,
    "session_dir": "artifacts/pose_debug/20260408_031500",
    "artifacts": {
      "preprocessed_keypoints": "...png",
      "reprojection_check": "...png",
      "joints_3d_check": "...png",
      "optimization_loss_graph": "...png",
      "performance_graph": "...png",
      "metrics_jsonl": "...jsonl"
    }
  }
}
```

## Environment Variables

```text
FITTER_BACKEND=optimization
SMPLX_MODEL_PATH=../smplx_locked_head/neutral/model.npz
COCO_J_REGRESSOR_PATH=./coco_j_regressor.npy
USE_CUDA=true
SMPLX_OPT_ITERS=15
SMPLX_OPT_LR=0.03
SMPLX_CAMERA_DEPTH=2.5
KEYPOINT_FORMAT=movenet_yx
DIAGNOSTICS_ENABLED=true
DIAGNOSTICS_OUTPUT_DIR=model_3d/artifacts/pose_debug
DIAGNOSTICS_SAVE_EVERY_N=1
DIAGNOSTICS_GRAPH_EVERY_N=1
POSE_QUEUE_MAXSIZE=2
```

For higher FPS during live testing, increase `DIAGNOSTICS_SAVE_EVERY_N` to `5`
or `10`, or set `DIAGNOSTICS_ENABLED=false`.

## Phase 2 Replacement Point

Keep `BasePoseFitter.forward(payload)` stable and implement OSX, PIXIE, or
another single-pass regressor inside `RegressionPoseFitter`. The server,
pipeline, analyzer, and diagnostics layers can remain unchanged.
