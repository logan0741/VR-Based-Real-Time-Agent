"""End-to-end workflow: train the fitness lifter, validate the pipeline, export Unity sequences."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Optional, Sequence

from model_3d.config import project_root
from model_3d.export_fitness_unity import main as export_fitness_unity_main
from model_3d.pipeline_cli import main as pipeline_cli_main
from model_3d.train_fitness_lifter import main as train_fitness_lifter_main


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the full fitness workflow: training, pipeline QA, and Unity export.",
    )
    parser.add_argument("--epochs", type=int, default=800)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--hidden-dim", type=int, default=512)
    parser.add_argument("--num-layers", type=int, default=4)
    parser.add_argument("--dropout", type=float, default=0.1)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--early-stop-patience", type=int, default=40)
    parser.add_argument("--early-stop-min-delta", type=float, default=1.0)
    parser.add_argument("--checkpoint", type=Path, default=None)
    parser.add_argument("--best-checkpoint", type=Path, default=None)
    parser.add_argument("--train-artifacts-dir", type=Path, default=None)
    parser.add_argument("--pipeline-output", type=Path, default=None)
    parser.add_argument("--sample-input", type=Path, default=Path("sample_keypoints.json"))
    parser.add_argument("--unity-output-dir", type=Path, default=None)
    parser.add_argument("--unity-view", default="view1")
    parser.add_argument("--unity-limit", type=int, default=0)
    parser.add_argument("--skip-train", action="store_true")
    parser.add_argument("--skip-pipeline-check", action="store_true")
    parser.add_argument("--skip-unity-export", action="store_true")
    args = parser.parse_args(argv)

    repo_root = project_root()
    checkpoint = args.checkpoint or (repo_root / "model_3d" / "artifacts" / "checkpoints" / "fitness_pose_lifter_latest.pt")
    best_checkpoint = args.best_checkpoint or checkpoint.with_name(f"{checkpoint.stem}_best{checkpoint.suffix}")
    train_artifacts_dir = args.train_artifacts_dir or (repo_root / "model_3d" / "artifacts" / "training" / "fitness_full")
    pipeline_output = args.pipeline_output or (repo_root / "model_3d" / "artifacts" / "fitness_pipeline_check.json")
    unity_output_dir = args.unity_output_dir or (repo_root / "artifacts" / "unity_fitness_viewer" / "sequences")

    summary = {
        "train": {},
        "pipeline_check": {},
        "unity_export": {},
    }

    if not args.skip_train:
        train_args: List[str] = [
            "--epochs", str(args.epochs),
            "--batch-size", str(args.batch_size),
            "--lr", str(args.lr),
            "--hidden-dim", str(args.hidden_dim),
            "--num-layers", str(args.num_layers),
            "--dropout", str(args.dropout),
            "--max-files", "0",
            "--eval-max-files", "0",
            "--num-workers", str(args.num_workers),
            "--early-stop-patience", str(args.early_stop_patience),
            "--early-stop-min-delta", str(args.early_stop_min_delta),
            "--checkpoint", str(checkpoint),
            "--best-checkpoint", str(best_checkpoint),
            "--artifacts-dir", str(train_artifacts_dir),
        ]
        if args.device:
            train_args.extend(["--device", args.device])
        print("[workflow] training fitness lifter")
        train_fitness_lifter_main(train_args)
        summary["train"] = {
            "checkpoint": str(checkpoint),
            "best_checkpoint": str(best_checkpoint),
            "artifacts_dir": str(train_artifacts_dir),
            "epochs_requested": args.epochs,
        }
    else:
        summary["train"] = {
            "skipped": True,
            "checkpoint": str(checkpoint),
            "best_checkpoint": str(best_checkpoint),
        }

    chosen_checkpoint = best_checkpoint if best_checkpoint.exists() else checkpoint

    if not args.skip_pipeline_check:
        print("[workflow] validating pipeline with the trained lifter checkpoint")
        pipeline_cli_main(
            [
                "--check-all",
                "--lifter-checkpoint", str(chosen_checkpoint),
                "--output", str(pipeline_output),
            ]
        )
        summary["pipeline_check"] = {
            "checkpoint": str(chosen_checkpoint),
            "output": str(pipeline_output),
        }
    else:
        summary["pipeline_check"] = {
            "skipped": True,
            "checkpoint": str(chosen_checkpoint),
        }

    if not args.skip_unity_export:
        print("[workflow] exporting Unity-ready fitness sequences")
        export_args: List[str] = [
            "--split", "train", "val",
            "--view", args.unity_view,
            "--limit", str(args.unity_limit),
            "--output-dir", str(unity_output_dir),
        ]
        export_fitness_unity_main(export_args)
        summary["unity_export"] = {
            "output_dir": str(unity_output_dir),
            "view": args.unity_view,
            "limit": args.unity_limit,
        }
    else:
        summary["unity_export"] = {
            "skipped": True,
        }

    summary_path = repo_root / "model_3d" / "artifacts" / "fitness_to_unity_workflow.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[workflow] summary saved: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
