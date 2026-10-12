"""Trainable 2D-to-3D pose lifting models and dataset adapters."""

from __future__ import annotations

import json
import pickle
from collections import OrderedDict
from pathlib import Path, PurePosixPath
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


COCO_17_JOINT_NAMES: Tuple[str, ...] = (
    "Nose",
    "Left Eye",
    "Right Eye",
    "Left Ear",
    "Right Ear",
    "Left Shoulder",
    "Right Shoulder",
    "Left Elbow",
    "Right Elbow",
    "Left Wrist",
    "Right Wrist",
    "Left Hip",
    "Right Hip",
    "Left Knee",
    "Right Knee",
    "Left Ankle",
    "Right Ankle",
)

DEFAULT_FITNESS_IMAGE_SIZE: Tuple[int, int] = (1920, 1080)


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


class FitnessLabelDataset(Dataset):
    """Frame/view-level dataset backed by the prepared fitness JSON labels."""

    def __init__(
        self,
        root: Path,
        split: str,
        max_files: Optional[int] = None,
    ) -> None:
        if torch is None:
            raise RuntimeError("torch is required to use FitnessLabelDataset.")

        resolved_split = resolve_fitness_split(root, split)
        self.root = root.resolve()
        self.split = resolved_split
        self.label_pairs = resolve_fitness_label_pairs(self.root, resolved_split)
        if max_files is not None:
            self.label_pairs = self.label_pairs[:max_files]
        if not self.label_pairs:
            raise FileNotFoundError(f"No fitness label pairs found for split={resolved_split} under {root}.")

        self.samples = load_fitness_samples(self.root, resolved_split, self.label_pairs)
        if not self.samples:
            raise ValueError(f"No training samples were parsed from {root} split={resolved_split}.")

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> Dict[str, Any]:
        sample = self.samples[index]
        return {
            "input": torch.from_numpy(sample["input"]),
            "target": torch.from_numpy(sample["target"]),
            "source": sample["source"],
            "frame_index": sample["frame_index"],
            "view": sample["view"],
            "image_path": sample["image_path"],
        }


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
        model_input = pixels_to_normalized_lifter_input(
            target_2d,
            confidence,
            width=float(self.camera.width),
            height=float(self.camera.height),
        )
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


def detect_training_dataset_format(root: Path) -> str:
    resolved = root.resolve()
    if (resolved / "labels").exists():
        return "fitness_json"
    if resolve_pose3d_frame_files(resolved, "train"):
        return "pose3d_v3"
    raise FileNotFoundError(f"Could not infer a supported dataset format under {resolved}.")


def build_pose_lifter_dataset(
    root: Path,
    split: str,
    max_files: Optional[int] = None,
    dataset_format: str = "auto",
) -> Dataset:
    resolved = root.resolve()
    detected_format = detect_training_dataset_format(resolved) if dataset_format == "auto" else dataset_format
    if detected_format == "pose3d_v3":
        return Pose3DFrameDataset(resolved, split=split, max_files=max_files)
    if detected_format == "fitness_json":
        return FitnessLabelDataset(resolved, split=split, max_files=max_files)
    raise ValueError(f"Unsupported dataset_format={detected_format}.")


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


def pixels_to_normalized_lifter_input(
    points_2d: np.ndarray,
    confidence: np.ndarray,
    width: float = 640.0,
    height: float = 480.0,
) -> np.ndarray:
    x = points_2d[:, 0].astype(np.float32) / max(1.0, float(width))
    y = points_2d[:, 1].astype(np.float32) / max(1.0, float(height))
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


def resolve_fitness_split(root: Path, split: str) -> str:
    requested = split.strip().lower()
    split_dir = root / "labels" / requested
    if split_dir.exists():
        return requested

    aliases = {
        "valid": "val",
        "validation": "val",
        "test": "val",
    }
    aliased = aliases.get(requested)
    if aliased and (root / "labels" / aliased).exists():
        return aliased
    raise FileNotFoundError(f"Fitness split={split} was not found under {root / 'labels'}.")


def resolve_fitness_label_pairs(root: Path, split: str) -> List[Tuple[Path, Path]]:
    label_dir = root / "labels" / split
    pairs: List[Tuple[Path, Path]] = []
    for path_2d in sorted(label_dir.rglob("*.json")):
        if path_2d.name.endswith("-3d.json"):
            continue
        path_3d = path_2d.with_name(f"{path_2d.stem}-3d.json")
        if path_3d.exists():
            pairs.append((path_2d, path_3d))
    return pairs


