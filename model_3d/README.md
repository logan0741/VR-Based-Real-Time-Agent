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
  pipeline.py        # One-frame processing pipeline
  preprocessing.py   # MoveNet keypoint validation and pixel conversion
  schemas.py         # FitResult, SquatFeedback, and COCO constants
```

`server.py` only handles FastAPI, ngrok, and WebSocket transport. Model
execution is routed through `PosePipeline`. If you do not want to start the
server, run the pipeline directly with `python -m model_3d`.

## Run

```powershell
$env:SMPLX_MODEL_PATH="C:\path\to\SMPLX_NEUTRAL.pkl"
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

Smoke-test the pipeline and diagnostics without SMPL-X assets:

```powershell
python -m model_3d --dummy --frame-id smoke-test
```

Run the real SMPL-X pipeline from a keypoint JSON file:

```powershell
$env:SMPLX_MODEL_PATH="C:\path\to\SMPLX_NEUTRAL.pkl"
$env:COCO_J_REGRESSOR_PATH="C:\path\to\coco_j_regressor.npy"
python -m model_3d --input sample_keypoints.json --output artifacts\last_response.json
```

Run the analyzer and diagnostics directly from existing `pose_3d_v3` 3D labels:

```powershell
python -m model_3d --pose3d-path pose_3d_v3 --pose3d-split train --max-frames 3 --output artifacts\pose3d_response.json
```

This mode uses `data_label` as 3D joints and `data_input` as the 2D diagnostic
overlay source. It bypasses SMPL-X optimization so it does not need
`SMPLX_MODEL_PATH`.

## Train the Actual 2D-to-3D Model

Train a real PyTorch pose lifting model from `pose_3d_v3/data_input` to
`pose_3d_v3/data_label`:

```powershell
python -m model_3d.train_lifter --data pose_3d_v3 --epochs 5 --max-files 500 --eval-max-files 100 --checkpoint artifacts\model_3d\checkpoints\pose_lifter_latest.pt
```

For a quick smoke test:

```powershell
python -m model_3d.train_lifter --data pose_3d_v3 --epochs 1 --max-files 2 --eval-max-files 1 --batch-size 64 --checkpoint artifacts\model_3d\checkpoints\pose_lifter_smoke.pt
```

Run inference with the trained checkpoint:

```powershell
python -m model_3d --lifter-checkpoint artifacts\model_3d\checkpoints\pose_lifter_latest.pt --input sample_keypoints.json --output artifacts\lifter_response.json
```

Use the trained lifter in the FastAPI server:

```powershell
$env:LIFTER_CHECKPOINT="artifacts\model_3d\checkpoints\pose_lifter_latest.pt"
python server.py
```

Training artifacts:

```text
artifacts/model_3d/
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
artifacts/pose_debug/YYYYMMDD_HHMMSS/
  metrics.jsonl
  frames/
    frame_000001_preprocessed_keypoints.png
    frame_000001_reprojection_check.png
    frame_000001_joints_3d_check.png
    frame_000001_optimization_loss.png
  graphs/
    performance_graph.png
```

Artifact meanings:

- `preprocessed_keypoints.png`: 2D input keypoints after pixel conversion.
- `reprojection_check.png`: target 2D keypoints versus projected 3D SMPL-X joints.
- `joints_3d_check.png`: fitted COCO 17 joint skeleton in 3D.
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
SMPLX_MODEL_PATH=./SMPLX_NEUTRAL.pkl
COCO_J_REGRESSOR_PATH=./coco_j_regressor.npy
USE_CUDA=true
SMPLX_OPT_ITERS=15
SMPLX_OPT_LR=0.03
SMPLX_CAMERA_DEPTH=2.5
KEYPOINT_FORMAT=movenet_yx
DIAGNOSTICS_ENABLED=true
DIAGNOSTICS_OUTPUT_DIR=artifacts/pose_debug
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
