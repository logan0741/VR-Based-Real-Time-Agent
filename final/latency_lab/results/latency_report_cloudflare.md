# App / Viewer Latency Report

- Created: `2026-06-13T01:42:21.256556+00:00`
- WebSocket URL: `wss://pt.gun-hee.com/ws/pose`
- Frames sent: `90`
- Target FPS: `30.0`
- Exercise: `squat`

## Result Summary

| Path | Count | Avg | Median | P90 | P95 | Max |
|---|---:|---:|---:|---:|---:|---:|
| viewer echo, live skeleton relay | 90 | 203.291 ms | 196.57 ms | 235.051 ms | 238.21 ms | 274.706 ms |
| app receive, live skeleton relay | 90 | 201.012 ms | 195.159 ms | 231.562 ms | 235.606 ms | 270.284 ms |
| viewer receive, processed feedback | 90 | 207.892 ms | 199.331 ms | 238.931 ms | 245.746 ms | 276.251 ms |
| app receive, processed feedback | 90 | 205.692 ms | 197.519 ms | 237.95 ms | 247.397 ms | 272.424 ms |

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
