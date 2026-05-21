"""Configuration helpers shared by the server and 3D model pipeline."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Union


def env_bool(name: str, default: bool) -> bool:
    """Parse a boolean environment variable without accepting surprising values."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def project_root() -> Path:
    """Return the repository root from inside the model_3d package."""
    return Path(__file__).resolve().parents[2]


def package_root() -> Path:
    """Return the model_3d package root."""
    return Path(__file__).resolve().parent


def resolve_workspace_path(path: Union[Path, str]) -> Path:
    """
    Resolve a path from either the current directory or the repository root.

    This lets commands run from both the repository root and model_3d/.
    """
    candidate = Path(path)
    if candidate.is_absolute() or candidate.exists():
        return candidate

    root_candidate = project_root() / candidate
    if root_candidate.exists():
        return root_candidate

    package_candidate = package_root() / candidate
    if package_candidate.exists():
        return package_candidate

    return root_candidate
