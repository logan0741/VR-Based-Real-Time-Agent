"""Small data containers used across the 3D pose pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np


COCO_17_NAMES = [
    "nose",
    "left_eye",
    "right_eye",
    "left_ear",
    "right_ear",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
]


COCO_SKELETON = [
    (0, 1),
    (0, 2),
    (1, 3),
    (2, 4),
    (5, 6),
    (5, 7),
    (7, 9),
    (6, 8),
    (8, 10),
    (5, 11),
    (6, 12),
    (11, 12),
    (11, 13),
    (13, 15),
    (12, 14),
    (14, 16),
]


@dataclass
class FitResult:
    """CPU-owned result object. Never store GPU tensors in this dataclass."""

    backend: str
    joints_3d: np.ndarray
    projected_joints_2d: np.ndarray
    target_joints_2d: np.ndarray
    confidence: np.ndarray
    reprojection_loss: float
    global_orient: np.ndarray
    body_pose: np.ndarray
    loss_history: List[float] = field(default_factory=list)
    vertices: Optional[np.ndarray] = None


@dataclass
class SquatFeedback:
    label: str
    knee_angle_deg: float
    left_knee_angle_deg: float
    right_knee_angle_deg: float
