# Final Handoff Summary

The final implementation is documented in `FINAL_ARCHITECTURE.md`.

Short version:

- `viewer` extracts COCO-17 keypoints from the phone camera.
- `server` immediately relays pose frames and separately processes feedback.
- `app` renders live 2D skeleton, reps, sets, score, red joints, final feedback, and TTS.
- `latency_lab` measures local versus domain WebSocket latency.

Use:

```powershell
.\final\scripts\05_verify.ps1
.\final\scripts\03_run_server.ps1
```
