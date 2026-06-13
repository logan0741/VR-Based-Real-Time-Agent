# Report: Overall System Structure

## Overview

The final system is a browser-based 2D real-time exercise feedback pipeline.
The phone acts as the camera viewer, the backend acts as the relay and analysis
engine, and the Quest/app browser renders the workout interface.

## Overall Diagram

```text
                +--------------------------+
                | Phone Viewer Browser     |
                | final/s05_frontend       |
                | - webcam                 |
                | - TF.js MoveNet          |
                | - local skeleton draw    |
                +-------------+------------+
                              |
                              | COCO-17 keypoints
                              | WebSocket /ws/pose
                              v
                +-------------+------------+
                | FastAPI Backend          |
                | final/s02_backend        |
                | - connection manager     |
                | - immediate relay        |
                | - preprocessing session  |
                | - session progress       |
                +------+------+------------+
                       |      |
       relay pose -----+      +----- processed feedback
                       |            score/reps/bad_joints
                       v
                +------+-------------------+
                | Quest/App Browser        |
                | final/src + app_dist     |
                | - live 2D skeleton       |
                | - expert pose            |
                | - score/reps/sets        |
                | - final feedback + TTS   |
                +--------------------------+
```

## Runtime Responsibility

| Layer | Folder | Responsibility |
|---|---|---|
| Viewer | `s05_frontend` | Camera, MoveNet, local skeleton draw, keypoint send |
| Backend | `s02_backend` | WebSocket relay, API, session control |
| Preprocessing | `s01_preprocessing` | Normalize, count reps, score, feedback |
| App | `src`, `app_dist` | Quest UI and live feedback display |
| TTS | `s07_tts` | Final feedback audio generation |
| Assets | `assets` | Expert videos/keypoints and runtime audio |
| Latency | `latency_lab` | Local/domain latency measurement |

## Key Design Choice

The system has two data paths:

- **Immediate relay path** for live skeleton movement.
- **Processed feedback path** for score, reps, feedback, and red joints.

This split is the main latency-control decision.
