"""종목별 운동 설정 딕셔너리."""
from __future__ import annotations

from pathlib import Path

from .utils.keypoints import (
    LEFT_SHOULDER, RIGHT_SHOULDER,
    LEFT_ELBOW, RIGHT_ELBOW,
    LEFT_WRIST, RIGHT_WRIST,
    LEFT_HIP, RIGHT_HIP,
    LEFT_KNEE, RIGHT_KNEE,
    LEFT_ANKLE, RIGHT_ANKLE,
)

_ASSETS = Path(__file__).resolve().parents[2] / "final" / "assets" / "expert_videos"

EXERCISES: dict[str, dict] = {
    "squat": {
        "video_path": str(_ASSETS / "squat_full.mp4"),
        "normalizer_type": "side_left",
        "keypoints_used": [
            LEFT_SHOULDER, RIGHT_SHOULDER,
            LEFT_HIP, RIGHT_HIP,
            LEFT_KNEE, RIGHT_KNEE,
            LEFT_ANKLE, RIGHT_ANKLE,
        ],
        "weights": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
        "target_fps": 24,
        "n_frames": 30,
        "max_distance": 1.35,
        "rep_detector_type": "squat",
        "norm_buffer_size": 7,
        "rep_slope_window": 9,
        "min_rep_frames": 14,
        "dtw_interval": 3,
        "view": "side",
        "implemented": True,
    },
    "hammer_curl": {
        # 백엔드 DTW 로직 미구현 — implemented=False 확인 후 stub 피드백 반환
        "video_path": str(_ASSETS / "hammer_curl.mp4"),
        "normalizer_type": "side_left",
        "keypoints_used": [LEFT_SHOULDER, LEFT_ELBOW, LEFT_WRIST],
        "weights": [1.0, 1.0, 1.0],
        "target_fps": 30,
        "n_frames": 45,
        "max_distance": 1.35,
        "rep_detector_type": "hammer_curl",
        "norm_buffer_size": 7,
        "rep_slope_window": 8,
        "min_rep_frames": 12,
        "dtw_interval": 3,
        "view": "side",
        "implemented": True,
    },
    "pullup": {
        # Expert video, rep detector, and feedback config are available.
        "video_path": str(_ASSETS / "pull_up.mp4"),
        "normalizer_type": "front",
        "keypoints_used": [LEFT_SHOULDER, RIGHT_SHOULDER, LEFT_ELBOW, RIGHT_ELBOW],
        "weights": [1.0, 1.0, 1.0, 1.0],
        "target_fps": 30,
        "n_frames": 90,
        "max_distance": 1.35,
        "rep_detector_type": "pullup",
        "norm_buffer_size": 7,
        "rep_slope_window": 12,
        "min_rep_frames": 24,
        "dtw_interval": 3,
        "view": "front",
        "implemented": True,
    },
    "lateral_raise": {
        # 백엔드 DTW 로직 미구현 — implemented=False 확인 후 stub 피드백 반환
        "video_path": str(_ASSETS / "lateral_raise.mp4"),
        "normalizer_type": "front",
        "keypoints_used": [LEFT_SHOULDER, RIGHT_SHOULDER, LEFT_ELBOW, RIGHT_ELBOW],
        "weights": [1.0, 1.0, 1.0, 1.0],
        "target_fps": 30,
        "n_frames": 45,
        "max_distance": 1.35,
        "rep_detector_type": "lateral_raise",
        "norm_buffer_size": 7,
        "rep_slope_window": 8,
        "min_rep_frames": 12,
        "dtw_interval": 3,
        "view": "front",
        "implemented": True,
    },
}
