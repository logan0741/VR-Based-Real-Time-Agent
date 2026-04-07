from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import os
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image
from tqdm import tqdm

if __package__:
    from .config import RESULTS_DIR
    from .dataset import Pose2DDataset, Pose2DRecord
else:
    from config import RESULTS_DIR
    from dataset import Pose2DDataset, Pose2DRecord


os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")


COCO_KEYPOINT_NAMES = [
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

MEDIAPIPE_TO_COCO = {
    0: 0,
    2: 1,
    5: 2,
    7: 3,
    8: 4,
    11: 5,
    12: 6,
    13: 7,
    14: 8,
    15: 9,
    16: 10,
    23: 11,
    24: 12,
    25: 13,
    26: 14,
    27: 15,
    28: 16,
}

MOVENET_LIGHTNING_URL = "https://tfhub.dev/google/movenet/singlepose/lightning/4"
MOVENET_THUNDER_URL = "https://tfhub.dev/google/movenet/singlepose/thunder/4"

DEFAULT_MODELS = [
    "mediapipe",
    "movenet_lightning",
    "movenet_thunder",
    "mmpose",
]

MODEL_DEPENDENCIES = {
    "mediapipe": ["mediapipe"],
    "movenet_lightning": ["tensorflow", "tensorflow_hub"],
    "movenet_thunder": ["tensorflow", "tensorflow_hub"],
    "mmpose": ["torch", "mmpose"],
}


class ModelInitError(RuntimeError):
    pass


class Timer:
    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.elapsed_ms = (time.perf_counter() - self.start) * 1000.0


def module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def dependency_report(model_name: str) -> Dict[str, bool]:
    return {module_name: module_available(module_name) for module_name in MODEL_DEPENDENCIES[model_name]}


def load_image_rgb(image_path: Path) -> np.ndarray:
    with Image.open(image_path) as image:
        return np.asarray(image.convert("RGB"), dtype=np.uint8)


def clip_bbox(
    bbox: Sequence[float],
    image_width: int,
    image_height: int,
    pad_factor: float,
) -> Tuple[int, int, int, int]:
    x_coord, y_coord, box_width, box_height = bbox
    if box_width <= 0 or box_height <= 0:
        return 0, 0, image_width, image_height

    center_x = x_coord + box_width / 2.0
    center_y = y_coord + box_height / 2.0
    padded_width = box_width * pad_factor
    padded_height = box_height * pad_factor

    left = max(int(math.floor(center_x - padded_width / 2.0)), 0)
    top = max(int(math.floor(center_y - padded_height / 2.0)), 0)
    right = min(int(math.ceil(center_x + padded_width / 2.0)), image_width)
    bottom = min(int(math.ceil(center_y + padded_height / 2.0)), image_height)

    if right <= left or bottom <= top:
        return 0, 0, image_width, image_height

    return left, top, right, bottom


def crop_image(
    image_rgb: np.ndarray,
    bbox: Sequence[float],
    pad_factor: float,
) -> Tuple[np.ndarray, Tuple[int, int, int, int]]:
    image_height, image_width = image_rgb.shape[:2]
    left, top, right, bottom = clip_bbox(bbox, image_width, image_height, pad_factor)
    return image_rgb[top:bottom, left:right].copy(), (left, top, right, bottom)


def mediapipe_to_coco(landmarks, image_width: int, image_height: int) -> np.ndarray:
    keypoints = np.zeros((17, 3), dtype=np.float32)
    for mediapipe_index, coco_index in MEDIAPIPE_TO_COCO.items():
        landmark = landmarks[mediapipe_index]
        keypoints[coco_index] = [
            float(landmark.x) * image_width,
            float(landmark.y) * image_height,
            float(getattr(landmark, "visibility", 1.0)),
        ]
    return keypoints


def movenet_to_coco(keypoints: np.ndarray, image_width: int, image_height: int) -> np.ndarray:
    raw_keypoints = keypoints[0, 0]
    output = np.zeros((17, 3), dtype=np.float32)
    for joint_index in range(17):
        y_norm, x_norm, score = raw_keypoints[joint_index]
        output[joint_index] = [
            float(x_norm) * image_width,
            float(y_norm) * image_height,
            float(score),
        ]
    return output


def choose_best_prediction(predictions) -> Optional[dict]:
    if not predictions:
        return None

    if isinstance(predictions, list) and predictions and isinstance(predictions[0], list):
        candidates = predictions[0]
    elif isinstance(predictions, list):
        candidates = predictions
    else:
        return None

    if not candidates:
        return None

    def prediction_score(candidate: dict) -> float:
        if "bbox_score" in candidate:
            return float(candidate["bbox_score"])
        if "keypoint_scores" in candidate:
            scores = np.asarray(candidate["keypoint_scores"], dtype=np.float32)
            if scores.size > 0:
                return float(scores.mean())
        return 0.0

    return max(candidates, key=prediction_score)


class MediaPipeRunner:
    name = "mediapipe"

    def __init__(self) -> None:
        try:
            import mediapipe as mp
        except ImportError as exc:
            raise ModelInitError("mediapipe is not installed.") from exc

        self.pose = mp.solutions.pose.Pose(
            static_image_mode=True,
            model_complexity=1,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

    def infer(self, crop_rgb: np.ndarray) -> Optional[np.ndarray]:
        crop_height, crop_width = crop_rgb.shape[:2]
        result = self.pose.process(crop_rgb)
        if result.pose_landmarks is None:
            return None
        return mediapipe_to_coco(result.pose_landmarks.landmark, crop_width, crop_height)

    def close(self) -> None:
        self.pose.close()


class MoveNetRunner:
    def __init__(self, variant: str) -> None:
        try:
            import tensorflow_hub as hub
        except ImportError as exc:
            raise ModelInitError("tensorflow-hub is not installed.") from exc

        if variant == "lightning":
            self.name = "movenet_lightning"
            self.input_size = 192
            model_url = MOVENET_LIGHTNING_URL
        else:
            self.name = "movenet_thunder"
            self.input_size = 256
            model_url = MOVENET_THUNDER_URL

        try:
            self.model = hub.load(model_url)
        except Exception as exc:
            raise ModelInitError(f"failed to load TF Hub model: {exc}") from exc

        self.signature = self.model.signatures["serving_default"]

    def infer(self, crop_rgb: np.ndarray) -> Optional[np.ndarray]:
        import tensorflow as tf

        crop_height, crop_width = crop_rgb.shape[:2]
        image_tensor = tf.image.resize_with_pad(
            tf.expand_dims(crop_rgb, axis=0),
            self.input_size,
            self.input_size,
        )
        image_tensor = tf.cast(image_tensor, dtype=tf.int32)
        outputs = self.signature(image_tensor)
        keypoints = outputs["output_0"].numpy()
        return movenet_to_coco(keypoints, crop_width, crop_height)

    def close(self) -> None:
        return None


class MMPoseRunner:
    name = "mmpose"

    def __init__(self, model_name: str) -> None:
        try:
            from mmpose.apis import MMPoseInferencer
        except ImportError as exc:
            raise ModelInitError(f"failed to import MMPoseInferencer: {exc}") from exc

        try:
            self.inferencer = MMPoseInferencer(model_name)
        except Exception as exc:
            raise ModelInitError(f"failed to initialize MMPoseInferencer: {exc}") from exc

    def infer(self, crop_rgb: np.ndarray) -> Optional[np.ndarray]:
        crop_bgr = crop_rgb[:, :, ::-1]
        result = next(self.inferencer(crop_bgr, return_vis=False))
        best_prediction = choose_best_prediction(result.get("predictions"))
        if best_prediction is None:
            return None

        raw_keypoints = np.asarray(best_prediction.get("keypoints", []), dtype=np.float32)
        if raw_keypoints.shape[0] != 17:
            return None

        raw_scores = best_prediction.get("keypoint_scores")
        if raw_scores is None:
            scores = np.ones((17,), dtype=np.float32)
        else:
            scores = np.asarray(raw_scores, dtype=np.float32).reshape(17)

        output = np.zeros((17, 3), dtype=np.float32)
        output[:, :2] = raw_keypoints[:, :2]
        output[:, 2] = scores
        return output

    def close(self) -> None:
        return None


def create_runner(model_name: str, mmpose_model: str):
    if model_name == "mediapipe":
        return MediaPipeRunner()
    if model_name == "movenet_lightning":
        return MoveNetRunner("lightning")
    if model_name == "movenet_thunder":
        return MoveNetRunner("thunder")
    if model_name == "mmpose":
        return MMPoseRunner(mmpose_model)
    raise ValueError(f"unsupported model: {model_name}")


def build_bbox_map(split: str, bbox_source: str) -> Dict[int, Pose2DRecord]:
    bbox_dataset = Pose2DDataset(split, bbox_source=bbox_source)
    bbox_map: Dict[int, Pose2DRecord] = {}
    for record in bbox_dataset.records:
        bbox_map.setdefault(record.image_id, record)
    return bbox_map


def select_records(
    split: str,
    bbox_source: str,
    limit: Optional[int],
    stride: int,
) -> Tuple[List[Tuple[Pose2DRecord, Dict[str, object]]], int]:
    gt_dataset = Pose2DDataset(split, bbox_source="gt")
    requested_bbox_map = build_bbox_map(split, bbox_source) if bbox_source != "gt" else {}

    selected: List[Tuple[Pose2DRecord, Dict[str, object]]] = []
    fallback_count = 0

    for record in gt_dataset.records[::stride]:
        used_bbox_source = bbox_source
        bbox = record.bbox
        if bbox_source != "gt":
            bbox_record = requested_bbox_map.get(record.image_id)
            if bbox_record is None:
                fallback_count += 1
                used_bbox_source = "gt"
            else:
                bbox = bbox_record.bbox
                used_bbox_source = bbox_record.bbox_source

        selected.append((record, make_bbox_context(bbox, used_bbox_source)))
        if limit is not None and len(selected) >= limit:
            break

    return selected, fallback_count


def make_bbox_context(bbox: Sequence[float], used_bbox_source: str) -> Dict[str, object]:
    return {
        "bbox": [float(value) for value in bbox],
        "used_bbox_source": used_bbox_source,
    }


def visible_joint_mask(record: Pose2DRecord) -> np.ndarray:
    gt_keypoints = np.asarray(record.keypoints, dtype=np.float32)
    return gt_keypoints[:, 2] > 0


def evaluate_prediction(
    record: Pose2DRecord,
    prediction: Optional[np.ndarray],
    requested_bbox_source: str,
    used_bbox_source: str,
    crop_box: Tuple[int, int, int, int],
    inference_ms: Optional[float],
    confidence_threshold: float,
) -> Dict[str, object]:
    gt_keypoints = np.asarray(record.keypoints, dtype=np.float32)
    visible_mask = gt_keypoints[:, 2] > 0
    gt_visible_joints = int(visible_mask.sum())

    row: Dict[str, object] = {
        "split": record.split,
        "sample_index": record.sample_index,
        "image_id": record.image_id,
        "annotation_id": record.annotation_id,
        "image_path": str(record.image_path),
        "requested_bbox_source": requested_bbox_source,
        "used_bbox_source": used_bbox_source,
        "crop_left": crop_box[0],
        "crop_top": crop_box[1],
        "crop_right": crop_box[2],
        "crop_bottom": crop_box[3],
        "gt_bbox_x": round(float(record.bbox[0]), 2),
        "gt_bbox_y": round(float(record.bbox[1]), 2),
        "gt_bbox_w": round(float(record.bbox[2]), 2),
        "gt_bbox_h": round(float(record.bbox[3]), 2),
        "gt_visible_joints": gt_visible_joints,
        "pred_visible_joints": 0,
        "avg_confidence": None,
        "mean_error_px": None,
        "median_error_px": None,
        "pck_005": None,
        "pck_010": None,
        "correct_005": 0,
        "correct_010": 0,
        "valid_joint_count": gt_visible_joints,
        "status": "no_prediction",
        "inference_ms": round(float(inference_ms), 4) if inference_ms is not None else None,
    }

    if prediction is None:
        return row

    errors = np.linalg.norm(prediction[:, :2] - gt_keypoints[:, :2], axis=1)
    visible_errors = errors[visible_mask]
    visible_confidences = prediction[visible_mask, 2]

    bbox_size = max(float(record.bbox[2]), float(record.bbox[3]), 1.0)
    correct_005 = int(np.sum(visible_errors <= bbox_size * 0.05))
    correct_010 = int(np.sum(visible_errors <= bbox_size * 0.10))
    pred_visible_joints = int(np.sum(prediction[:, 2] >= confidence_threshold))

    row.update(
        {
            "pred_visible_joints": pred_visible_joints,
            "avg_confidence": round(float(np.mean(visible_confidences)), 4) if gt_visible_joints else None,
            "mean_error_px": round(float(np.mean(visible_errors)), 4) if gt_visible_joints else None,
            "median_error_px": round(float(np.median(visible_errors)), 4) if gt_visible_joints else None,
            "pck_005": round(correct_005 / gt_visible_joints, 4) if gt_visible_joints else None,
            "pck_010": round(correct_010 / gt_visible_joints, 4) if gt_visible_joints else None,
            "correct_005": correct_005,
            "correct_010": correct_010,
            "status": "ok",
        }
    )
    return row


def summarize_rows(model_name: str, rows: Sequence[Dict[str, object]]) -> Dict[str, object]:
    total_samples = len(rows)
    ok_rows = [row for row in rows if row["status"] == "ok"]
    inference_values = [float(row["inference_ms"]) for row in ok_rows if row["inference_ms"] is not None]
    error_values = [float(row["mean_error_px"]) for row in ok_rows if row["mean_error_px"] is not None]
    confidence_values = [float(row["avg_confidence"]) for row in ok_rows if row["avg_confidence"] is not None]

    visible_joint_count = sum(int(row["valid_joint_count"]) for row in rows)
    correct_005 = sum(int(row["correct_005"]) for row in rows)
    correct_010 = sum(int(row["correct_010"]) for row in rows)

    summary: Dict[str, object] = {
        "model": model_name,
        "samples_total": total_samples,
        "samples_ok": len(ok_rows),
        "samples_failed": total_samples - len(ok_rows),
        "success_rate": round(len(ok_rows) / total_samples, 4) if total_samples else 0.0,
        "avg_inference_ms": None,
        "p95_inference_ms": None,
        "avg_fps": None,
        "mean_error_px": None,
        "median_error_px": None,
        "mean_confidence": None,
        "pck_005": round(correct_005 / visible_joint_count, 4) if visible_joint_count else None,
        "pck_010": round(correct_010 / visible_joint_count, 4) if visible_joint_count else None,
        "visible_joint_count": visible_joint_count,
    }

    if inference_values:
        avg_inference_ms = float(np.mean(inference_values))
        summary["avg_inference_ms"] = round(avg_inference_ms, 4)
        summary["p95_inference_ms"] = round(float(np.percentile(inference_values, 95)), 4)
        summary["avg_fps"] = round(1000.0 / avg_inference_ms, 4) if avg_inference_ms > 0 else None

    if error_values:
        summary["mean_error_px"] = round(float(np.mean(error_values)), 4)
        summary["median_error_px"] = round(float(np.median(error_values)), 4)

    if confidence_values:
        summary["mean_confidence"] = round(float(np.mean(confidence_values)), 4)
    return summary


def summarize_joint_errors(rows: Sequence[Dict[str, object]], prediction_cache: Dict[int, Optional[np.ndarray]], records: Sequence[Pose2DRecord]) -> Dict[str, Optional[float]]:
    joint_errors: Dict[str, List[float]] = defaultdict(list)
    for record in records:
        prediction = prediction_cache.get(record.sample_index)
        if prediction is None:
            continue
        gt_keypoints = np.asarray(record.keypoints, dtype=np.float32)
        errors = np.linalg.norm(prediction[:, :2] - gt_keypoints[:, :2], axis=1)
        visible_mask = gt_keypoints[:, 2] > 0
        for joint_index, joint_name in enumerate(COCO_KEYPOINT_NAMES):
            if visible_mask[joint_index]:
                joint_errors[joint_name].append(float(errors[joint_index]))

    per_joint: Dict[str, Optional[float]] = {}
    for joint_name in COCO_KEYPOINT_NAMES:
        values = joint_errors.get(joint_name, [])
        per_joint[joint_name] = round(float(np.mean(values)), 4) if values else None
    return per_joint


def write_summary_csv(summary_rows: Sequence[Dict[str, object]], output_path: Path) -> None:
    fieldnames = [
        "model",
        "samples_total",
        "samples_ok",
        "samples_failed",
        "success_rate",
        "avg_inference_ms",
        "p95_inference_ms",
        "avg_fps",
        "mean_error_px",
        "median_error_px",
        "mean_confidence",
        "pck_005",
        "pck_010",
        "visible_joint_count",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in summary_rows:
            writer.writerow({field: row.get(field) for field in fieldnames})


def write_rows_csv(rows: Sequence[Dict[str, object]], output_path: Path) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def markdown_cell(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def build_markdown_report(
    summary_rows: Sequence[Dict[str, object]],
    unavailable_models: Dict[str, str],
    args,
    output_dir: Path,
    sample_count: int,
    fallback_count: int,
) -> str:
    lines: List[str] = []
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines.append("# pose_2d Model Comparison Summary")
    lines.append("")
    lines.append(f"- Created at: `{created_at}`")
    lines.append(f"- Split: `{args.split}`")
    lines.append(f"- BBox source: `{args.bbox_source}`")
    lines.append(f"- Models requested: `{', '.join(args.models)}`")
    lines.append(f"- Samples evaluated: `{sample_count}`")
    lines.append(f"- Fallback to GT bbox count: `{fallback_count}`")
    lines.append("")

    if summary_rows:
        lines.append("## Metrics")
        lines.append("")
        lines.append("| Model | OK / Total | Success Rate | Avg ms | P95 ms | Avg FPS | Mean Error px | Median Error px | Mean Conf | PCK@0.05 | PCK@0.10 |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for row in summary_rows:
            lines.append(
                "| {model} | {samples_ok}/{samples_total} | {success_rate} | {avg_inference_ms} | {p95_inference_ms} | {avg_fps} | {mean_error_px} | {median_error_px} | {mean_confidence} | {pck_005} | {pck_010} |".format(
                    model=markdown_cell(row.get("model")),
                    samples_ok=markdown_cell(row.get("samples_ok")),
                    samples_total=markdown_cell(row.get("samples_total")),
                    success_rate=markdown_cell(row.get("success_rate")),
                    avg_inference_ms=markdown_cell(row.get("avg_inference_ms")),
                    p95_inference_ms=markdown_cell(row.get("p95_inference_ms")),
                    avg_fps=markdown_cell(row.get("avg_fps")),
                    mean_error_px=markdown_cell(row.get("mean_error_px")),
                    median_error_px=markdown_cell(row.get("median_error_px")),
                    mean_confidence=markdown_cell(row.get("mean_confidence")),
                    pck_005=markdown_cell(row.get("pck_005")),
                    pck_010=markdown_cell(row.get("pck_010")),
                )
            )
        lines.append("")

        lines.append("## Per-Joint Mean Error")
        lines.append("")
        for row in summary_rows:
            lines.append(f"### {row['model']}")
            lines.append("")
            per_joint = row.get("per_joint_mean_error_px", {})
            lines.append("| Joint | Mean Error px |")
            lines.append("| --- | --- |")
            for joint_name in COCO_KEYPOINT_NAMES:
                lines.append(f"| {joint_name} | {markdown_cell(per_joint.get(joint_name))} |")
            lines.append("")

    if unavailable_models:
        lines.append("## Skipped Models")
        lines.append("")
        for model_name, error_message in unavailable_models.items():
            lines.append(f"- `{model_name}`: {error_message}")
        lines.append("")

    lines.append("## Output Files")
    lines.append("")
    lines.append(f"- Summary CSV: `{output_dir / 'summary.csv'}`")
    lines.append(f"- Summary JSON: `{output_dir / 'summary.json'}`")
    lines.append(f"- Summary Markdown: `{output_dir / 'summary.md'}`")
    for row in summary_rows:
        model_name = str(row["model"])
        lines.append(f"- Sample CSV `{model_name}`: `{output_dir / f'{model_name}_samples.csv'}`")
    lines.append("")

    return "\n".join(lines)


def print_dependency_summary(selected_models: Sequence[str]) -> None:
    print("Dependency check")
    for model_name in selected_models:
        report = dependency_report(model_name)
        status_text = ", ".join(
            f"{module_name}={'ok' if is_ready else 'missing'}"
            for module_name, is_ready in report.items()
        )
        print(f"  {model_name}: {status_text}")
    print()


def print_run_summary(summary_rows: Sequence[Dict[str, object]]) -> None:
    print("Run summary")
    for row in summary_rows:
        print(
            "  {model}: ok={samples_ok}/{samples_total}, avg_ms={avg_inference_ms}, "
            "mean_error_px={mean_error_px}, pck_005={pck_005}, pck_010={pck_010}".format(**row)
        )
    print()


def run_model(
    model_name: str,
    selected_records: Sequence[Tuple[Pose2DRecord, Dict[str, object]]],
    args,
    output_dir: Path,
) -> Tuple[Optional[Dict[str, object]], Optional[List[Dict[str, object]]], Optional[str]]:
    try:
        runner = create_runner(model_name, args.mmpose_model)
    except Exception as exc:
        return None, None, str(exc)

    sample_rows: List[Dict[str, object]] = []
    prediction_cache: Dict[int, Optional[np.ndarray]] = {}

    try:
        iterator = tqdm(selected_records, desc=model_name, ncols=100)
        for record, bbox_context in iterator:
            image_rgb = load_image_rgb(record.image_path)
            crop_rgb, crop_box = crop_image(image_rgb, bbox_context["bbox"], args.bbox_pad)

            try:
                with Timer() as timer:
                    prediction = runner.infer(crop_rgb)
            except Exception:
                prediction = None
                timer = None

            if prediction is not None:
                prediction = prediction.copy()
                prediction[:, 0] += crop_box[0]
                prediction[:, 1] += crop_box[1]

            prediction_cache[record.sample_index] = prediction
            row = evaluate_prediction(
                record=record,
                prediction=prediction,
                requested_bbox_source=args.bbox_source,
                used_bbox_source=str(bbox_context["used_bbox_source"]),
                crop_box=crop_box,
                inference_ms=timer.elapsed_ms if timer is not None else None,
                confidence_threshold=args.confidence_threshold,
            )
            sample_rows.append(row)
    finally:
        runner.close()

    summary = summarize_rows(model_name, sample_rows)
    summary["per_joint_mean_error_px"] = summarize_joint_errors(
        sample_rows,
        prediction_cache,
        [record for record, _ in selected_records],
    )

    write_rows_csv(sample_rows, output_dir / f"{model_name}_samples.csv")
    return summary, sample_rows, None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare pose models on the local pose_2d dataset.")
    parser.add_argument("--split", default="valid_100", help="Dataset split. Example: valid_100, valid, test, train")
    parser.add_argument("--bbox-source", default="gt", choices=("gt", "det"))
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    parser.add_argument("--limit", type=int, default=None, help="Optional max sample count after stride is applied.")
    parser.add_argument("--stride", type=int, default=1, help="Use every Nth sample.")
    parser.add_argument("--bbox-pad", type=float, default=1.25, help="Padding factor applied around bbox crops.")
    parser.add_argument("--confidence-threshold", type=float, default=0.2)
    parser.add_argument("--mmpose-model", default="rtmpose-m")
    parser.add_argument("--dry-run", action="store_true", help="Only print dependency and dataset info.")
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.stride <= 0:
        raise SystemExit("--stride must be >= 1")

    selected_models = args.models
    invalid_models = [model_name for model_name in selected_models if model_name not in DEFAULT_MODELS]
    if invalid_models:
        raise SystemExit(f"unsupported models: {', '.join(invalid_models)}")

    selected_records, fallback_count = select_records(
        split=args.split,
        bbox_source=args.bbox_source,
        limit=args.limit,
        stride=args.stride,
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = args.output_dir or (RESULTS_DIR / "comparisons" / f"{timestamp}_{args.split}_{args.bbox_source}")
    output_dir.mkdir(parents=True, exist_ok=True)

    print_dependency_summary(selected_models)
    print(f"split={args.split}, bbox_source={args.bbox_source}, samples={len(selected_records)}, fallback_to_gt={fallback_count}")
    print(f"output_dir={output_dir}")
    print()

    if args.dry_run:
        return

    summary_rows: List[Dict[str, object]] = []
    unavailable_models: Dict[str, str] = {}

    for model_name in selected_models:
        summary, _, error_message = run_model(model_name, selected_records, args, output_dir)
        if error_message is not None:
            unavailable_models[model_name] = error_message
            print(f"{model_name}: skipped ({error_message})")
            continue
        if summary is not None:
            summary_rows.append(summary)

    if not summary_rows:
        report_payload = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "split": args.split,
            "bbox_source": args.bbox_source,
            "requested_models": selected_models,
            "unavailable_models": unavailable_models,
            "samples": len(selected_records),
            "fallback_to_gt": fallback_count,
        }
        (output_dir / "summary.json").write_text(json.dumps(report_payload, indent=2), encoding="utf-8")
        raise SystemExit("no models were run successfully")

    write_summary_csv(summary_rows, output_dir / "summary.csv")
    report_payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "split": args.split,
        "bbox_source": args.bbox_source,
        "requested_models": selected_models,
        "completed_models": [row["model"] for row in summary_rows],
        "unavailable_models": unavailable_models,
        "samples": len(selected_records),
        "fallback_to_gt": fallback_count,
        "summaries": summary_rows,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(report_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "summary.md").write_text(
        build_markdown_report(
            summary_rows=summary_rows,
            unavailable_models=unavailable_models,
            args=args,
            output_dir=output_dir,
            sample_count=len(selected_records),
            fallback_count=fallback_count,
        ),
        encoding="utf-8",
    )

    print()
    print_run_summary(summary_rows)
    if unavailable_models:
        print("Skipped models")
        for model_name, error_message in unavailable_models.items():
            print(f"  {model_name}: {error_message}")
        print()

    print(f"summary_csv={output_dir / 'summary.csv'}")
    print(f"summary_json={output_dir / 'summary.json'}")
    print(f"summary_md={output_dir / 'summary.md'}")


if __name__ == "__main__":
    main()