def load_fitness_samples(root: Path, split: str, label_pairs: Sequence[Tuple[Path, Path]]) -> List[Dict[str, Any]]:
    samples: List[Dict[str, Any]] = []
    for path_2d, path_3d in label_pairs:
        data_2d = json.loads(path_2d.read_text(encoding="utf-8"))
        data_3d = json.loads(path_3d.read_text(encoding="utf-8"))
        frames_2d = list(data_2d.get("frames", []))
        frames_3d = list(data_3d.get("frames", []))
        if not frames_2d or not frames_3d:
            continue

        image_width, image_height = resolve_fitness_image_size(root, split, frames_2d)
        frame_count = min(len(frames_2d), len(frames_3d))
        for frame_index in range(frame_count):
            frame_2d = frames_2d[frame_index]
            frame_3d = frames_3d[frame_index]
            target = fitness_points_to_3d_array(extract_fitness_3d_points(frame_3d))
            for view_name in sorted(key for key in frame_2d.keys() if key.lower().startswith("view")):
                view_payload = frame_2d.get(view_name, {})
                if not fitness_view_is_active(view_payload):
                    continue
                points_2d = fitness_points_to_2d_array(view_payload.get("pts", {}))
                confidence = points_2d[:, 2]
                model_input = pixels_to_normalized_lifter_input(
                    points_2d[:, :2],
                    confidence,
                    width=float(image_width),
                    height=float(image_height),
                )
                image_path = ""
                img_key = view_payload.get("img_key")
                if isinstance(img_key, str) and img_key:
                    image_path = str(root / "raw" / split / Path(*PurePosixPath(img_key).parts))
                samples.append(
                    {
                        "input": model_input,
                        "target": target.copy(),
                        "source": str(path_2d),
                        "frame_index": frame_index,
                        "view": view_name,
                        "image_path": image_path,
                    }
                )
    return samples


def extract_fitness_3d_points(frame_payload: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
    points = frame_payload.get("pts_3d") or frame_payload.get("pts")
    if not isinstance(points, dict):
        raise ValueError("Fitness 3D frame must contain a pts or pts_3d mapping.")
    return points


def fitness_points_to_2d_array(points: Dict[str, Dict[str, Any]]) -> np.ndarray:
    rows: List[List[float]] = []
    for joint_name in COCO_17_JOINT_NAMES:
        joint = points.get(joint_name) or {}
        x = safe_float(joint.get("x"), default=0.0)
        y = safe_float(joint.get("y"), default=0.0)
        confidence = 1.0 if joint else 0.0
        rows.append([x, y, confidence])
    return np.asarray(rows, dtype=np.float32)


def fitness_points_to_3d_array(points: Dict[str, Dict[str, Any]]) -> np.ndarray:
    rows: List[List[float]] = []
    for joint_name in COCO_17_JOINT_NAMES:
        joint = points.get(joint_name) or {}
        rows.append(
            [
                safe_float(joint.get("x"), default=0.0),
                safe_float(joint.get("y"), default=0.0),
                safe_float(joint.get("z"), default=0.0),
            ]
        )
    return np.asarray(rows, dtype=np.float32)


def fitness_view_is_active(view_payload: Dict[str, Any]) -> bool:
    active = view_payload.get("active", "Yes")
    if isinstance(active, bool):
        return active
    return str(active).strip().lower() in {"yes", "y", "true", "1"}


def resolve_fitness_image_size(root: Path, split: str, frames_2d: Sequence[Dict[str, Any]]) -> Tuple[int, int]:
    for frame in frames_2d:
        for view_name in sorted(key for key in frame.keys() if key.lower().startswith("view")):
            view_payload = frame.get(view_name, {})
            img_key = view_payload.get("img_key")
            if not isinstance(img_key, str) or not img_key:
                continue
            image_path = root / "raw" / split / Path(*PurePosixPath(img_key).parts)
            if image_path.exists():
                return read_image_size(image_path)
    return DEFAULT_FITNESS_IMAGE_SIZE


def read_image_size(path: Path) -> Tuple[int, int]:
    try:
        with path.open("rb") as stream:
            header = stream.read(24)
            if header.startswith(b"\x89PNG\r\n\x1a\n") and len(header) >= 24:
                width = int.from_bytes(header[16:20], "big")
                height = int.from_bytes(header[20:24], "big")
                return width, height
            if header.startswith(b"\xff\xd8"):
                stream.seek(2)
                while True:
                    marker_start = stream.read(1)
                    if not marker_start:
                        break
                    if marker_start != b"\xff":
                        continue
                    marker = stream.read(1)
                    while marker == b"\xff":
                        marker = stream.read(1)
                    if not marker:
                        break
                    if marker in {b"\xc0", b"\xc1", b"\xc2", b"\xc3", b"\xc5", b"\xc6", b"\xc7", b"\xc9", b"\xca", b"\xcb", b"\xcd", b"\xce", b"\xcf"}:
                        _segment_length = int.from_bytes(stream.read(2), "big")
                        _precision = stream.read(1)
                        height = int.from_bytes(stream.read(2), "big")
                        width = int.from_bytes(stream.read(2), "big")
                        return width, height
                    segment_length = int.from_bytes(stream.read(2), "big")
                    stream.seek(max(0, segment_length - 2), 1)
    except OSError:
        pass
    return DEFAULT_FITNESS_IMAGE_SIZE


def safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
