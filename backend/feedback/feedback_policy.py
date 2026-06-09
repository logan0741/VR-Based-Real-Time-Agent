class FeedbackPolicy:
    def __init__(self, hold_frames: int) -> None:
        """hold_frames 동안 피드백을 유지한다."""
        if hold_frames <= 0:
            raise ValueError(f"hold_frames must be positive: {hold_frames}")
        self._hold_frames = hold_frames
        self._active_message: str = "측정 중입니다."
        self._active_bad_joints: frozenset[int] = frozenset()
        self._expire_at: int = -1
        self._is_accumulating: bool = False
        self._score_buffer: dict[str, list[float]] = {}
        self._last_candidate_per_part: dict[str, dict[str, object]] = {}

    def update(
        self,
        frame_idx: int,
        candidate: dict[str, object] | None = None,
    ) -> tuple[str, frozenset[int]]:
        """Case 1: spike → 즉시 표시. Case 2: ok 누적 → 만료 시 최악 부위 표시."""
        if self._expire_at != -1 and frame_idx >= self._expire_at:
            if self._is_accumulating:
                self._expire_at = -1
                self._is_accumulating = False
                if self._score_buffer:
                    worst = max(
                        self._score_buffer,
                        key=lambda p: sum(self._score_buffer[p]) / len(self._score_buffer[p]),
                    )
                    worst_cand = self._last_candidate_per_part[worst]
                    self._active_message = str(worst_cand["message"])
                    self._active_bad_joints = worst_cand.get("bad_joints", frozenset())  # type: ignore[assignment]
                    self._score_buffer.clear()
                    self._last_candidate_per_part.clear()
                    self._expire_at = frame_idx + self._hold_frames
                    return self._active_message, self._active_bad_joints
                self._active_message = "측정 중입니다."
                self._active_bad_joints = frozenset()
            else:
                self._active_message = "측정 중입니다."
                self._active_bad_joints = frozenset()
                self._expire_at = -1

        if self._expire_at != -1 and not self._is_accumulating:
            return self._active_message, self._active_bad_joints

        if candidate is None:
            return self._active_message, self._active_bad_joints

        body_part = str(candidate.get("body_part", "pending"))

        if body_part not in {"pending", "ok"}:
            self._active_message = str(candidate["message"])
            self._active_bad_joints = candidate.get("bad_joints", frozenset())  # type: ignore[assignment]
            self._score_buffer.clear()
            self._last_candidate_per_part.clear()
            self._expire_at = frame_idx + self._hold_frames
            self._is_accumulating = False
            return self._active_message, self._active_bad_joints

        if body_part == "ok":
            all_candidates: dict[str, dict[str, object]] = candidate.get("all_candidates", {})  # type: ignore[assignment]
            for part_name, part_cand in all_candidates.items():
                self._score_buffer.setdefault(part_name, []).append(float(part_cand.get("severity", 0.0)))
                self._last_candidate_per_part[part_name] = part_cand
            if self._expire_at == -1:
                self._expire_at = frame_idx + self._hold_frames
                self._is_accumulating = True

        return self._active_message, self._active_bad_joints
