"""Input keypoint validation and conversion into camera pixel coordinates."""

from __future__ import annotations

import os
from typing import Any, Tuple

import numpy as np

from model_3d.camera import CameraIntrinsics


def parse_keypoints_payload(
    payload: Any, camera: CameraIntrinsics
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Convert MoveNet keypoints into pixel-space COCO [x, y] coordinates.

    Default input format is MoveNet's normalized [y, x, score]. If the VR client
    sends [x, y, score], set KEYPOINT_FORMAT=xy.
    """
    keypoint_format = os.getenv("KEYPOINT_FORMAT", "movenet_yx").strip().lower()
    array = np.asarray(payload, dtype=np.float32)

    if array.ndim > 2:
        array = array.reshape(-1, array.shape[-1])
    if array.ndim != 2 or array.shape[0] != 17 or array.shape[1] < 2:
        raise ValueError(
            "keypoints payload must be 17 rows of [y, x, score] or [x, y, score]. "
            f"Received shape {array.shape}."
        )

    if keypoint_format in {"movenet", "movenet_yx", "yx"}:
        y = array[:, 0]
        x = array[:, 1]
    elif keypoint_format in {"xy", "coco_xy"}:
        x = array[:, 0]
        y = array[:, 1]
    else:
        raise ValueError(
            f"Unsupported KEYPOINT_FORMAT={keypoint_format}. Use movenet_yx or xy."
        )

    confidence = array[:, 2] if array.shape[1] >= 3 else np.ones(17, dtype=np.float32)
    confidence = np.nan_to_num(confidence, nan=0.0, posinf=0.0, neginf=0.0)
    if float(np.nanmax(confidence)) > 1.0:
        confidence = np.ones(17, dtype=np.float32)
    confidence = np.clip(confidence, 0.0, 1.0).astype(np.float32)

    x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
    y = np.nan_to_num(y, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)

    # MoveNet commonly emits normalized coordinates. Pixel inputs are accepted.
    if max(float(np.max(np.abs(x))), float(np.max(np.abs(y)))) <= 1.5:
        x = x * float(camera.width)
        y = y * float(camera.height)

    target_2d = np.stack((x, y), axis=-1).astype(np.float32)
    return target_2d, confidence
