# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VR-based real-time personal trainer system. External camera captures exercise form → 2D pose estimation (MediaPipe) → 3D lifting (PoseLifterMLP) → SMPL-X avatar in Unity VR + web viewers with real-time coaching feedback.

**Target latency:** <100ms frame-to-feedback. **Target hardware:** Meta Quest 3 + PC.

## Commands

### Setup
```powershell
pip install -r requirements.txt
npm install                          # React dashboard only
cp .env.example .env                 # Configure DB, checkpoint path, smoothing
```

### Running the System
```powershell
# Environment check (Python, PyTorch, FastAPI, checkpoint)
python run_steps.py --check

# Start FastAPI server + 2D web viewer (primary workflow)
python run_steps.py --server
# Access: http://localhost:8000/viewer/ (Quest 3: http://<PC_IP>:8000/viewer/)

# Start with Cloudflare tunnel for remote/HTTPS access
python run_steps.py --cloudflare

# Train PoseLifterMLP (requires fitness dataset)
python run_steps.py --train

# Export Unity-ready JSON keyframe sequences
python run_steps.py --export-unity
```

### Input Clients (separate from server)
```powershell
python -m model_3d.server_app.clients.webcam_client     # Live webcam → /ws/pose
python -m model_3d.server_app.clients.video_client --video exercise.mp4
python play_squat.py                                     # Replay pre-extracted keypoints
```

### React Dashboard
```powershell
npm run dev     # Dev server
npm run build   # Build to /dist (served by FastAPI at /app/)
```

## Architecture

### Data Flow
```
Camera → MediaPipe (COCO-17 2D keypoints)
  → FastAPI WebSocket /ws/pose
    → PoseLifterMLP (2D→3D, outputs 66 SMPL-X pose params)
    → PoseRetargeter (OneEuro filter + velocity clamping)
    → PostureAnalyzer (joint angles, muscle fatigue labels)
    → MySQL (session persistence, optional)
  → Broadcast to clients:
      { fit: { global_orient[3], body_pose[63] }, feedback: { score, label } }
        → viewer_2d/ (Canvas skeleton + fatigue heatmap)
        → React dashboard (score ring + set counter)
        → Unity (SMPL-X avatar animation via WebSocketClient.cs)
```

### Key Components

| File | Role |
|------|------|
| `model_3d/server_app/server.py` | FastAPI server: loads checkpoint, runs inference, broadcasts frames |
| `model_3d/lifter_model.py` | PoseLifterMLP: PyTorch MLP that regresses 17 COCO joints → 66 SMPL-X params |
| `model_3d/pose_retargeting.py` | Temporal smoothing: OneEuro filter + velocity clamping to remove jitter |
| `model_3d/server_app/posture_analyzer.py` | Joint angle computation + muscle fatigue state machine |
| `model_3d/server_app/database.py` | MySQL schema + session/rep recording |
| `unity_integration/FitnessAvatarController.cs` | Applies `global_orient`+`body_pose` to SMPL-X Unity rig bones |
| `unity_integration/WebSocketClient.cs` | Connects Unity to FastAPI, deserializes JSON → avatar controller |
| `viewer_2d/viewer.js` | WebSocket consumer: draws skeleton on Canvas + shows score/fatigue |
| `src/App.tsx` | React dashboard: exercise selection → session → results |
| `run_steps.py` | Orchestrates all pipeline modes (server, train, export, check) |

### Coordinate Systems
- SMPL-X uses **right-handed** axes; Unity uses **left-handed**. `FitnessAvatarController.cs` handles the X-axis flip on import.
- Pose params are **axis-angle** format (not quaternions or Euler). Each joint is a 3-vector where the direction = rotation axis, magnitude = angle in radians.

### WebSocket Protocol
- **Client → Server:** `{ keypoints: [[x,y,conf], ...] }` (17 COCO-format joints, normalized 0–1)
- **Server → Client:** `{ status: "ok", fit: { global_orient, body_pose }, feedback: { score, label, details } }`
- Endpoint: `ws://host:8000/ws/pose`

## Configuration (.env)

Critical variables:
```bash
FITTER_BACKEND=lifter                  # "lifter" (MLP) is the only active backend
LIFTER_CHECKPOINT=model_3d/artifacts/checkpoints/fitness_pose_lifter_latest_best.pt
SMOOTHING_ENABLED=true
SMOOTHING_MIN_CUTOFF=1.0               # Lower = more smoothing, higher latency
SMOOTHING_BETA=0.007
SMOOTHING_MAX_VELOCITY=0.5
DB_ENABLED=true                        # Set false to skip MySQL
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=vr_fitness
KEYPOINT_FORMAT=movenet_yx             # Input joint ordering convention
```

## Development Notes

- The 2D viewer (`viewer_2d/`) is self-contained HTML/JS and works directly in Meta Quest 3's browser — no build step needed.
- Unity integration is Phase 2; the C# scripts in `unity_integration/` are standalone and must be manually placed in the Unity project's `Assets/Scripts/`.
- The React app (`src/`) is served by FastAPI as a static mount at `/app/` after `npm run build`.
- `run_steps.py` is the single entry point for all operational modes — prefer it over invoking server/train scripts directly.
- MySQL is optional; set `DB_ENABLED=false` in `.env` to run without a database.
- The model checkpoint must exist at the path in `LIFTER_CHECKPOINT` before starting the server. Train it with `--train` or obtain a pre-trained `.pt` file.
