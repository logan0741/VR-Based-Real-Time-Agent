"""Train the pose lifter on the prepared fitness subset with sensible defaults.

Examples:
    python -m model_3d.train_fitness_lifter
    python -m model_3d.train_fitness_lifter --epochs 800 --batch-size 128
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from model_3d.config import project_root
from model_3d.train_lifter import main as train_lifter_main


DEFAULT_OUTPUT_NAME = "prepared_train_eval_body01_compact"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Train model_3d on the prepared fitness subset without typing the dataset path.",
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=None,
        help="Prepared fitness subset root. Auto-discovered when omitted.",
    )
    parser.add_argument("--epochs", type=int, default=800)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--hidden-dim", type=int, default=512)
    parser.add_argument("--num-layers", type=int, default=4)
    parser.add_argument("--dropout", type=float, default=0.1)
    parser.add_argument(
        "--max-files",
        type=int,
        default=0,
        help="Training label pairs to use. 0 means the whole train split.",
    )
    parser.add_argument(
        "--eval-max-files",
        type=int,
        default=0,
        help="Validation label pairs to use. 0 means the whole val split.",
    )
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--device", default=None)
    parser.add_argument("--max-hours", type=float, default=0.0)
    parser.add_argument("--early-stop-patience", type=int, default=40)
    parser.add_argument("--early-stop-min-delta", type=float, default=1.0)
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--best-checkpoint",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=None,
    )
    parser.add_argument("--eval-only", action="store_true")
    args = parser.parse_args(argv)

    repo_root = project_root()
    data_root = args.data or discover_prepared_fitness_dataset_root()
    checkpoint = args.checkpoint or (repo_root / "model_3d" / "artifacts" / "checkpoints" / "fitness_pose_lifter_latest.pt")
    best_checkpoint = args.best_checkpoint or checkpoint.with_name(f"{checkpoint.stem}_best{checkpoint.suffix}")
    artifacts_dir = args.artifacts_dir or (repo_root / "model_3d" / "artifacts" / "training" / "fitness_full")
    forwarded_args = [
        "--data",
        str(data_root),
        "--dataset-format",
        "fitness_json",
        "--train-split",
        "train",
        "--eval-split",
        "val",
        "--epochs",
        str(args.epochs),
        "--batch-size",
        str(args.batch_size),
        "--lr",
        str(args.lr),
        "--hidden-dim",
        str(args.hidden_dim),
        "--num-layers",
        str(args.num_layers),
        "--dropout",
        str(args.dropout),
        "--max-files",
        str(args.max_files),
        "--eval-max-files",
        str(args.eval_max_files),
        "--num-workers",
        str(args.num_workers),
        "--max-hours",
        str(args.max_hours),
        "--early-stop-patience",
        str(args.early_stop_patience),
        "--early-stop-min-delta",
        str(args.early_stop_min_delta),
        "--checkpoint",
        str(checkpoint),
        "--best-checkpoint",
        str(best_checkpoint),
        "--artifacts-dir",
        str(artifacts_dir),
    ]
    if args.device:
        forwarded_args.extend(["--device", str(args.device)])
    if args.eval_only:
        forwarded_args.append("--eval-only")
    return train_lifter_main(forwarded_args)


def discover_prepared_fitness_dataset_root() -> Path:
    root = project_root()
    candidates = sorted(
        candidate / DEFAULT_OUTPUT_NAME
        for candidate in root.iterdir()
        if candidate.is_dir() and candidate.name.startswith("013.") and (candidate / DEFAULT_OUTPUT_NAME).exists()
    )
    if not candidates:
        raise FileNotFoundError(
            f"Could not find {DEFAULT_OUTPUT_NAME} under a local 013.* dataset directory."
        )
    return candidates[0]


if __name__ == "__main__":
    raise SystemExit(main())
