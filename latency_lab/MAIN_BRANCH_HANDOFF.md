# Main Branch Handoff

Use this folder as the latency feature source of truth.

## What To Copy First

1. Copy `latency_lab/implementation/00_shared` into the frontend shared area.
2. Copy `latency_lab/implementation/03_app` into the React app hooks area.
3. Apply `implementation/05_app_integration/useWebSocket.patch.md`.
4. Apply `implementation/06_viewer_integration/viewer_js.patch.md`.
5. Apply backend timestamp fields from `implementation/APPLY_TO_MAIN.md`.

## What To Run

```powershell
python -m py_compile final\s02_backend\server.py
npm run build
python latency_lab\run_latency_suite.py --frames 90 --fps 30 --exercise squat
```

## Expected Baseline From This Branch

- Local app relay average: around `4 ms`.
- Local app processed feedback average: around `10 ms`.
- Cloudflare app relay average: around `200 ms`.
- Cloudflare app processed feedback average: around `206 ms`.

Numbers can move with Wi-Fi, Quest browser load, and Cloudflare tunnel state.
The important comparison is local versus domain under the same frame count and
FPS.
