"""Train/evaluate the actual 2D-to-3D pose lifting model.

Examples:
    python -m model_3d.train_lifter --data pose_3d_v3 --epochs 1 --max-files 20
    python -m model_3d.train_lifter --data 013.피트니스자세/prepared_train_eval_body01_compact --dataset-format fitness_json --epochs 5
    python -m model_3d.train_lifter --data pose_3d_v3 --eval-only --checkpoint artifacts/model_3d/checkpoints/pose_lifter_latest.pt
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader
except ImportError:  # pragma: no cover - command raises a clear error when used.
    torch = None
    nn = None
    DataLoader = None

from model_3d.lifter_model import (
    build_pose_lifter_dataset,
    detect_training_dataset_format,
    PoseLifterMLP,
    load_lifter_checkpoint,
    mpjpe,
    save_lifter_checkpoint,
    write_json,
)
from model_3d.config import package_root, resolve_workspace_path


def main(argv: Optional[List[str]] = None) -> int:
    if torch is None:
        raise RuntimeError("torch is required. Install torch before training the 3D model.")

    parser = argparse.ArgumentParser(description="Train/evaluate the model_3d 2D-to-3D pose lifter.")
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("pose_3d_v3"),
        help="Dataset root. Supports pose_3d_v3 or the prepared fitness subset.",
    )
    parser.add_argument(
        "--dataset-format",
        default="auto",
        choices=["auto", "pose3d_v3", "fitness_json"],
        help="Dataset format. Use auto to infer from the provided root.",
    )
    parser.add_argument("--train-split", default=None, help="Train split name. Defaults depend on dataset format.")
    parser.add_argument("--eval-split", default=None, help="Eval split name. Defaults depend on dataset format.")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--hidden-dim", type=int, default=512)
    parser.add_argument("--num-layers", type=int, default=4)
    parser.add_argument("--dropout", type=float, default=0.1)
    parser.add_argument("--max-files", type=int, default=100, help="Limit files for quick local runs.")
    parser.add_argument("--eval-max-files", type=int, default=20)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--device", default=None, help="cuda, cpu, or omitted for auto.")
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=package_root() / "artifacts" / "checkpoints" / "pose_lifter_latest.pt",
    )
    parser.add_argument("--artifacts-dir", type=Path, default=package_root() / "artifacts" / "training")
    parser.add_argument("--eval-only", action="store_true")
    args = parser.parse_args(argv)

    device = torch.device(args.device or ("cuda" if torch.cuda.is_available() else "cpu"))
    args.artifacts_dir.mkdir(parents=True, exist_ok=True)
    data_root = resolve_workspace_path(args.data)
    dataset_format = detect_training_dataset_format(data_root) if args.dataset_format == "auto" else args.dataset_format
    train_split = args.train_split or "train"
    eval_split = args.eval_split or ("val" if dataset_format == "fitness_json" else "test")
    print(f"[data] root={data_root}")
    print(f"[data] format={dataset_format} train_split={train_split} eval_split={eval_split}")

    if args.eval_only:
        checkpoint = load_lifter_checkpoint(args.checkpoint, device=str(device))
        model = checkpoint["model"]
        config = checkpoint["checkpoint"].get("config", {})
    else:
        model = PoseLifterMLP(
            hidden_dim=args.hidden_dim,
            num_layers=args.num_layers,
            dropout=args.dropout,
        ).to(device)
        config = {
            "hidden_dim": args.hidden_dim,
            "num_layers": args.num_layers,
            "dropout": args.dropout,
            "input_shape": [17, 3],
            "output_shape": [17, 3],
            "dataset_format": dataset_format,
            "data_root": str(data_root),
            "train_split": train_split,
            "eval_split": eval_split,
        }

    train_history: List[Dict[str, float]] = []
    optimizer = None
    if not args.eval_only:
        train_dataset = build_pose_lifter_dataset(
            data_root,
            split=train_split,
            max_files=args.max_files,
            dataset_format=dataset_format,
        )
        print(f"[train] samples={len(train_dataset)}")
        train_loader = DataLoader(
            train_dataset,
            batch_size=args.batch_size,
            shuffle=True,
            num_workers=args.num_workers,
            pin_memory=device.type == "cuda",
        )
        optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
        loss_fn = nn.MSELoss()

        for epoch in range(1, args.epochs + 1):
            train_metrics = train_one_epoch(model, train_loader, optimizer, loss_fn, device, epoch)
            train_history.append(train_metrics)
            print(
                "[train] "
                f"epoch={epoch}/{args.epochs} "
                f"loss={train_metrics['loss']:.6f} "
                f"mpjpe={train_metrics['mpjpe']:.6f} "
                f"fps={train_metrics['samples_per_sec']:.1f}"
            )
            save_lifter_checkpoint(
                args.checkpoint,
                model,
                optimizer,
                epoch,
                config,
                {"train": train_metrics},
            )

    eval_dataset = build_pose_lifter_dataset(
        data_root,
        split=eval_split,
        max_files=args.eval_max_files,
        dataset_format=dataset_format,
    )
    print(f"[eval] samples={len(eval_dataset)}")
    eval_loader = DataLoader(
        eval_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
        pin_memory=device.type == "cuda",
    )
    eval_metrics = evaluate(model, eval_loader, device)
    print(
        "[eval] "
        f"loss={eval_metrics['loss']:.6f} "
        f"mpjpe={eval_metrics['mpjpe']:.6f} "
        f"samples={eval_metrics['samples']}"
    )

    metrics = {
        "device": str(device),
        "dataset_format": dataset_format,
        "data_root": str(data_root),
        "train_split": train_split,
        "eval_split": eval_split,
        "checkpoint": str(args.checkpoint),
        "train_history": train_history,
        "eval": eval_metrics,
    }
    write_json(args.artifacts_dir / "pose_lifter_metrics.json", metrics)
    save_training_curve(args.artifacts_dir / "pose_lifter_training_curve.png", train_history, eval_metrics)
    save_lifter_checkpoint(
        args.checkpoint,
        model,
        optimizer,
        int(train_history[-1]["epoch"]) if train_history else int(eval_metrics.get("epoch", 0)),
        config,
        metrics,
    )
    print(f"[checkpoint] saved: {args.checkpoint}")
    print(f"[artifacts] dir: {args.artifacts_dir}")
    return 0


def train_one_epoch(
    model: Any,
    loader: Any,
    optimizer: Any,
    loss_fn: Any,
    device: Any,
    epoch: int,
) -> Dict[str, float]:
    model.train()
    total_loss = 0.0
    total_mpjpe = 0.0
    total_samples = 0
    start = time.perf_counter()

    for batch in loader:
        inputs = batch["input"].to(device, non_blocking=True).float()
        targets = batch["target"].to(device, non_blocking=True).float()
        optimizer.zero_grad(set_to_none=True)
        predictions = model(inputs)
        loss = loss_fn(predictions, targets)
        loss.backward()
        optimizer.step()

        batch_size = int(inputs.shape[0])
        total_loss += float(loss.detach().cpu().item()) * batch_size
        total_mpjpe += float(mpjpe(predictions.detach(), targets).detach().cpu().item()) * batch_size
        total_samples += batch_size

    elapsed = max(1e-6, time.perf_counter() - start)
    return {
        "epoch": float(epoch),
        "loss": total_loss / max(1, total_samples),
        "mpjpe": total_mpjpe / max(1, total_samples),
        "samples": float(total_samples),
        "samples_per_sec": total_samples / elapsed,
    }


def evaluate(model: Any, loader: Any, device: Any) -> Dict[str, float]:
    model.eval()
    total_loss = 0.0
    total_mpjpe = 0.0
    total_samples = 0
    loss_fn = nn.MSELoss(reduction="mean")
    with torch.no_grad():
        for batch in loader:
            inputs = batch["input"].to(device, non_blocking=True).float()
            targets = batch["target"].to(device, non_blocking=True).float()
            predictions = model(inputs)
            loss = loss_fn(predictions, targets)
            batch_size = int(inputs.shape[0])
            total_loss += float(loss.detach().cpu().item()) * batch_size
            total_mpjpe += float(mpjpe(predictions, targets).detach().cpu().item()) * batch_size
            total_samples += batch_size

    return {
        "loss": total_loss / max(1, total_samples),
        "mpjpe": total_mpjpe / max(1, total_samples),
        "samples": float(total_samples),
    }


def save_training_curve(path: Path, train_history: List[Dict[str, float]], eval_metrics: Dict[str, float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 1, figsize=(7, 6), dpi=120, sharex=True)

    if train_history:
        epochs = list(range(1, len(train_history) + 1))
        axes[0].plot(epochs, [item["loss"] for item in train_history], marker="o", label="train loss")
        axes[1].plot(epochs, [item["mpjpe"] for item in train_history], marker="o", label="train MPJPE")
    else:
        epochs = [1]
        axes[0].plot(epochs, [math.nan], marker="o", label="train loss")
        axes[1].plot(epochs, [math.nan], marker="o", label="train MPJPE")

    axes[0].axhline(eval_metrics["loss"], color="#e53935", linestyle="--", label="eval loss")
    axes[1].axhline(eval_metrics["mpjpe"], color="#e53935", linestyle="--", label="eval MPJPE")
    axes[0].set_ylabel("MSE")
    axes[1].set_ylabel("MPJPE")
    axes[1].set_xlabel("epoch")
    axes[0].grid(True, alpha=0.3)
    axes[1].grid(True, alpha=0.3)
    axes[0].legend()
    axes[1].legend()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


if __name__ == "__main__":
    raise SystemExit(main())
