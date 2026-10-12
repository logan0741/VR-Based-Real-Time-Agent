# App / Viewer Latency Lab

This folder is a standalone latency measurement pipeline for the current
`/ws/pose` flow.

## What It Measures

- `viewer_sender`: a synthetic viewer camera client sends COCO-17 keypoints.
- `viewer_echo`: latency until the sender receives the server relay broadcast.
- `app_receiver`: latency until a separate app-like client receives the same relay.
- `processed_feedback`: latency until the backend preprocessing result is broadcast.

The relay path represents the live skeleton path. The processed path represents
feedback, score, reps, and final app state updates.

## Run

```powershell
cd latency_lab
python -m pip install -r requirements.txt
python measure_latency.py --ws-url wss://pt.gun-hee.com/ws/pose --frames 90 --fps 30
```

For local testing:

```powershell
python measure_latency.py --ws-url ws://127.0.0.1:8000/ws/pose --frames 90 --fps 30
```

## Output

- `results/latency_report.json`: raw summary, per-frame samples, and environment data.
- `results/latency_report.md`: report-style summary for documentation.
- `results/latency_report_local.json`: local backend measurement.
- `results/latency_report_cloudflare.json`: Cloudflare/domain measurement.
- `results/latency_suite_summary.json`: local vs domain comparison.

## Implementation Kit

`implementation/` contains the web/backend code split by pipeline stage:

- shared telemetry helpers
- viewer send instrumentation
- backend timestamp fields
- app receive metrics hook
- JSON report writer
- app/viewer integration notes

## Notes

This does not include TF.js MoveNet camera inference time in the browser. It
measures the network and backend broadcast path after keypoints have already
been produced by the viewer.
