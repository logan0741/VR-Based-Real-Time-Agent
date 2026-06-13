# Report: Component Structures

## Viewer Component

```text
s05_frontend/
  index.html
  style.css
  viewer.js
```

```text
viewer.js
  -> startCamera()
  -> getCameraStream()
  -> detectLoop()
  -> normalize MoveNet pixel coords
  -> drawSkeleton()
  -> ws.send(keypoints)
```

The viewer must keep drawing locally even when backend latency changes.

## Backend Component

```text
s02_backend/
  server.py
  config.py
  pose_retargeting.py
  posture_analyzer.py
  session_progress.py
```

```text
websocket_endpoint()
  -> manager.connect()
  -> receive keypoints
  -> broadcast relay pose
  -> process_latest_keypoints()
  -> attach progress
  -> broadcast feedback
```

## Preprocessing Component

```text
s01_preprocessing/
  config.py
  pose_normalizer.py
  rep_detector.py
  rep_rules.py
  rep_signals.py
  dtw_comparator.py
  score_engine.py
  expert_cache.py
  feedback/
```

```text
PreprocessingSession.process()
  -> camera visibility gate
  -> PoseNormalizer
  -> RepDetector
  -> DTWComparator
  -> ScoreEngine
  -> FeedbackEngine
  -> FeedbackPolicy
```

## App Component

```text
src/
  App.tsx
  components/
  hooks/
  services/
  styles/
  utils/
```

```text
useWebSocket()
  -> receive relay pose
  -> merge pose with latest feedback
  -> receive processed feedback
  -> expose latestFrame to App

App.tsx
  -> ExerciseSelector
  -> SkeletonCanvas2D
  -> Hud
  -> FeedbackChip
  -> ResultPanel
```

## TTS Component

```text
s07_tts/
  tts_service.py
```

```text
ResultPanel
  -> services/ttsApi.ts
  -> /api/tts/final-feedback
  -> s07_tts
  -> assets/tts/*.wav
```

## Latency Component

```text
latency_lab/
  measure_latency.py
  run_latency_suite.py
  data/sample_coco17_keypoints.json
  results/*.json
```

```text
run_latency_suite.py
  -> local ws://127.0.0.1:8000/ws/pose
  -> cloud wss://pt.gun-hee.com/ws/pose
  -> compare relay and processed paths
```
