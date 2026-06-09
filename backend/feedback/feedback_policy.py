class FeedbackPolicy:
    def __init__(self, hold_frames: int) -> None:
        """hold_frames 동안 피드백 메시지와 bad_joints를 유지한다."""
        if hold_frames <= 0:
            raise ValueError(f"hold_frames must be positive: {hold_frames}")
        self._hold_frames = hold_frames
        self._active_message: str = "측정 중입니다."
        self._active_bad_joints: frozenset[int] = frozenset()
        self._expire_at: int = -1

    def update(
        self,
        frame_idx: int,
        candidate: dict[str, object] | None = None,
    ) -> tuple[str, frozenset[int]]:
        """hold 중에는 새 candidate를 무시하고, 만료 후 bad 상태만 갱신한다."""
        if self._expire_at != -1:
            if frame_idx < self._expire_at:
                return self._active_message, self._active_bad_joints
            self._active_message = "측정 중입니다."
            self._active_bad_joints = frozenset()
            self._expire_at = -1

        if candidate is not None:
            body_part = str(candidate.get("body_part", "pending"))
            if body_part not in {"pending", "ok"}:
                self._active_message = str(candidate["message"])
                self._active_bad_joints = candidate.get("bad_joints", frozenset())  # type: ignore[assignment]
                self._expire_at = frame_idx + self._hold_frames

        return self._active_message, self._active_bad_joints
