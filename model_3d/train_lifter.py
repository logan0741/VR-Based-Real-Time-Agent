"""Train/evaluate the actual 2D-to-3D pose lifting model.

Examples:
    python -m model_3d.train_lifter --data pose_3d_v3 --epochs 1 --max-files 20
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
    Pose3DFrameDataset,
    PoseLifterMLP,
    load_lifter_checkpoint,
    mpjpe,
    save_lifter_checkpoint,
    write_json,
)


def main(argv: Optional[List[str]] = None) -> int:
    if torch is None:
        raise RuntimeError("torch is required. Install torch before training the 3D model.")

    parser = argparse.ArgumentParser(description="Train/evaluate the model_3d 2D-to-3D pose lifter.")
    parser.add_argument("--data", type=Path, default=Path("pose_3d_v3"), help="pose_3d_v3 root path.")
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
        default=Path("artifacts/model_3d/checkpoints/pose_lifter_latest.pt"),
    )
    parser.add_argument("--artifacts-dir", type=Path, default=Path("artifacts/model_3d"))
    parser.add_argument("--eval-only", action="store_true")
    args = parser.parse_args(argv)

    device = torch.device(args.device or ("cuda" if torch.cuda.is_available() else "cpu"))
    args.artifacts_dir.mkdir(parents=True, exist_ok=True)

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
        }

    train_history: List[Dict[str, float]] = []
    optimizer = None
    if not args.eval_only:
        train_dataset = Pose3DFrameDataset(args.data, split="train", max_files=args.max_files)
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

    eval_dataset = Pose3DFrameDataset(args.data, split="test", max_files=args.eval_max_files)
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
