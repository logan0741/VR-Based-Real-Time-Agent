# Final Architecture

## Purpose

This folder is the final standalone implementation of the 2D VR real-time pose
feedback app. It replaces the earlier mixed root/final setup. Only the code
needed for the final browser-based system remains.

## Final Scope

Included:

- phone viewer camera page
- Quest/app React UI
- FastAPI WebSocket server
- pose preprocessing
- rep counting
- DTW scoring
- real-time feedback
- red joint highlighting
- final feedback TTS
- latency measurement
- build/run/verify scripts

Excluded:

- old prototype tests
- Unity/SMPLX prototype runtime
- unused 3D React renderers
- unused mock APIs
- stale generated TTS files
- Python cache files
- patch-only latency implementation examples

## System Diagram

```text
Phone Browser
  final/s05_frontend/viewer.js
  TF.js MoveNet
  COCO-17 [y,x,confidence]
        |
        | WebSocket keypoints
        v
FastAPI Server
  final/s02_backend/server.py
        |
        +--> immediate relay pose --------------------+
        |                                             |
        +--> preprocessing / score / feedback ----+   |
                                                |   |
                                                v   v
Quest / VR Browser
  final/src React App
  live skeleton + feedback + reps + TTS
```

## Runtime URLs

Local:

```text
http://127.0.0.1:8000/viewer/
http://127.0.0.1:8000/app/
http://127.0.0.1:8000/api/health
```

Domain:

```text
https://viewer.gun-hee.com/viewer/
https://app.gun-hee.com/app/
https://pt.gun-hee.com/api/health
```

## Folder Structure

```text
final/
  app_dist/               Built React app served at /app/
  assets/
    expert_videos/        Exercise videos and precomputed keypoint caches
    tts/                  Runtime final-feedback audio output
  latency_lab/            WebSocket latency measurement tools and reports
  s01_preprocessing/      Normalization, rep detection, DTW, scoring, feedback
  s02_backend/            FastAPI server and WebSocket orchestration
  s03_database/           Optional session persistence
  s05_frontend/           Viewer camera web page
  s07_tts/                TTS service
  scripts/                Install, build, run, latency, verify scripts
  src/                    React app source
```

## Viewer Logic

File:

```text
final/s05_frontend/viewer.js
```

Responsibilities:

- load TF.js MoveNet Lightning
- request camera permission
- detect pose from webcam
- normalize MoveNet pixel coordinates into `[y, x, confidence]`
- draw local skeleton immediately
- send keypoints to `/ws/pose`
- receive session control
- synchronize expert exercise pose

Important rule:

The viewer local draw must remain independent from server round trip. It is the
fastest way to confirm camera detection is working.

## Coordinate Rule

The server and app expect:

```text
[y, x, confidence]
```

MoveNet in the browser returns pixel coordinates, so viewer normalizes:

```javascript
[kp.y / videoHeight, kp.x / videoWidth, kp.score]
```

The app canvas converts normalized coordinates to canvas coordinates and applies
mirror only at draw time.

## Server Logic

File:

```text
final/s02_backend/server.py
```

Key WebSocket behavior:

1. Accept viewer and app WebSocket connections.
2. On `data_type: "keypoints"`, immediately broadcast `data_type: "pose"`.
3. Process only the latest frame for feedback to avoid queue delay.
4. Attach session progress.
5. Broadcast processed feedback.

Relay message:

```json
{
  "data_type": "pose",
  "keypoints_2d": [],
  "debug": {
    "relay_only": true,
    "client_timestamp_ms": 0,
    "server_received_ms": 0,
    "server_relay_sent_ms": 0
  }
}
```

Processed message includes:

- score
- rep_count
- progress
- message
- body_part
- severity
- bad_joints
- countable
- feedback_event

## Preprocessing Logic

Folder:

```text
final/s01_preprocessing/
```

Stages:

1. Camera visibility gate
2. Pose normalization
3. Rep detection
4. DTW comparison
5. Score update
6. Feedback analysis
7. Feedback hold policy

Camera gate:

```text
CAMERA_MIN_CONFIDENCE = 0.12
CAMERA_EDGE_MARGIN = 0.01
```

If camera visibility fails:

- message tells the user to fit the whole body in frame
- `countable = false`
- score and rep count do not advance

