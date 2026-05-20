_SYSTEM_PARTS: frozenset[str] = frozenset({"pending", "ok"})


class FeedbackPolicy:
    def __init__(self, update_interval: int = 48) -> None:
        """update_interval 프레임마다 severity 평균 기반으로 피드백 메시지를 교체한다."""
        if update_interval <= 0:
            raise ValueError(f"update_interval must be positive: {update_interval}")
        self._update_interval = update_interval
        self._severity_buffer: dict[str, list[float]] = {}
        self._last_candidate_per_part: dict[str, dict[str, object]] = {}
        self._active_message: str = "측정 중입니다."

    def update(self, frame_idx: int, candidate: dict[str, object] | None) -> str:
        """frame_idx가 update_interval 배수일 때 severity 평균이 가장 높은 부위의 메시지로 교체한다."""
        if candidate is not None:
            body_part = str(candidate["body_part"])
            if body_part not in _SYSTEM_PARTS:
                self._severity_buffer.setdefault(body_part, []).append(
                    float(candidate["severity"])
                )
                self._last_candidate_per_part[body_part] = candidate

        if frame_idx % self._update_interval != 0:
            return self._active_message

        if self._severity_buffer:
            best_part = max(
                self._severity_buffer,
                key=lambda p: sum(self._severity_buffer[p]) / len(self._severity_buffer[p]),
            )
            self._active_message = str(self._last_candidate_per_part[best_part]["message"])
        elif candidate is not None:
            self._active_message = str(candidate["message"])

        self._severity_buffer.clear()
        self._last_candidate_per_part.clear()
        return self._active_message
