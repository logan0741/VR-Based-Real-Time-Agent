"""3D Pose Retargeting & Smoothing for natural avatar motion.

Applies temporal filters to raw per-frame pose estimation output to remove
jitter and produce smooth, natural-looking motion suitable for real-time
avatar driving.

Filters implemented:
  - OneEuro Filter: Adaptive low-pass filter (Casiez et al., 2012) that
    smooths slow movements while preserving fast, intentional motions.
  - Exponential Moving Average (EMA): Simple temporal smoothing fallback.
  - Velocity Clamping: Caps maximum per-frame joint displacement to prevent
    physically impossible jumps.

Usage:
    retargeter = PoseRetargeter()
    smoothed = retargeter.smooth_body_pose(raw_body_pose_63)
    smoothed_orient = retargeter.smooth_global_orient(raw_orient_3)
    smoothed_joints = retargeter.smooth_joints_3d(raw_joints_17x3)
"""

from __future__ import annotations

import math
import os
import time
from typing import Dict, Optional

import numpy as np

from .config import env_bool


# ---------------------------------------------------------------------------
# OneEuro Filter (Casiez et al., CHI 2012)
# ---------------------------------------------------------------------------

class LowPassFilter:
    """First-order exponential low-pass filter."""

    __slots__ = ("_y", "_initialized")

    def __init__(self) -> None:
        self._y: float = 0.0
        self._initialized: bool = False

    def reset(self) -> None:
        self._initialized = False

    def __call__(self, x: float, alpha: float) -> float:
        if not self._initialized:
            self._y = x
            self._initialized = True
        else:
            self._y = alpha * x + (1.0 - alpha) * self._y
        return self._y


class OneEuroFilter:
    """Adaptive low-pass filter per Casiez et al. (2012).

    Smooths slow movements aggressively while letting fast, intentional
    movements through with minimal lag.

    Parameters:
        min_cutoff: Minimum cutoff frequency in Hz.  Lower values give more
            smoothing for slow movements.  Default 1.0 is good for body joints.
        beta: Speed coefficient.  Higher values let fast movements through
            more easily.  Default 0.007 is conservative.
        d_cutoff: Cutoff frequency for the derivative filter.
    """

    __slots__ = ("min_cutoff", "beta", "d_cutoff", "_x_filter", "_dx_filter",
                 "_last_time", "_freq")

    def __init__(
        self,
        min_cutoff: float = 1.0,
        beta: float = 0.007,
        d_cutoff: float = 1.0,
    ) -> None:
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self._x_filter = LowPassFilter()
        self._dx_filter = LowPassFilter()
        self._last_time: Optional[float] = None
        self._freq: float = 30.0  # initial assumption

    def reset(self) -> None:
        self._x_filter.reset()
        self._dx_filter.reset()
        self._last_time = None

    @staticmethod
    def _smoothing_factor(te: float, cutoff: float) -> float:
        r = 2.0 * math.pi * cutoff * te
        return r / (r + 1.0)

    def __call__(self, x: float, t: Optional[float] = None) -> float:
        now = t if t is not None else time.perf_counter()
        if self._last_time is not None and now > self._last_time:
            self._freq = 1.0 / (now - self._last_time)
        self._last_time = now

        te = 1.0 / max(self._freq, 1e-6)

        # Estimate derivative (speed).
        d_alpha = self._smoothing_factor(te, self.d_cutoff)
        prev_y = self._x_filter._y if self._x_filter._initialized else x
        dx = (x - prev_y) * self._freq
        edx = self._dx_filter(dx, d_alpha)

        # Adapt cutoff based on speed.
        cutoff = self.min_cutoff + self.beta * abs(edx)
        alpha = self._smoothing_factor(te, cutoff)

        return self._x_filter(x, alpha)


# ---------------------------------------------------------------------------
# Multi-channel filter bank
# ---------------------------------------------------------------------------

class OneEuroFilterBank:
    """Apply independent OneEuro filters to each channel of a flat array."""

    def __init__(self, num_channels: int, **kwargs) -> None:
        self.filters = [OneEuroFilter(**kwargs) for _ in range(num_channels)]

    def reset(self) -> None:
        for f in self.filters:
            f.reset()

    def __call__(self, values: np.ndarray, t: Optional[float] = None) -> np.ndarray:
        flat = values.ravel().astype(float)
        assert len(flat) == len(self.filters), (
            f"Expected {len(self.filters)} channels, got {len(flat)}"
        )
        now = t if t is not None else time.perf_counter()
        return np.array(
            [f(float(v), now) for f, v in zip(self.filters, flat)],
            dtype=np.float32,
        ).reshape(values.shape)


# ---------------------------------------------------------------------------
# Velocity Clamping
# ---------------------------------------------------------------------------

class VelocityClamper:
    """Clamp per-frame displacement so joints can't teleport."""

    def __init__(self, max_delta: float = 0.5) -> None:
        self.max_delta = max_delta
        self._prev: Optional[np.ndarray] = None

    def reset(self) -> None:
        self._prev = None

    def __call__(self, values: np.ndarray) -> np.ndarray:
        if self._prev is None:
            self._prev = values.copy()
            return values

        delta = values - self._prev
        norms = np.linalg.norm(delta.reshape(-1, 3), axis=-1, keepdims=True)
        scale = np.where(
            norms > self.max_delta,
            self.max_delta / np.maximum(norms, 1e-8),
            1.0,
        )
        clamped_delta = (delta.reshape(-1, 3) * scale).reshape(values.shape)
        result = self._prev + clamped_delta
        self._prev = result.copy()
        return result


