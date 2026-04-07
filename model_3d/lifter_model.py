"""Trainable 2D-to-3D pose lifting model for pose_3d_v3."""

from __future__ import annotations

import json
import pickle
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

try:
    import torch
    from torch import nn
    from torch.utils.data import Dataset
except ImportError:  # pragma: no cover - commands raise a clear error when used.
    torch = None
    nn = None
    Dataset = object

from model_3d.camera import CameraIntrinsics
from model_3d.fitter import BasePoseFitter
from model_3d.preprocessing import parse_keypoints_payload
from model_3d.schemas import FitResult


class PoseLifterMLP(nn.Module if nn is not None else object):
    """Small residual MLP that maps flattened 17x3 2D keypoints to 17x3 3D joints."""

    def __init__(self, hidden_dim: int = 512, num_layers: int = 4, dropout: float = 0.1) -> None:
        if nn is None:
            raise RuntimeError("torch is required to create PoseLifterMLP.")
        super().__init__()
        layers: List[nn.Module] = []
        in_dim = 17 * 3
        for layer_index in range(num_layers):
            layers.append(nn.Linear(in_dim if layer_index == 0 else hidden_dim, hidden_dim))
            layers.append(nn.LayerNorm(hidden_dim))
            layers.append(nn.GELU())
            layers.append(nn.Dropout(dropout))
        layers.append(nn.Linear(hidden_dim, 17 * 3))
        self.network = nn.Sequential(*layers)

    def forward(self, keypoints_2d: Any) -> Any:
        batch_size = keypoints_2d.shape[0]
        flattened = keypoints_2d.reshape(batch_size, -1)
        return self.network(flattened).reshape(batch_size, 17, 3)


class Pose3DFrameDataset(Dataset):
    """Frame-level dataset backed by pose_3d_v3/frame_81/*.pkl files."""

    def __init__(
        self,
        root: Path,
        split: str,
        max_files: Optional[int] = None,
        cache_size: int = 32,
    ) -> None:
        if torch is None:
            raise RuntimeError("torch is required to use Pose3DFrameDataset.")
        self.files = resolve_pose3d_frame_files(root, split)
        if max_files is not None:
            self.files = self.files[:max_files]
        if not self.files:
            raise FileNotFoundError(f"No pose_3d_v3 frame files found for split={split} under {root}.")

        self.split = split
        self.frames_per_file = _frame_count(self.files[0])
        self.cache_size = max(1, cache_size)
        self._cache: OrderedDict[Path, Tuple[np.ndarray, np.ndarray]] = OrderedDict()

    def __len__(self) -> int:
        return len(self.files) * self.frames_per_file

    def __getitem__(self, index: int) -> Dict[str, Any]:
        file_index = index // self.frames_per_file
        frame_index = index % self.frames_per_file
        data_input, data_label = self._load_file(self.files[file_index])
        x = data_input[frame_index].astype(np.float32)
        y = data_label[frame_index].astype(np.float32)
        return {
            "input": torch.from_numpy(x),
            "target": torch.from_numpy(y),
            "source": str(self.files[file_index]),
            "frame_index": frame_index,
        }

    def _load_file(self, path: Path) -> Tuple[np.ndarray, np.ndarray]:
        cached = self._cache.get(path)
        if cached is not None:
            self._cache.move_to_end(path)
            return cached

        with path.open("rb") as stream:
            payload = pickle.load(stream)
        if not isinstance(payload, dict) or "data_input" not in payload or "data_label" not in payload:
            raise ValueError(f"{path} must contain data_input and data_label arrays.")

        data_input = np.asarray(payload["data_input"], dtype=np.float32)
        data_label = np.asarray(payload["data_label"], dtype=np.float32)
        if data_input.shape != data_label.shape or data_input.shape[1:] != (17, 3):
            raise ValueError(
                f"{path} data_input/data_label must both have shape (T, 17, 3). "
                f"Received {data_input.shape} and {data_label.shape}."
            )

        self._cache[path] = (data_input, data_label)
        if len(self._cache) > self.cache_size:
            self._cache.popitem(last=False)
        return data_input, data_label


