"""Utilities for running the pipeline from the local pose_3d_v3 dataset."""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from model_3d.fitter import BasePoseFitter
from model_3d.schemas import FitResult


class DirectPose3DFitter(BasePoseFitter):
    """
    Fitter adapter that uses dataset 3D joints directly.

    This is for validating the analyzer/diagnostics pipeline with existing
    pose_3d_v3 coordinates. It bypasses SMPL-X optimization by design.
    """

    backend = "pose_3d_dataset"

    def forward(self, payload: Any) -> FitResult:
        if not isinstance(payload, dict):
            raise ValueError("DirectPose3DFitter expects a dict payload from pose_3d_v3.")

        joints_3d = np.asarray(payload["joints_3d"], dtype=np.float32)
        if joints_3d.shape != (17, 3):
            raise ValueError(f"joints_3d must have shape (17, 3). Received {joints_3d.shape}.")

        keypoints_2d = np.asarray(payload.get("keypoints_2d", joints_3d), dtype=np.float32)
        target_2d, confidence = pose3d_keypoints_to_pixels(keypoints_2d)

        return FitResult(
            backend=self.backend,
            joints_3d=joints_3d,
            projected_joints_2d=target_2d.copy(),
            target_joints_2d=target_2d,
            confidence=confidence,
            reprojection_loss=0.0,
            global_orient=np.zeros(3, dtype=np.float32),
            body_pose=np.zeros(63, dtype=np.float32),
            loss_history=[],
        )


def load_pose3d_frames(
    path: Path,
    split: str = "train",
    max_frames: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Load frame payloads from pose_3d_v3.

    Supported inputs:
        - pose_3d_v3 root directory
        - pose_3d_v3/frame_81/train directory
        - one frame-level .pkl containing data_input/data_label arrays
    """
    resolved = path.resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"pose_3d path not found: {resolved}")

    pkl_files = _resolve_pose3d_pkls(resolved, split)
    frames: List[Dict[str, Any]] = []
    for pkl_path in pkl_files:
        frames.extend(_load_pose3d_pkl(pkl_path, max_frames_remaining(max_frames, len(frames))))
        if max_frames is not None and len(frames) >= max_frames:
            return frames[:max_frames]

    if not frames:
        raise ValueError(f"No pose_3d frames loaded from {resolved}.")
    return frames


def pose3d_keypoints_to_pixels(keypoints: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Convert pose_3d_v3 x/y coordinates to 640x480 pixel space.

    pose_3d_v3 frame files store x/y in columns 0/1 and confidence or z in
    column 2. When x/y look normalized, scale them to image pixels.
    """
    if keypoints.shape != (17, 3):
        raise ValueError(f"keypoints must have shape (17, 3). Received {keypoints.shape}.")

    x = keypoints[:, 0].astype(np.float32)
    y = keypoints[:, 1].astype(np.float32)
    if max(float(np.max(np.abs(x))), float(np.max(np.abs(y)))) <= 1.5:
        x = x * 640.0
        y = y * 480.0

    confidence = keypoints[:, 2].astype(np.float32)
    if float(np.nanmin(confidence)) < 0.0 or float(np.nanmax(confidence)) > 1.0:
        confidence = np.ones(17, dtype=np.float32)
    confidence = np.clip(np.nan_to_num(confidence, nan=1.0), 0.0, 1.0)
    target_2d = np.stack((x, y), axis=-1).astype(np.float32)
    return target_2d, confidence


def _resolve_pose3d_pkls(path: Path, split: str) -> List[Path]:
    if path.is_file():
        return [path]

    split_dir = path / "frame_81" / split
    if split_dir.exists():
        return sorted(split_dir.glob("*.pkl"))

    direct_split_dir = path / split
    if direct_split_dir.exists():
        return sorted(direct_split_dir.glob("*.pkl"))

    pkl_files = sorted(path.glob("*.pkl"))
    if pkl_files:
        return pkl_files

    recursive_files = sorted(path.glob(f"**/{split}/*.pkl"))
    if recursive_files:
        return recursive_files

    return sorted(path.glob("**/*.pkl"))


def _load_pose3d_pkl(path: Path, max_items: Optional[int]) -> List[Dict[str, Any]]:
    with path.open("rb") as stream:
        data = pickle.load(stream)

    if not isinstance(data, dict) or "data_label" not in data:
        raise ValueError(f"{path} must contain a dict with data_label.")

    labels = np.asarray(data["data_label"], dtype=np.float32)
    inputs = np.asarray(data.get("data_input", labels), dtype=np.float32)

    if labels.ndim == 2:
        labels = labels[None, ...]
    if inputs.ndim == 2:
        inputs = inputs[None, ...]
    if labels.ndim != 3 or labels.shape[1:] != (17, 3):
        raise ValueError(f"{path} data_label must have shape (T, 17, 3). Received {labels.shape}.")

    count = labels.shape[0] if max_items is None else min(labels.shape[0], max_items)
    frames: List[Dict[str, Any]] = []
    for index in range(count):
        frames.append(
            {
                "frame_id": f"{path.stem}_{index:03d}",
                "payload": {
                    "source_path": str(path),
                    "source_index": index,
                    "joints_3d": labels[index],
                    "keypoints_2d": inputs[index],
                },
            }
        )
    return frames


def max_frames_remaining(max_frames: Optional[int], current_count: int) -> Optional[int]:
    if max_frames is None:
        return None
    return max(0, max_frames - current_count)
