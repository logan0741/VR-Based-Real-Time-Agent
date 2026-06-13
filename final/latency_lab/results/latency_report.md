# App / Viewer Latency Report

- Created: `2026-06-13T01:40:25.871125+00:00`
- WebSocket URL: `ws://127.0.0.1:8000/ws/pose`
- Frames sent: `90`
- Target FPS: `30.0`
- Exercise: `squat`

## Result Summary

| Path | Count | Avg | Median | P90 | P95 | Max |
|---|---:|---:|---:|---:|---:|---:|
| viewer echo, live skeleton relay | 90 | 3.767 ms | 2.736 ms | 4.266 ms | 4.948 ms | 32.48 ms |
| app receive, live skeleton relay | 90 | 3.991 ms | 2.969 ms | 4.617 ms | 5.11 ms | 32.556 ms |
| viewer receive, processed feedback | 90 | 9.062 ms | 5.774 ms | 8.889 ms | 32.219 ms | 68.281 ms |
| app receive, processed feedback | 90 | 9.263 ms | 5.937 ms | 9.092 ms | 32.456 ms | 68.54 ms |

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
