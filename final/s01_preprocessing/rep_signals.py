"""Map normalized keypoint frames to exercise-specific rep signals."""
from __future__ import annotations

import numpy as np

from .joint_angles import angle
from .utils.keypoints import (
    LEFT_ANKLE,
    LEFT_ELBOW,
    LEFT_HIP,
    LEFT_KNEE,
    LEFT_SHOULDER,
    LEFT_WRIST,
    RIGHT_ANKLE,
    RIGHT_ELBOW,
    RIGHT_HIP,
    RIGHT_KNEE,
    RIGHT_SHOULDER,
    RIGHT_WRIST,
)


def extract_rep_signal(rep_type: str, normalizer_type: str, norm_frame: np.ndarray) -> float:
    if rep_type == "squat":
        left = angle(norm_frame[LEFT_HIP], norm_frame[LEFT_KNEE], norm_frame[LEFT_ANKLE])
        right = angle(norm_frame[RIGHT_HIP], norm_frame[RIGHT_KNEE], norm_frame[RIGHT_ANKLE])
        return _side_or_average(left, right, normalizer_type)

    if rep_type == "hammer_curl":
        left = angle(norm_frame[LEFT_SHOULDER], norm_frame[LEFT_ELBOW], norm_frame[LEFT_WRIST])
        right = angle(norm_frame[RIGHT_SHOULDER], norm_frame[RIGHT_ELBOW], norm_frame[RIGHT_WRIST])
        return _side_or_average(left, right, normalizer_type)

    if rep_type == "pullup":
        left = angle(norm_frame[LEFT_SHOULDER], norm_frame[LEFT_ELBOW], norm_frame[LEFT_WRIST])
        right = angle(norm_frame[RIGHT_SHOULDER], norm_frame[RIGHT_ELBOW], norm_frame[RIGHT_WRIST])
        return (left + right) / 2.0

    if rep_type == "lateral_raise":
        left = angle(norm_frame[LEFT_HIP], norm_frame[LEFT_SHOULDER], norm_frame[LEFT_WRIST])
        right = angle(norm_frame[RIGHT_HIP], norm_frame[RIGHT_SHOULDER], norm_frame[RIGHT_WRIST])
        return (left + right) / 2.0

    return 0.0


def _side_or_average(left: float, right: float, normalizer_type: str) -> float:
    if normalizer_type == "side_left":
        return left
    if normalizer_type == "side_right":
        return right
    return (left + right) / 2.0
