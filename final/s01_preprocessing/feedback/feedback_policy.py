"""rep 완료 피드백 메시지를 일정 프레임 동안 유지하는 정책 클래스."""
from __future__ import annotations


class FeedbackPolicy:
    """rep 완료 시 피드백 메시지를 hold_frames 동안 유지하는 클래스."""

    def __init__(self, hold_frames: int) -> None:
        """hold_frames 동안 rep 완료 피드백 메시지를 유지한다."""
        if hold_frames <= 0:
            raise ValueError(f"hold_frames must be positive: {hold_frames}")
        self._hold_frames = hold_frames
        self._active_message: str = "측정 중입니다."
        self._expire_at: int = -1

    def on_rep_complete(self, frame_idx: int, candidate: dict[str, object]) -> None:
        """rep 완료 시 피드백 메시지를 갱신하고 hold_frames 후 만료를 설정한다."""
        self._active_message = str(candidate["message"])
        self._expire_at = frame_idx + self._hold_frames

    def update(self, frame_idx: int) -> str:
        """현재 프레임 기준 활성 메시지를 반환하고 만료 시 초기화한다."""
        if self._expire_at != -1 and frame_idx >= self._expire_at:
            self._active_message = "측정 중입니다."
            self._expire_at = -1
        return self._active_message