# ---------------------------------------------------------------------------
# PoseRetargeter — unified smoothing interface
# ---------------------------------------------------------------------------

class PoseRetargeter:
    """Temporal smoothing for real-time pose estimation output.

    Wraps OneEuro filters and velocity clamping for the three main pose
    signals: body_pose (63-dim axis-angle), global_orient (3-dim), and
    raw 3D joint positions (17×3).

    Parameters are read from environment variables with sensible defaults:
        SMOOTHING_ENABLED        — true/false (default: true)
        SMOOTHING_MIN_CUTOFF     — float (default: 1.0)
        SMOOTHING_BETA           — float (default: 0.007)
        SMOOTHING_D_CUTOFF       — float (default: 1.0)
        SMOOTHING_MAX_VELOCITY   — float, max per-frame delta (default: 0.5)
    """

    def __init__(
        self,
        enabled: Optional[bool] = None,
        min_cutoff: Optional[float] = None,
        beta: Optional[float] = None,
        d_cutoff: Optional[float] = None,
        max_velocity: Optional[float] = None,
    ) -> None:
        self.enabled = (
            enabled if enabled is not None
            else env_bool("SMOOTHING_ENABLED", True)
        )
        _min_cutoff = min_cutoff or float(os.getenv("SMOOTHING_MIN_CUTOFF", "1.0"))
        _beta = beta or float(os.getenv("SMOOTHING_BETA", "0.007"))
        _d_cutoff = d_cutoff or float(os.getenv("SMOOTHING_D_CUTOFF", "1.0"))
        _max_velocity = max_velocity or float(os.getenv("SMOOTHING_MAX_VELOCITY", "0.5"))

        filter_kwargs = dict(min_cutoff=_min_cutoff, beta=_beta, d_cutoff=_d_cutoff)

        # body_pose: 21 joints × 3 axis-angle = 63 channels
        self._body_pose_filter = OneEuroFilterBank(63, **filter_kwargs)
        self._body_pose_clamper = VelocityClamper(max_delta=_max_velocity)

        # global_orient: 3 channels
        self._orient_filter = OneEuroFilterBank(3, **filter_kwargs)
        self._orient_clamper = VelocityClamper(max_delta=_max_velocity * 0.5)

        # joints_3d: 17 joints × 3 coords = 51 channels
        self._joints_filter = OneEuroFilterBank(51, **filter_kwargs)
        self._joints_clamper = VelocityClamper(max_delta=_max_velocity)

        self._frame_count = 0

    def reset(self) -> None:
        """Reset all filters. Call when starting a new exercise sequence."""
        self._body_pose_filter.reset()
        self._body_pose_clamper.reset()
        self._orient_filter.reset()
        self._orient_clamper.reset()
        self._joints_filter.reset()
        self._joints_clamper.reset()
        self._frame_count = 0

    @property
    def frame_count(self) -> int:
        return self._frame_count

    def smooth_body_pose(self, raw: np.ndarray, t: Optional[float] = None) -> np.ndarray:
        """Smooth 63-dim body_pose axis-angle vector."""
        if not self.enabled:
            return raw
        arr = np.asarray(raw, dtype=np.float32).ravel()
        assert arr.shape == (63,), f"body_pose must be 63-dim, got {arr.shape}"
        clamped = self._body_pose_clamper(arr)
        return self._body_pose_filter(clamped, t)

    def smooth_global_orient(self, raw: np.ndarray, t: Optional[float] = None) -> np.ndarray:
        """Smooth 3-dim global_orient axis-angle vector."""
        if not self.enabled:
            return raw
        arr = np.asarray(raw, dtype=np.float32).ravel()
        assert arr.shape == (3,), f"global_orient must be 3-dim, got {arr.shape}"
        clamped = self._orient_clamper(arr)
        return self._orient_filter(clamped, t)

    def smooth_joints_3d(self, raw: np.ndarray, t: Optional[float] = None) -> np.ndarray:
        """Smooth 17×3 joint positions."""
        if not self.enabled:
            return raw
        arr = np.asarray(raw, dtype=np.float32)
        original_shape = arr.shape
        assert arr.size == 51, f"joints_3d must be 17×3=51 values, got {arr.size}"
        flat = arr.ravel()
        clamped = self._joints_clamper(flat)
        smoothed = self._joints_filter(clamped, t)
        self._frame_count += 1
        return smoothed.reshape(original_shape)

    def smooth_all(
        self,
        body_pose: np.ndarray,
        global_orient: np.ndarray,
        joints_3d: Optional[np.ndarray] = None,
        t: Optional[float] = None,
    ) -> Dict[str, np.ndarray]:
        """Convenience method to smooth all signals at once."""
        result = {
            "body_pose": self.smooth_body_pose(body_pose, t),
            "global_orient": self.smooth_global_orient(global_orient, t),
        }
        if joints_3d is not None:
            result["joints_3d"] = self.smooth_joints_3d(joints_3d, t)
        return result
