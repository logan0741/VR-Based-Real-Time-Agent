# VR Real-Time Pose App Final

`final` is the standalone production folder for the current 2D real-time pose
feedback system.

## Run

One-command pipeline:

```powershell
.\final\scripts\00_pipeline.ps1
```

First-time setup:

```powershell
.\final\scripts\00_pipeline.ps1 -Install
```

Verify/build without starting the server:

```powershell
.\final\scripts\00_pipeline.ps1 -NoServer
```

The pipeline verifies Python files, builds the React app, then starts the
FastAPI server in the current PowerShell window.

Manual steps:

```powershell
.\final\scripts\01_install.ps1
.\final\scripts\02_build_app.ps1
.\final\scripts\03_run_server.ps1
```

Open:

```text
http://127.0.0.1:8000/app/
http://127.0.0.1:8000/viewer/
http://127.0.0.1:8000/api/health
```

Domain, when Cloudflare tunnel is running:

```text
https://app.gun-hee.com/app/
https://viewer.gun-hee.com/viewer/
https://pt.gun-hee.com/api/health
```

## Verify

```powershell
.\final\scripts\05_verify.ps1
```

## Core Structure

```text
final/
  app_dist/              React production build served at /app/
  assets/                Expert videos/keypoints and runtime TTS output
  latency_lab/           Local/domain WebSocket latency measurement
  s01_preprocessing/     Normalization, rep detection, scoring, feedback
  s02_backend/           FastAPI server, WebSocket relay, session control
  s03_database/          Optional MySQL session persistence
  s05_frontend/          Phone viewer page with TF.js MoveNet camera
  s07_tts/               Final feedback TTS service
  scripts/               Install/build/run/verify scripts
  src/                   React Quest/app source
```

## Main Documents

- `FINAL_ARCHITECTURE.md`: final architecture, rules, logic, troubleshooting.
- `REPORT_SYSTEM_STRUCTURE.md`: report-ready overall system structure.
- `REPORT_COMPONENT_STRUCTURES.md`: report-ready component-by-component structure.
- `PIPELINE.md`: runtime pipeline summary.
