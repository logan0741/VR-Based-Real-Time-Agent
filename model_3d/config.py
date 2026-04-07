"""Configuration helpers shared by the server and 3D model pipeline."""

from __future__ import annotations

import os
from pathlib import Path


def env_bool(name: str, default: bool) -> bool:
    """Parse a boolean environment variable without accepting surprising values."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def project_root() -> Path:
    """Return the repository root from inside the model_3d package."""
    return Path(__file__).resolve().parents[1]
