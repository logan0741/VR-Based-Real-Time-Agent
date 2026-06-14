# Final Handoff Summary

The final implementation is documented in `FINAL_ARCHITECTURE.md`. This file
summarizes the latest handoff state and the exact run/push process used for the
current `final` folder.

## Current System

- `viewer` extracts COCO-17 keypoints from the phone camera.
- `server` immediately relays pose frames and separately processes feedback.
- `app` renders live 2D skeleton, reps, sets, score, red joints, final feedback, and TTS.
- `latency_lab` measures local versus domain WebSocket latency.
- `scripts/00_pipeline.ps1` is the one-command local pipeline entry point.

## Latest Fixes Included

1. Phone portrait display is viewer-local only.
   - The phone viewer may rotate the local preview when a portrait phone receives a landscape camera stream.
   - The WebSocket payload stays raw MoveNet `[y, x, confidence]`, so the app, scoring, and rep counter are not rotated by the viewer UI fix.

2. Expert pose canvas axis detection was aligned.
   - Expert `.npy` caches can be normalized or pixel-scale.
   - Viewer and app canvas logic both detect `[y, x, confidence]` before drawing.

3. App exercise selection and viewer expert pose now share one WebSocket backend on the domain.
   - `viewer.gun-hee.com` and `app.gun-hee.com` both use `wss://pt.gun-hee.com/ws/pose`.
   - App-side `session_config` broadcasts reach the phone viewer.
   - Viewer reloads `/api/expert?exercise=...` and updates the expert title when the selected exercise changes.

4. Set and rep target flow is no longer frontend-only.
   - The app sends both `sets` and selected `reps_per_set` through `session_config` and `session_start`.
   - The backend calculates `total_target_reps = sets * reps_per_set`.
   - The app auto-ends when backend progress reports `completed = true`.
   - The default reps-per-set remains the existing default of `8`; changing it on screen changes the backend target.

5. Final pipeline script was added.
   - `00_pipeline.ps1` runs verify/build and then starts the server.
   - `-Install` runs dependency install first.
   - `-NoServer` verifies/builds without starting uvicorn.

## Run

Standard local run:

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

Open after the server starts:

```text
http://127.0.0.1:8000/app/
http://127.0.0.1:8000/viewer/
http://127.0.0.1:8000/api/health
```

Domain URLs require the Cloudflare tunnel to be running:

```text
https://app.gun-hee.com/app/
https://viewer.gun-hee.com/viewer/
https://pt.gun-hee.com/api/health
```

## Validation Used

```powershell
.\final\scripts\00_pipeline.ps1 -NoServer
```

This executed:

- Python compile checks from `05_verify.ps1`
- React/TypeScript build through `npm --prefix final run build`

Additional targeted checks:

- `node --check final\s05_frontend\viewer.js`
- backend progress check with `sets=3`, `reps_per_set=2`, `total_reps=6`, which returned `completed: True`
- local HTTP checks for `/viewer/viewer.js`, `/app/`, and the generated app bundle

## Push Scope

Pushed to `origin/main`:

```text
db38f7aac Update final app session pipeline
```

Committed files were limited to the `final` code, docs, pipeline script, and
generated `app_dist` bundle needed to run the final app.

Not committed:

- root-level untracked prototype files
- runtime TTS outputs under `final/assets/tts/final_feedback_*.wav`
- Python `__pycache__` folders
