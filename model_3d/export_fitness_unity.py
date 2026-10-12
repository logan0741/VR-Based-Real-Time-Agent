"""Export prepared fitness pose sequences to a Unity-friendly JSON format.

Examples:
    python -m model_3d.export_fitness_unity --limit 3
    python -m model_3d.export_fitness_unity --split train --sequence-id D05-1-001 --view view1
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from model_3d.config import project_root


DATASET_JOINT_NAMES: Tuple[str, ...] = (
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
    "Neck",
    "Left Palm",
    "Right Palm",
    "Back",
    "Waist",
    "Left Foot",
    "Right Foot",
)

DEFAULT_BONE_LINKS: Tuple[Tuple[str, str], ...] = (
    ("Waist", "Back"),
    ("Back", "Neck"),
    ("Neck", "Nose"),
    ("Nose", "Left Eye"),
    ("Nose", "Right Eye"),
    ("Left Eye", "Left Ear"),
    ("Right Eye", "Right Ear"),
    ("Neck", "Left Shoulder"),
    ("Left Shoulder", "Left Elbow"),
    ("Left Elbow", "Left Wrist"),
    ("Left Wrist", "Left Palm"),
    ("Neck", "Right Shoulder"),
    ("Right Shoulder", "Right Elbow"),
    ("Right Elbow", "Right Wrist"),
    ("Right Wrist", "Right Palm"),
    ("Waist", "Left Hip"),
    ("Left Hip", "Left Knee"),
    ("Left Knee", "Left Ankle"),
    ("Left Ankle", "Left Foot"),
    ("Waist", "Right Hip"),
    ("Right Hip", "Right Knee"),
    ("Right Knee", "Right Ankle"),
    ("Right Ankle", "Right Foot"),
)

DEFAULT_PREPARED_DATASET_NAME = "prepared_train_eval_body01_compact"


@dataclass
class LabelPair:
    split: str
    label_2d_path: Path
    label_3d_path: Path

    @property
    def sequence_id(self) -> str:
        return self.label_2d_path.stem


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Export prepared fitness sequences for Unity playback.")
    parser.add_argument(
        "--data",
        type=Path,
        default=None,
        help="Prepared dataset root. Auto-discovered when omitted.",
    )
    parser.add_argument(
        "--split",
        nargs="+",
        default=["train"],
        help="Split(s) to export. Example: train val",
    )
    parser.add_argument(
        "--sequence-id",
        action="append",
        default=[],
        help="One or more sequence ids like D05-1-001. Omit to export the first N pairs.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=3,
        help="How many sequences to export per split when --sequence-id is omitted.",
    )
    parser.add_argument(
        "--view",
        default="view1",
        help="2D source view used for background frame playback.",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=10.0,
        help="Playback frame rate stored in the exported JSON.",
    )
    parser.add_argument(
        "--units-per-meter",
        type=float,
        default=100.0,
        help="Source coordinate units per one Unity meter. 100 means centimeter-like scaling.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=project_root() / "artifacts" / "unity_fitness_viewer" / "sequences",
        help="Directory where Unity sequence JSON files are written.",
    )
    args = parser.parse_args(argv)

    dataset_root = args.data or discover_prepared_dataset_root()
    output_root = args.output_dir.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    sequence_filter = {value.strip() for value in args.sequence_id if value.strip()}
    manifest: Dict[str, object] = {
        "dataset_root": str(dataset_root.resolve()),
        "output_root": str(output_root),
        "view": args.view,
        "fps": args.fps,
        "units_per_meter": args.units_per_meter,
        "splits": {},
    }

    for split in args.split:
        pairs = resolve_label_pairs(dataset_root, split)
        if sequence_filter:
            pairs = [pair for pair in pairs if pair.sequence_id in sequence_filter]
        elif args.limit > 0:
            pairs = pairs[: args.limit]

        split_output_dir = output_root / split
        split_output_dir.mkdir(parents=True, exist_ok=True)
        exported_files: List[Dict[str, object]] = []
        for pair in pairs:
            payload = build_unity_sequence_payload(
                dataset_root=dataset_root,
                pair=pair,
                view_name=args.view,
                fps=args.fps,
                units_per_meter=args.units_per_meter,
            )
            output_path = split_output_dir / f"{pair.sequence_id}_{args.view}.json"
            output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            exported_files.append(
                {
                    "sequence_id": pair.sequence_id,
                    "path": str(output_path),
                    "frame_count": payload["frameCount"],
                    "exercise_name": payload["exerciseName"],
                    "view": payload["viewName"],
                }
            )
            print(f"[exported] {output_path}")

        manifest["splits"][split] = {
            "count": len(exported_files),
            "files": exported_files,
        }

    manifest_path = output_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[manifest] {manifest_path}")
    return 0


def discover_prepared_dataset_root() -> Path:
    root = project_root()
    candidates = sorted(
        candidate / DEFAULT_PREPARED_DATASET_NAME
        for candidate in root.iterdir()
        if candidate.is_dir() and candidate.name.startswith("013.") and (candidate / DEFAULT_PREPARED_DATASET_NAME).exists()
    )
    if not candidates:
        raise FileNotFoundError(
            f"Could not find {DEFAULT_PREPARED_DATASET_NAME} under a local 013.* dataset directory."
        )
    return candidates[0].resolve()


def resolve_label_pairs(dataset_root: Path, split: str) -> List[LabelPair]:
    label_dir = dataset_root / "labels" / split
    if not label_dir.exists():
        raise FileNotFoundError(f"Split not found: {label_dir}")

    pairs: List[LabelPair] = []
    for label_2d_path in sorted(label_dir.rglob("*.json")):
        if label_2d_path.name.endswith("-3d.json"):
            continue
        label_3d_path = label_2d_path.with_name(f"{label_2d_path.stem}-3d.json")
        if label_3d_path.exists():
            pairs.append(LabelPair(split=split, label_2d_path=label_2d_path, label_3d_path=label_3d_path))
    return pairs


def build_unity_sequence_payload(
    dataset_root: Path,
    pair: LabelPair,
    view_name: str,
    fps: float,
    units_per_meter: float,
) -> Dict[str, object]:
    data_2d = json.loads(pair.label_2d_path.read_text(encoding="utf-8"))
    data_3d = json.loads(pair.label_3d_path.read_text(encoding="utf-8"))

    frames_2d = list(data_2d.get("frames", []))
    frames_3d = list(data_3d.get("frames", []))
    frame_count = min(len(frames_2d), len(frames_3d))
    if frame_count == 0:
        raise ValueError(f"No frames found in {pair.label_2d_path}")

    root_reference = compute_root_reference(frames_3d)
    ground_offset = compute_ground_offset(frames_3d)
    joint_names = list(DATASET_JOINT_NAMES)
    joint_index = {name: idx for idx, name in enumerate(joint_names)}

    exported_frames: List[Dict[str, object]] = []
    for frame_index in range(frame_count):
        frame_2d = frames_2d[frame_index]
        frame_3d = frames_3d[frame_index]
        view_payload = resolve_view_payload(frame_2d, view_name)
        absolute_image_path, relative_image_path = resolve_image_paths(dataset_root, pair.split, view_payload)
        joints_3d = build_joint_positions(
            frame_3d=frame_3d,
            root_reference=root_reference,
            ground_offset=ground_offset,
            units_per_meter=units_per_meter,
        )
        joints_2d = build_screen_points(view_payload)
        confidence = [point["confidence"] for point in joints_2d]
        exported_frames.append(
            {
                "index": frame_index,
                "timeSec": round(frame_index / max(0.001, fps), 6),
                "imagePath": absolute_image_path,
                "imageRelativePath": relative_image_path,
                "joints": joints_3d,
                "screenJoints": joints_2d,
                "confidence": confidence,
            }
        )

    bone_links = [
        {
            "name": f"{start}_{end}",
            "fromIndex": joint_index[start],
            "toIndex": joint_index[end],
        }
        for start, end in DEFAULT_BONE_LINKS
        if start in joint_index and end in joint_index
    ]

    type_info = data_2d.get("type_info", {})
    return {
        "formatVersion": 1,
        "sequenceId": pair.sequence_id,
        "split": pair.split,
        "viewName": view_name,
        "frameRate": fps,
        "frameCount": frame_count,
        "unitsPerMeter": units_per_meter,
        "coordinateSystem": "unity_y_up_z_forward",
        "rootReference": root_reference,
        "groundOffset": round(ground_offset, 6),
        "exerciseType": data_2d.get("type", ""),
        "exerciseName": type_info.get("exercise", ""),
        "exerciseCategory": type_info.get("type", ""),
        "sourceLabel2D": str(pair.label_2d_path.resolve()),
        "sourceLabel3D": str(pair.label_3d_path.resolve()),
        "jointNames": joint_names,
        "boneLinks": bone_links,
        "frames": exported_frames,
    }


def compute_root_reference(frames_3d: Sequence[Dict[str, object]]) -> Dict[str, float]:
    first_points = extract_3d_points(frames_3d[0])
    waist = first_points.get("Waist")
    if waist is None:
        left_hip = first_points.get("Left Hip", {"x": 0.0, "y": 0.0, "z": 0.0})
        right_hip = first_points.get("Right Hip", {"x": 0.0, "y": 0.0, "z": 0.0})
        return {
            "x": (safe_float(left_hip.get("x")) + safe_float(right_hip.get("x"))) * 0.5,
            "y": (safe_float(left_hip.get("y")) + safe_float(right_hip.get("y"))) * 0.5,
            "z": (safe_float(left_hip.get("z")) + safe_float(right_hip.get("z"))) * 0.5,
        }
    return {
        "x": safe_float(waist.get("x")),
        "y": safe_float(waist.get("y")),
        "z": safe_float(waist.get("z")),
    }


def compute_ground_offset(frames_3d: Sequence[Dict[str, object]]) -> float:
    candidates: List[float] = []
    for frame in frames_3d:
        points = extract_3d_points(frame)
        for name in ("Left Foot", "Right Foot", "Left Ankle", "Right Ankle"):
            joint = points.get(name)
            if joint is not None:
                candidates.append(safe_float(joint.get("y")))
    return min(candidates) if candidates else 0.0


def resolve_view_payload(frame_2d: Dict[str, object], view_name: str) -> Dict[str, object]:
    payload = frame_2d.get(view_name)
    if isinstance(payload, dict):
        return payload
    fallback = next((value for key, value in frame_2d.items() if str(key).lower().startswith("view") and isinstance(value, dict)), None)
    if fallback is None:
        raise ValueError("No 2D view payload found in frame.")
    return fallback


def resolve_image_paths(dataset_root: Path, split: str, view_payload: Dict[str, object]) -> Tuple[str, str]:
    img_key = str(view_payload.get("img_key", "")).strip()
    if not img_key:
        return "", ""
    relative_path = Path(*PurePosixPath(img_key).parts)
    absolute_path = (dataset_root / "raw" / split / relative_path).resolve()
    return str(absolute_path), str(relative_path).replace("\\", "/")


def build_joint_positions(
    frame_3d: Dict[str, object],
    root_reference: Dict[str, float],
    ground_offset: float,
    units_per_meter: float,
) -> List[Dict[str, float]]:
    points = extract_3d_points(frame_3d)
    output: List[Dict[str, float]] = []
    root_x = root_reference["x"]
    root_z = root_reference["z"]
    scale = max(0.001, units_per_meter)

    for joint_name in DATASET_JOINT_NAMES:
        point = points.get(joint_name, {})
        source_x = safe_float(point.get("x"))
        source_y = safe_float(point.get("y"))
        source_z = safe_float(point.get("z"))
        output.append(
            {
                "x": round((source_x - root_x) / scale, 6),
                "y": round((source_y - ground_offset) / scale, 6),
                "z": round((root_z - source_z) / scale, 6),
            }
        )
    return output


def build_screen_points(view_payload: Dict[str, object]) -> List[Dict[str, float]]:
    points = view_payload.get("pts", {})
    output: List[Dict[str, float]] = []
    for joint_name in DATASET_JOINT_NAMES:
        point = points.get(joint_name, {})
        has_point = bool(point)
        output.append(
            {
                "x": round(safe_float(point.get("x")), 3),
                "y": round(safe_float(point.get("y")), 3),
                "confidence": 1.0 if has_point else 0.0,
            }
        )
    return output


def extract_3d_points(frame_3d: Dict[str, object]) -> Dict[str, Dict[str, object]]:
    points = frame_3d.get("pts_3d") or frame_3d.get("pts")
    if not isinstance(points, dict):
        raise ValueError("3D frame does not contain pts or pts_3d.")
    return points


def safe_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


if __name__ == "__main__":
    raise SystemExit(main())