class PoseLifterFitter(BasePoseFitter):
    """PosePipeline adapter that runs a trained PoseLifterMLP checkpoint."""

    backend = "pose_lifter_mlp"

    def __init__(self, checkpoint_path: Path, device: Optional[str] = None) -> None:
        if torch is None:
            raise RuntimeError("torch is required to run PoseLifterFitter.")
        self.checkpoint_path = checkpoint_path
        checkpoint = load_lifter_checkpoint(checkpoint_path, device=device)
        self.device = checkpoint["device"]
        self.model = checkpoint["model"]
        self.model.eval()
        self.camera = CameraIntrinsics()

    def forward(self, payload: Any) -> FitResult:
        target_2d, confidence = parse_keypoints_payload(payload, self.camera)
        model_input = pixels_to_normalized_lifter_input(target_2d, confidence)
        tensor = torch.from_numpy(model_input[None, ...]).to(self.device)
        with torch.no_grad():
            prediction = self.model(tensor)[0].detach().cpu().numpy().astype(np.float32)

        projected_2d, _ = pose3d_prediction_to_pixels(prediction, confidence)
        reprojection_loss = float(np.mean(np.sum((projected_2d - target_2d) ** 2, axis=1)))
        return FitResult(
            backend=self.backend,
            joints_3d=prediction,
            projected_joints_2d=projected_2d,
            target_joints_2d=target_2d,
            confidence=confidence,
            reprojection_loss=reprojection_loss,
            global_orient=np.zeros(3, dtype=np.float32),
            body_pose=np.zeros(63, dtype=np.float32),
            loss_history=[],
        )


def resolve_pose3d_frame_files(root: Path, split: str) -> List[Path]:
    resolved = root.resolve()
    if resolved.is_file():
        return [resolved]

    candidates = [
        resolved / "frame_81" / split,
        resolved / split,
    ]
    for candidate in candidates:
        if candidate.exists():
            files = sorted(candidate.glob("*.pkl"))
            if files:
                return files

    files = sorted(resolved.glob(f"**/{split}/*.pkl"))
    if files:
        return files
    return sorted(resolved.glob("*.pkl"))


def mpjpe(prediction: Any, target: Any) -> Any:
    """Mean per-joint position error."""
    return torch.linalg.norm(prediction - target, dim=-1).mean()


def save_lifter_checkpoint(
    path: Path,
    model: Any,
    optimizer: Any,
    epoch: int,
    config: Dict[str, Any],
    metrics: Dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state": model.state_dict(),
            "optimizer_state": optimizer.state_dict() if optimizer is not None else None,
            "epoch": epoch,
            "config": config,
            "metrics": metrics,
        },
        path,
    )


def load_lifter_checkpoint(checkpoint_path: Path, device: Optional[str] = None) -> Dict[str, Any]:
    if torch is None:
        raise RuntimeError("torch is required to load a pose lifter checkpoint.")
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")

    resolved_device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
    try:
        checkpoint = torch.load(checkpoint_path, map_location=resolved_device, weights_only=True)
    except TypeError:
        checkpoint = torch.load(checkpoint_path, map_location=resolved_device)
    config = checkpoint.get("config", {})
    model = PoseLifterMLP(
        hidden_dim=int(config.get("hidden_dim", 512)),
        num_layers=int(config.get("num_layers", 4)),
        dropout=float(config.get("dropout", 0.1)),
    ).to(resolved_device)
    model.load_state_dict(checkpoint["model_state"])
    return {
        "model": model,
        "device": resolved_device,
        "checkpoint": checkpoint,
    }


def pixels_to_normalized_lifter_input(points_2d: np.ndarray, confidence: np.ndarray) -> np.ndarray:
    x = points_2d[:, 0].astype(np.float32) / 640.0
    y = points_2d[:, 1].astype(np.float32) / 480.0
    conf = confidence.astype(np.float32)
    return np.stack((x, y, conf), axis=-1).astype(np.float32)


def pose3d_prediction_to_pixels(joints_3d: np.ndarray, confidence: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    x = joints_3d[:, 0].astype(np.float32)
    y = joints_3d[:, 1].astype(np.float32)
    if max(float(np.max(np.abs(x))), float(np.max(np.abs(y)))) <= 1.5:
        x = x * 640.0
        y = y * 480.0
    points = np.stack((x, y), axis=-1).astype(np.float32)
    return points, confidence.astype(np.float32)


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def _frame_count(path: Path) -> int:
    with path.open("rb") as stream:
        payload = pickle.load(stream)
    data_input = np.asarray(payload["data_input"])
    if data_input.ndim != 3:
        raise ValueError(f"{path} data_input must have shape (T, 17, 3).")
    return int(data_input.shape[0])
