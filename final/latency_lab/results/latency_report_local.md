# App / Viewer Latency Report

- Created: `2026-06-13T01:42:12.353083+00:00`
- WebSocket URL: `ws://127.0.0.1:8000/ws/pose`
- Frames sent: `90`
- Target FPS: `30.0`
- Exercise: `squat`

## Result Summary

| Path | Count | Avg | Median | P90 | P95 | Max |
|---|---:|---:|---:|---:|---:|---:|
| viewer echo, live skeleton relay | 90 | 4.034 ms | 2.757 ms | 3.73 ms | 5.504 ms | 61.169 ms |
| app receive, live skeleton relay | 90 | 4.235 ms | 2.957 ms | 3.901 ms | 5.607 ms | 61.337 ms |
| viewer receive, processed feedback | 90 | 9.289 ms | 5.588 ms | 9.262 ms | 35.081 ms | 68.84 ms |
| app receive, processed feedback | 90 | 9.509 ms | 5.781 ms | 9.498 ms | 35.33 ms | 69.166 ms |

## Delivery Counts

- Relay frames at viewer: `90`
- Relay frames at app: `90`
- Processed frames at viewer: `90`
- Processed frames at app: `90`

## Interpretation

- The relay path is the live 2D skeleton path. This should stay close to real time.
- The processed feedback path includes backend preprocessing, rep counting, scoring, and feedback policy.
- If processed frame count is lower than sent frames, it is expected when the backend drops old frames and keeps the latest frame.
- Browser TF.js pose extraction and canvas rendering are outside this synthetic measurement.
