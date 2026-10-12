"""Re-train PoseLifterNet (17x3 -> 66 SMPL-X params) on the v2 dataset.

Loads the pickled samples produced by prepare_smplx_dataset.py and trains a
PoseLifterNet whose architecture matches the one used inside the FastAPI
server (model_3d/server_app/server.py on this branch;
final/s02_backend/server.py on the App branch).

Checkpoints are written to model_3d/artifacts/checkpoints/v2/:
    smplx_lifter.pt       -> latest (overwritten every epoch)
    smplx_lifter_best.pt  -> lowest validation loss seen so far

NOTE: This does NOT touch the existing checkpoint
      model_3d/artifacts/checkpoints/fitness_pose_lifter_latest_best.pt

Usage:
    python model_3d/train_smplx_v2.py
"""

from __future__ import annotations

import os
import pickle
from typing import Dict, List

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

# --------------------------------------------------------------------------- #
# Paths / hyperparameters
# --------------------------------------------------------------------------- #
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "model_3d", "artifacts", "training", "smplx_v2")
CKPT_DIR = os.path.join(PROJECT_ROOT, "model_3d", "artifacts", "checkpoints", "v2")

TRAIN_PKL = os.path.join(DATA_DIR, "train.pkl")
VAL_PKL = os.path.join(DATA_DIR, "val.pkl")

NUM_EPOCHS = 500
BATCH_SIZE = 128
LEARNING_RATE = 1e-3
LOG_EVERY = 50


# --------------------------------------------------------------------------- #
# Model (must match model_3d/server_app/server.py PoseLifterNet)
# --------------------------------------------------------------------------- #
class PoseLifterNet(nn.Module):
    """Lightweight MLP that maps COCO-17 keypoints to SMPL-X pose params."""

    def __init__(self, hidden_dim: int = 512, num_layers: int = 4, dropout: float = 0.1):
        super().__init__()
        layers = []
        in_dim = 17 * 3
        out_dim = 3 + 63  # global_orient + body_pose

        for i in range(num_layers):
            layers.append(nn.Linear(in_dim if i == 0 else hidden_dim, hidden_dim))
            layers.append(nn.LayerNorm(hidden_dim))
            layers.append(nn.GELU())
            layers.append(nn.Dropout(dropout))

        layers.append(nn.Linear(hidden_dim, out_dim))
        self.network = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.network(x.reshape(x.shape[0], -1))


# --------------------------------------------------------------------------- #
# Dataset
# --------------------------------------------------------------------------- #
class PoseDataset(Dataset):
    def __init__(self, samples: List[Dict[str, np.ndarray]]):
        self.inputs = torch.from_numpy(
            np.stack([s["input"] for s in samples]).astype(np.float32)
        )  # (N, 17, 3)
        self.targets = torch.from_numpy(
            np.stack([s["target"] for s in samples]).astype(np.float32)
        )  # (N, 66)

    def __len__(self) -> int:
        return self.inputs.shape[0]

    def __getitem__(self, idx: int):
        return self.inputs[idx], self.targets[idx]


def load_samples(path: str) -> List[Dict[str, np.ndarray]]:
    with open(path, "rb") as fh:
        return pickle.load(fh)


# --------------------------------------------------------------------------- #
# Train / eval loops
# --------------------------------------------------------------------------- #
def run_epoch(model, loader, criterion, optimizer, device, train: bool) -> float:
    model.train(train)
    total_loss = 0.0
    total_count = 0
    torch.set_grad_enabled(train)
    for inputs, targets in loader:
        inputs = inputs.to(device)
        targets = targets.to(device)
        preds = model(inputs)
        loss = criterion(preds, targets)
        if train:
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
        bs = inputs.shape[0]
        total_loss += loss.item() * bs
        total_count += bs
    torch.set_grad_enabled(True)
    return total_loss / max(total_count, 1)


def main() -> None:
    os.makedirs(CKPT_DIR, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device      : {device}")
    print(f"Data dir    : {DATA_DIR}")
    print(f"Ckpt dir    : {CKPT_DIR}")

    train_samples = load_samples(TRAIN_PKL)
    val_samples = load_samples(VAL_PKL)
    print(f"Train       : {len(train_samples)} samples")
    print(f"Val         : {len(val_samples)} samples")

    train_loader = DataLoader(
        PoseDataset(train_samples), batch_size=BATCH_SIZE, shuffle=True
    )
    val_loader = DataLoader(
        PoseDataset(val_samples), batch_size=BATCH_SIZE, shuffle=False
    )

    model = PoseLifterNet().to(device)
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)

    latest_path = os.path.join(CKPT_DIR, "smplx_lifter.pt")
    best_path = os.path.join(CKPT_DIR, "smplx_lifter_best.pt")
    best_val = float("inf")

    print("-" * 60)
    for epoch in range(1, NUM_EPOCHS + 1):
        train_loss = run_epoch(model, train_loader, criterion, optimizer, device, train=True)
        val_loss = run_epoch(model, val_loader, criterion, optimizer, device, train=False)

        # Latest checkpoint every epoch.
        torch.save(
            {
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "train_loss": train_loss,
                "val_loss": val_loss,
            },
            latest_path,
        )

        # Best checkpoint on improved validation loss.
        if val_loss < best_val:
            best_val = val_loss
            torch.save(
                {
                    "epoch": epoch,
                    "model_state_dict": model.state_dict(),
                    "train_loss": train_loss,
                    "val_loss": val_loss,
                },
                best_path,
            )

        if epoch % LOG_EVERY == 0 or epoch == 1:
            print(
                f"epoch {epoch:4d}/{NUM_EPOCHS} | "
                f"train {train_loss:.6f} | val {val_loss:.6f} | best {best_val:.6f}"
            )

    print("-" * 60)
    print(f"Best val loss : {best_val:.6f}")
    print(f"Latest ckpt   : {latest_path}")
    print(f"Best ckpt     : {best_path}")
    print("Done.")


if __name__ == "__main__":
    main()
