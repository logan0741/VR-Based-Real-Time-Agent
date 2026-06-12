"""Throttle and hold live feedback messages."""
from __future__ import annotations

from typing import Any


PENDING_RESULT: dict[str, Any] = {
    "message": "측정 중입니다.",
    "body_part": "pending",
    "state": "warming_up",
    "severity": 0.0,
    "bad_joints": [],
}


class FeedbackPolicy:
    """Accept one meaningful feedback event, hold it, then allow the next one."""

    def __init__(self, hold_frames: int) -> None:
        if hold_frames <= 0:
            raise ValueError(f"hold_frames must be positive: {hold_frames}")
        self._hold_frames = hold_frames
        self._active_result: dict[str, Any] = dict(PENDING_RESULT)
        self._expire_at: int = -1

    def consider(self, frame_idx: int, candidate: dict[str, object]) -> tuple[dict[str, Any], bool]:
        """Return the visible feedback and whether this frame accepted a new event."""
        if self._expire_at != -1 and frame_idx >= self._expire_at:
            self._active_result = dict(PENDING_RESULT)
            self._expire_at = -1

        if self._expire_at != -1:
            return dict(self._active_result), False

        body_part = str(candidate.get("body_part", ""))
        message = str(candidate.get("message", ""))
        if body_part in {"", "pending"} or not message:
            return dict(self._active_result), False

        self._active_result = dict(candidate)
        self._expire_at = frame_idx + self._hold_frames
        return dict(self._active_result), True

    def on_rep_complete(self, frame_idx: int, candidate: dict[str, object]) -> None:
        self._active_result = dict(candidate)
        self._expire_at = frame_idx + self._hold_frames

    def update(self, frame_idx: int) -> str:
        if self._expire_at != -1 and frame_idx >= self._expire_at:
            self._active_result = dict(PENDING_RESULT)
            self._expire_at = -1
        return str(self._active_result["message"])
