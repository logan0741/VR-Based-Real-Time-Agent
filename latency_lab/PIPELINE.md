# Latency Lab Pipeline

## 1. Input Data

`data/sample_coco17_keypoints.json` contains one valid COCO-17 pose in the same
`[y, x, confidence]` shape that the viewer sends after MoveNet detection.

## 2. Viewer Sender Stage

`measure_latency.py` opens a WebSocket client that behaves like the viewer. It
sends animated synthetic keypoint frames with unique `frame_id` values.

## 3. App Receiver Stage

The same script opens a second WebSocket client that behaves like the app. It
does not send keypoints. It only receives broadcasts and measures when each
frame arrives.

## 4. Viewer Echo Stage

The sender socket also receives the broadcast. This measures what the viewer
would see after the server relay.

## 5. Split Measurements

The server sends two useful message classes:

- `relay_pose`: immediate live skeleton relay with `debug.relay_only=true`.
- `processed_feedback`: backend result after preprocessing, score, reps, and feedback.

The lab stores both separately for viewer and app.

## 6. Suite Stage

`run_latency_suite.py` runs the same probe twice:

- `ws://127.0.0.1:8000/ws/pose` for local backend latency.
- `wss://pt.gun-hee.com/ws/pose` for Cloudflare/domain latency.

## 7. Outputs

- `results/latency_report_local.json`
- `results/latency_report_cloudflare.json`
- `results/latency_suite_summary.json`
- Matching `.md` files for report use.
