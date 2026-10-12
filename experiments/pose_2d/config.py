from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict


EXPERIMENT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = EXPERIMENT_DIR.parent.parent
POSE2D_DIR = PROJECT_DIR / "pose_2d"
ANNOTATION_DIR = POSE2D_DIR / "annotations"
DETECTION_DIR = POSE2D_DIR / "det_result"
RESULTS_DIR = EXPERIMENT_DIR / "results"
SUMMARY_DIR = RESULTS_DIR / "summaries"

for directory in (RESULTS_DIR, SUMMARY_DIR):
    directory.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class SplitConfig:
    name: str
    annotation_file: Path
    image_dir: Path
    detection_file: Path


SPLIT_ALIASES: Dict[str, str] = {
    "train": "train",
    "train_set": "train",
    "valid": "valid",
    "valid_set": "valid",
    "val": "valid",
    "test": "test",
    "test_set": "test",
    "valid_100": "valid_100",
    "valid100": "valid_100",
    "valid_set_100": "valid_100",
}

SPLIT_CONFIGS: Dict[str, SplitConfig] = {
    "train": SplitConfig(
        name="train",
        annotation_file=ANNOTATION_DIR / "train_set.json",
        image_dir=POSE2D_DIR / "train_set",
        detection_file=DETECTION_DIR / "ap2d_train_det.json",
    ),
    "valid": SplitConfig(
        name="valid",
        annotation_file=ANNOTATION_DIR / "valid_set.json",
        image_dir=POSE2D_DIR / "valid_set",
        detection_file=DETECTION_DIR / "ap2d_valid_det.json",
    ),
    "test": SplitConfig(
        name="test",
        annotation_file=ANNOTATION_DIR / "test_set.json",
        image_dir=POSE2D_DIR / "test_set",
        detection_file=DETECTION_DIR / "ap2d_test_det.json",
    ),
    "valid_100": SplitConfig(
        name="valid_100",
        annotation_file=ANNOTATION_DIR / "valid_set_100.json",
        image_dir=POSE2D_DIR / "valid_set",
        detection_file=DETECTION_DIR / "ap2d_valid_det_100.json",
    ),
}

DEFAULT_SPLITS = ("train", "valid", "test")


def resolve_split_name(split: str) -> str:
    normalized = split.strip().lower()
    if normalized not in SPLIT_ALIASES:
        available = ", ".join(sorted(SPLIT_CONFIGS))
        raise KeyError(f"Unsupported split '{split}'. Available: {available}")
    return SPLIT_ALIASES[normalized]


def get_split_config(split: str) -> SplitConfig:
    return SPLIT_CONFIGS[resolve_split_name(split)]
