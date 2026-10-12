"""Exercise feedback logic based on fitted 3D joints."""

from __future__ import annotations

import math

import numpy as np

from model_3d.schemas import SquatFeedback


def angle_at_joint_deg(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """Return angle ABC in degrees, where B is the joint being measured."""
    ba = a - b
    bc = c - b
    denom = np.linalg.norm(ba) * np.linalg.norm(bc)
    if denom < 1e-8:
        return float("nan")
    cosine = float(np.dot(ba, bc) / denom)
    cosine = max(-1.0, min(1.0, cosine))
    return math.degrees(math.acos(cosine))


def analyze_squat(joints_3d: np.ndarray) -> SquatFeedback:
    """Simple squat-depth feedback from COCO hip-knee-ankle angles."""
    left_angle = angle_at_joint_deg(joints_3d[11], joints_3d[13], joints_3d[15])
    right_angle = angle_at_joint_deg(joints_3d[12], joints_3d[14], joints_3d[16])
    valid_angles = [value for value in [left_angle, right_angle] if not math.isnan(value)]

    if not valid_angles:
        return SquatFeedback("Unable to estimate knee angle", float("nan"), left_angle, right_angle)

    knee_angle = float(np.mean(valid_angles))
    if knee_angle >= 150.0:
        label = "Lower your hips"
    elif knee_angle < 60.0:
        label = "Raise your hips slightly"
    else:
        label = "Good"

    return SquatFeedback(label, knee_angle, left_angle, right_angle)
