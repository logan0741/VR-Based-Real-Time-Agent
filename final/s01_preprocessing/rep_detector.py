"""Angle/range based repetition detector for COCO-17 keypoint frames."""
from __future__ import annotations

from enum import Enum, auto

import numpy as np

from .rep_rules import ANGLE_REP_RULES, SUPPORTED_DETECTOR_TYPES, SUPPORTED_NORMALIZER_TYPES
from .rep_signals import extract_rep_signal


class _RepState(Enum):
    WAIT_READY = auto()
    WAIT_TARGET = auto()
    WAIT_RETURN = auto()


class RepDetector:
    """Detect completed reps from exercise-specific joint angles.

    The detector intentionally does not count tiny jitter. A rep must start from
    a ready position, cross a target angle, move through a minimum range, and
    return to the ready side before it is counted.
    """

    def __init__(
        self,
        rep_detector_type: str,
        normalizer_type: str,
        slope_window: int,
        min_rep_frames: int,
    ) -> None:
        if rep_detector_type not in SUPPORTED_DETECTOR_TYPES:
            raise ValueError(f"Unsupported rep_detector_type: {rep_detector_type!r}")
        if normalizer_type not in SUPPORTED_NORMALIZER_TYPES:
            raise ValueError(f"Unsupported normalizer_type: {normalizer_type!r}")

        self._type = rep_detector_type
        self._normalizer_type = normalizer_type
        self._min_rep_frames = min_rep_frames

        self._state: _RepState = _RepState.WAIT_READY
        self._rep_start: int = 0
        self._reps: list[tuple[int, int]] = []
        self._frame_idx: int = 0
        self._range_min: float = float("inf")
        self._range_max: float = float("-inf")

    def update(self, norm_frame: np.ndarray) -> list[tuple[int, int]]:
        signal = self._extract_signal(norm_frame)
        self._step(signal)
        self._frame_idx += 1
        return self._valid_reps()

    def finalize(self) -> list[tuple[int, int]]:
        return self._valid_reps()

    def _extract_signal(self, norm_frame: np.ndarray) -> float:
        return extract_rep_signal(self._type, self._normalizer_type, norm_frame)

    def _step(self, signal: float) -> None:
        rule = ANGLE_REP_RULES[self._type]
        direction = str(rule["direction"])
        ready = float(rule["ready"])
        target = float(rule["target"])
        finish = float(rule["return"])
        min_range = float(rule["min_range"])

        if self._state == _RepState.WAIT_READY:
            if _is_ready(signal, direction, ready):
                self._rep_start = self._frame_idx
                self._range_min = signal
                self._range_max = signal
                self._state = _RepState.WAIT_TARGET
            return

        self._range_min = min(self._range_min, signal)
        self._range_max = max(self._range_max, signal)

        if self._state == _RepState.WAIT_TARGET:
            if _hit_target(signal, direction, target):
                self._state = _RepState.WAIT_RETURN
            return

        if self._state == _RepState.WAIT_RETURN and _is_ready(signal, direction, finish):
            moved_range = self._range_max - self._range_min
            if moved_range >= min_range:
                self._reps.append((self._rep_start, self._frame_idx))
            self._rep_start = self._frame_idx
            self._range_min = signal
            self._range_max = signal
            self._state = _RepState.WAIT_TARGET

    def _valid_reps(self) -> list[tuple[int, int]]:
        return [(s, e) for s, e in self._reps if e - s >= self._min_rep_frames]


def _is_ready(signal: float, direction: str, threshold: float) -> bool:
    if direction == "increase":
        return signal <= threshold
    return signal >= threshold


def _hit_target(signal: float, direction: str, threshold: float) -> bool:
    if direction == "increase":
        return signal >= threshold
    return signal <= threshold
