"""Standalone entrypoint for the 3D pose pipeline.

Examples:
    python -m model_3d --input sample_keypoints.json
    python model_3d/run_pipeline.py --input sample_keypoints.json
    python -m model_3d --dummy --frame-id smoke-test
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

if __package__ in {None, ""}:
    # Support `python model_3d/run_pipeline.py` from the repository root.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from model_3d.diagnostics import DiagnosticsRecorder
from model_3d.lifter_model import PoseLifterFitter
from model_3d.pipeline import PosePipeline
from model_3d.pose3d_dataset import DirectPose3DFitter, load_pose3d_frames
from model_3d.schemas import FitResult


class DummyFitter:
    """Small no-SMPLX fitter for checking pipeline wiring and diagnostics output."""

    backend = "dummy"

    def forward(self, payload: Any) -> FitResult:
        target_2d = _payload_to_target_2d(payload)
        projected_2d = target_2d + np.array([8.0, -6.0], dtype=np.float32)
        joints_3d = _dummy_squat_joints()
        return FitResult(
            backend=self.backend,
            joints_3d=joints_3d,
            projected_joints_2d=projected_2d,
            target_joints_2d=target_2d,
            confidence=np.ones(17, dtype=np.float32),
            reprojection_loss=float(np.mean(np.sum((projected_2d - target_2d) ** 2, axis=1))),
            global_orient=np.zeros(3, dtype=np.float32),
            body_pose=np.zeros(63, dtype=np.float32),
            loss_history=[180.0, 120.0, 70.0, 35.0, 14.0],
        )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run the model_3d pose pipeline once or many times.")
    parser.add_argument(
        "--input",
        type=Path,
        help="JSON file. Accepts raw 17x3 keypoints, {'payload': ...}, or a list of frames.",
    )
    parser.add_argument(
        "--payload",
        help="Inline JSON payload. Accepts raw 17x3 keypoints or {'payload': ...}.",
    )
    parser.add_argument("--frame-id", default="local-frame", help="Frame id for diagnostics naming.")
    parser.add_argument("--output", type=Path, help="Optional JSON file for the pipeline response.")
    parser.add_argument(
        "--dummy",
        action="store_true",
        help="Use a no-SMPLX dummy fitter to test diagnostics and graph generation.",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Run the same payload N times. Useful for performance graph smoke tests.",
    )
    parser.add_argument(
        "--pose3d-path",
        type=Path,
        help="Load 3D coordinates directly from pose_3d_v3 root, split directory, or frame .pkl.",
    )
    parser.add_argument(
        "--lifter-checkpoint",
        type=Path,
        help="Run a trained 2D-to-3D pose lifter checkpoint instead of SMPL-X.",
    )
    parser.add_argument(
        "--pose3d-split",
        default="train",
        choices=["train", "valid", "test"],
        help="Split to use when --pose3d-path points to the pose_3d_v3 root.",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Maximum pose_3d_v3 frames to process.",
    )
    args = parser.parse_args(argv)

    if args.pose3d_path and (args.input or args.payload or args.dummy or args.lifter_checkpoint):
        raise ValueError(
            "Use --pose3d-path by itself, without --input, --payload, --dummy, or --lifter-checkpoint."
        )
    if args.lifter_checkpoint and args.dummy:
        raise ValueError("Use either --lifter-checkpoint or --dummy, not both.")

    if args.pose3d_path:
        frames = load_pose3d_frames(
            args.pose3d_path,
            split=args.pose3d_split,
            max_frames=args.max_frames,
        )
        fitter = DirectPose3DFitter()
    else:
        frames = _load_frames(args.input, args.payload)
        if not frames:
            frames = [{"frame_id": args.frame_id, "payload": _sample_movenet_payload()}]
        if args.lifter_checkpoint:
            fitter = PoseLifterFitter(args.lifter_checkpoint)
        else:
            fitter = DummyFitter() if args.dummy else None

    diagnostics = DiagnosticsRecorder.from_env()
    pipeline = PosePipeline(
        fitter=fitter,
        diagnostics=diagnostics,
    )

    last_response: Dict[str, Any] = {}
    repeat_count = max(1, args.repeat)
    for repeat_index in range(repeat_count):
        for frame_index, frame in enumerate(frames, start=1):
            frame_id = frame.get("frame_id", f"{args.frame_id}-{repeat_index + 1}-{frame_index}")
            last_response = pipeline.process_keypoints(frame["payload"], frame_id=frame_id)
            _print_summary(last_response)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(last_response, indent=2, ensure_ascii=False, allow_nan=False),
            encoding="utf-8",
        )
        print(f"[pipeline] response saved: {args.output}")

    print(f"[pipeline] diagnostics session: {diagnostics.session_dir}")
    return 0


def _load_frames(input_path: Optional[Path], inline_payload: Optional[str]) -> List[Dict[str, Any]]:
    if input_path and inline_payload:
        raise ValueError("Use either --input or --payload, not both.")

    if input_path:
        if not input_path.exists():
            raise FileNotFoundError(
                f"Input JSON not found: {input_path}. "
                "Use --dummy for a smoke test, or use --pose3d-path pose_3d_v3 "
                "to run from the local 3D coordinate dataset."
            )
        data = json.loads(input_path.read_text(encoding="utf-8"))
    elif inline_payload:
        data = json.loads(inline_payload)
    else:
        return []

    return _normalize_frames(data)


def _normalize_frames(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, dict):
        if "payload" not in data:
            raise ValueError("Input object must contain a 'payload' field.")
        return [
            {
                "frame_id": data.get("frame_id", "local-frame"),
                "payload": data["payload"],
            }
        ]

    if isinstance(data, list):
        if _looks_like_keypoints(data):
            return [{"frame_id": "local-frame", "payload": data}]
        return [_normalize_frame_item(item, index) for index, item in enumerate(data, start=1)]

    raise ValueError("Input must be a JSON object or list.")


def _normalize_frame_item(item: Any, index: int) -> Dict[str, Any]:
    if isinstance(item, dict) and "payload" in item:
        return {"frame_id": item.get("frame_id", f"frame-{index}"), "payload": item["payload"]}
    if _looks_like_keypoints(item):
        return {"frame_id": f"frame-{index}", "payload": item}
    raise ValueError(f"Frame item {index} must be a payload object or raw 17x3 keypoints.")


def _looks_like_keypoints(value: Any) -> bool:
    return isinstance(value, list) and len(value) == 17 and all(isinstance(row, list) for row in value)


def _sample_movenet_payload() -> List[List[float]]:
    # Normalized [y, x, score] COCO-ish skeleton. This is only a local smoke-test sample.
    return [
        [0.20, 0.50, 0.90],
        [0.18, 0.48, 0.85],
        [0.18, 0.52, 0.85],
        [0.19, 0.46, 0.80],
        [0.19, 0.54, 0.80],
        [0.34, 0.42, 0.92],
        [0.34, 0.58, 0.92],
        [0.50, 0.38, 0.88],
        [0.50, 0.62, 0.88],
        [0.64, 0.36, 0.80],
        [0.64, 0.64, 0.80],
        [0.58, 0.45, 0.93],
        [0.58, 0.55, 0.93],
        [0.78, 0.43, 0.94],
        [0.78, 0.57, 0.94],
        [0.95, 0.42, 0.90],
        [0.95, 0.58, 0.90],
    ]


def _payload_to_target_2d(payload: Any) -> np.ndarray:
    array = np.asarray(payload, dtype=np.float32)
    if array.shape != (17, 3):
        return np.zeros((17, 2), dtype=np.float32)
    y = array[:, 0] * 480.0
    x = array[:, 1] * 640.0
    return np.stack((x, y), axis=-1).astype(np.float32)


def _dummy_squat_joints() -> np.ndarray:
    joints = np.zeros((17, 3), dtype=np.float32)
    joints[0] = [0.0, 1.7, 2.0]
    joints[5] = [-0.4, 1.3, 2.0]
    joints[6] = [0.4, 1.3, 2.0]
    joints[11] = [-0.3, 0.5, 2.0]
    joints[12] = [0.3, 0.5, 2.0]
    joints[13] = [-0.35, -0.3, 2.0]
    joints[14] = [0.35, -0.3, 2.0]
    joints[15] = [0.15, -0.6, 2.0]
    joints[16] = [0.85, -0.6, 2.0]
    return joints


def _print_summary(response: Dict[str, Any]) -> None:
    feedback = response.get("feedback", {})
    performance = response.get("performance", {})
    diagnostics = response.get("diagnostics", {})
    print(
        "[pipeline] "
        f"frame_id={response.get('frame_id')} "
        f"status={response.get('status')} "
        f"feedback={feedback.get('label')} "
        f"knee={feedback.get('knee_angle_deg'):.2f} "
        f"model_ms={performance.get('model_latency_ms'):.2f} "
        f"artifacts={len(diagnostics.get('artifacts', {}))}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
