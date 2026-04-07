"""Camera projection used by the SMPL-X reprojection optimizer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    import torch
except ImportError:  # pragma: no cover - startup raises a clear error when fitting.
    torch = None


@dataclass(frozen=True)
class CameraIntrinsics:
    """Fixed pinhole camera used for Phase 1 2D reprojection loss."""

    width: int = 640
    height: int = 480
    fx: float = 500.0
    fy: float = 500.0
    cx: float = 320.0
    cy: float = 240.0
    flip_y: bool = True

    def project(self, joints_3d: Any) -> Any:
        """
        Project camera-space 3D joints to 2D pixels.

        SMPL-X uses a body-centric coordinate convention where Y is usually up.
        Image coordinates use Y down, so flip_y is enabled by default.
        """
        if torch is None:
            raise RuntimeError("torch is required for camera projection.")

        z = joints_3d[..., 2].clamp(min=1e-4)
        x = self.fx * (joints_3d[..., 0] / z) + self.cx
        y_source = -joints_3d[..., 1] if self.flip_y else joints_3d[..., 1]
        y = self.fy * (y_source / z) + self.cy
        return torch.stack((x, y), dim=-1)
