"""Small geometry helpers for COCO-17 keypoint angle calculations."""
from __future__ import annotations

import numpy as np


def angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """Return the 2D angle at point b in degrees."""
    ba = np.asarray(a[:2], dtype=np.float32) - np.asarray(b[:2], dtype=np.float32)
    bc = np.asarray(c[:2], dtype=np.float32) - np.asarray(b[:2], dtype=np.float32)
    denom = float(np.linalg.norm(ba) * np.linalg.norm(bc))
    if denom < 1e-6:
        return 180.0
    cosine = float(np.dot(ba, bc) / denom)
    return float(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0))))