## Rep Counting Rule

Rep counting is not based on feedback text. It is based on exercise-specific
movement signals and minimum movement duration.

Relevant files:

```text
rep_detector.py
rep_rules.py
rep_signals.py
```

The app displays server progress instead of maintaining separate dummy counts.

## Feedback Rule

Real-time feedback must not fire every frame. The feedback policy holds a
detected feedback event for a short period so one movement section does not
produce hundreds of repeated warnings.

Relevant files:

```text
feedback/feedback_engine.py
feedback/feedback_policy.py
feedback/feedback_templates.py
```

Bad joints are sent to the app as `bad_joints` and rendered red.

## App Logic

Folder:

```text
final/src/
```

Used app files:

```text
App.tsx
components/ExerciseSelector.tsx
components/FeedbackChip.tsx
components/Hud.tsx
components/ResultPanel.tsx
components/ScoreRing.tsx
components/ScreenContainer.tsx
components/SetControl.tsx
components/SkeletonCanvas2D.tsx
hooks/useExpertPose2D.ts
hooks/useTimer.ts
hooks/useWebSocket.ts
services/ttsApi.ts
styles/global.css
utils/workoutProgress.ts
```

The app receives two types of server updates:

- relay pose for live movement
- processed feedback for score/reps/message/bad joints

## TTS Logic

Folder:

```text
final/s07_tts/
```

The final feedback screen requests `/api/tts/final-feedback`. The generated
audio is written under:

```text
final/assets/tts/
```

Old generated `.wav` files were removed. Runtime output is generated again when
the feature is used.

## Latency Architecture

Folder:

```text
final/latency_lab/
```

Measured paths:

- viewer sender to viewer relay echo
- viewer sender to app relay receive
- viewer sender to viewer processed feedback
- viewer sender to app processed feedback

Current baseline:

```json
{
  "local_relay_avg_ms": 4.235,
  "cloudflare_relay_avg_ms": 201.012,
  "local_processed_avg_ms": 9.509,
  "cloudflare_processed_avg_ms": 205.692
}
```

Interpretation:

Backend processing is not the main latency source in local testing. Domain
latency mostly comes from Cloudflare/network routing.

## Problems Solved

### App Lag

Cause:

Processed feedback and live movement were too tightly coupled.

Fix:

Immediate relay pose path was separated from processed feedback path.

### DTW Latency

Cause:

DTW is expensive if run as full sequence comparison every frame.

Fix:

Use intervals, latest-frame dropping, and shorter realtime windows.

### WebSocket Disconnect On Domain

Cause:

Viewer calculated `viewer.gun-hee.com` as the WebSocket host.

Fix:

Domain viewer uses:

```text
wss://pt.gun-hee.com/ws/pose
```

### MoveNet Fetch Block

Cause:

CSP did not allow all required model endpoints.

Fix:

Viewer CSP allows jsDelivr, TFHub, Google Storage, and Kaggle model URLs.

### Realtime Feedback Missing

Cause:

Camera visibility gate read non-existent `confidence_joints`.

Fix:

Gate now uses exercise `keypoints_used`.

### Recognition Felt Too Strict

Cause:

Server scoring gate confidence threshold was too high.

Fix:

Default gate lowered to `0.12`; edge margin lowered to `0.01`.

### Coordinate Regression

Cause:

An older viewer file was accidentally copied over final viewer code.

Fix:

Restored the final viewer logic and kept only the domain WebSocket URL patch.

## Build And Run

```powershell
.\final\scripts\01_install.ps1
.\final\scripts\02_build_app.ps1
.\final\scripts\03_run_server.ps1
```

Verify:

```powershell
.\final\scripts\05_verify.ps1
```

Latency:

```powershell
.\final\scripts\04_latency_check.ps1
```

## Development Rules

1. Do not merge relay pose and processed feedback paths.
2. Do not maintain separate app-side dummy rep counts.
3. Keep viewer camera draw local and immediate.
4. Keep coordinates as `[y, x, confidence]`.
5. Apply mirror only at canvas draw time.
6. Keep camera visibility failures out of score and rep count.
7. Keep red joint rendering based on server `bad_joints`.
8. Keep final feedback more detailed than real-time feedback.
9. Keep `final` independent from root `src`, `viewer_2d`, and root `latency_lab`.
