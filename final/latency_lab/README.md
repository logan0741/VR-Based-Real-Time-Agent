# Latency Lab

This folder measures the actual `/ws/pose` path used by the final app.

## Run

```powershell
python final\latency_lab\run_latency_suite.py --frames 90 --fps 30 --exercise squat
```

## Outputs

- `results/latency_report_local.json`
- `results/latency_report_cloudflare.json`
- `results/latency_suite_summary.json`
- Matching `.md` report files

## Measurement Scope

Included:

- viewer-style keypoint WebSocket send
- server immediate relay broadcast
- server processed feedback broadcast
- app-style receive timing

Not included:

- browser camera permission time
- TF.js MoveNet inference time
- canvas drawing time

## Baseline From Current Final Build

- Local app relay average: about `4 ms`
- Local app processed feedback average: about `10 ms`
- Cloudflare app relay average: about `200 ms`
- Cloudflare app processed feedback average: about `206 ms`
