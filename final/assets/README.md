# Assets

This folder contains runtime assets for the final 2D pose feedback system.

## Structure

```text
assets/
  expert_videos/
    squat_full.mp4
    squat_full.npy
    squat.mp4
    hammer_curl.mp4
    hammer_curl.npy
    lateral_raise.mp4
    lateral_raise.npy
    pull_up.mp4
    pull_up.npy
  tts/
    .gitkeep
    runtime final_feedback_*.wav files
```

## Expert Videos And Keypoint Caches

`expert_videos` provides reference motion for supported exercises.

The backend uses these assets through:

```text
final/s01_preprocessing/config.py
final/s01_preprocessing/expert_cache.py
final/s02_backend/server.py
```

Supported final exercises:

| Exercise | Video | Cache |
|---|---|---|
| Squat | `squat_full.mp4` | `squat_full.npy` |
| Hammer curl | `hammer_curl.mp4` | `hammer_curl.npy` |
| Lateral raise | `lateral_raise.mp4` | `lateral_raise.npy` |
| Pull-up | `pull_up.mp4` | `pull_up.npy` |

## TTS Output

`tts/` is the runtime output folder for final feedback audio.

Old generated `.wav` files are intentionally not stored as source. The server
creates new files when the app requests final feedback TTS.

## Current Rule

This final build no longer depends on SMPLX/Unity runtime assets. Keep this
folder focused on 2D expert references and final-feedback audio output.
