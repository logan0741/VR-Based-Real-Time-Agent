# Runtime Pipeline

## Run Command

Standard run:

```powershell
.\final\scripts\00_pipeline.ps1
```

First-time setup and run:

```powershell
.\final\scripts\00_pipeline.ps1 -Install
```

Verify/build without starting the server:

```powershell
.\final\scripts\00_pipeline.ps1 -NoServer
```

The script runs verification/build first, then starts the FastAPI server at
`http://127.0.0.1:8000/`. Keep that PowerShell window open while testing.

## 1. Viewer

`s05_frontend/viewer.js` runs on the phone browser.

1. Load TF.js MoveNet Lightning.
2. Read webcam frames.
3. Convert MoveNet pixel coordinates to normalized COCO-17 `[y, x, confidence]`.
4. Draw the local user skeleton immediately.
5. Send keypoints to `/ws/pose` with `client_timestamp_ms`.

## 2. Server Relay

`s02_backend/server.py` receives `data_type: "keypoints"`.

1. Broadcast `data_type: "pose"` immediately.
2. Attach relay debug timestamps.
3. Keep the latest frame for preprocessing and drop stale queued frames.

This is the low-latency app movement path.

## 3. Server Processing

The latest keypoint frame is processed through:

1. Camera visibility gate.
2. Pose normalization.
3. Rep detection.
4. DTW/score update.
5. Feedback engine.
6. Feedback hold policy.
7. Bad joint mapping.
8. Session progress attachment.

## 4. App

`src/` runs as the Quest/app web UI.

1. Relay pose frames update the live 2D user skeleton.
2. Processed frames update score, reps, sets, feedback, and red joints.
3. Exercise selection sends `session_config` with `exercise_type`, `sets`, and `reps_per_set`.
4. The server broadcasts session control so the phone viewer reloads the matching expert pose.
5. The server calculates `total_target_reps = sets * reps_per_set`.
6. When progress becomes `completed = true`, the app automatically runs the session-end flow.
7. Session end displays detailed final feedback and TTS audio.

## 5. Latency Measurement

`latency_lab/run_latency_suite.py` sends synthetic COCO-17 frames through local
and Cloudflare WebSocket paths, then writes JSON/MD reports.
