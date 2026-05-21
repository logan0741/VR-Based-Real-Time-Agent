"""정규화된 관절 프레임을 1개씩 입력받아 운동 1회 구간을 증분으로 감지한다."""

from collections import deque
from enum import Enum, auto

import numpy as np

from backend.utils.keypoints import LEFT_KNEE, RIGHT_KNEE

SUPPORTED_DETECTOR_TYPES: frozenset[str] = frozenset({"squat"})
SUPPORTED_NORMALIZER_TYPES: frozenset[str] = frozenset({"front", "side_left", "side_right"})


class _RepState(Enum):
    WAIT_VALLEY = auto()
    WAIT_PEAK = auto()


class RepDetector:
    """종목별 감지 방법으로 운동 1회 구간 목록을 증분으로 반환하는 클래스."""

    def __init__(
        self,
        rep_detector_type: str,
        normalizer_type: str,
        slope_window: int,
        min_rep_frames: int,
    ) -> None:
        """감지 방법, 정규화 타입, 기울기 윈도우 크기, 최소 rep 길이를 설정한다."""
        if rep_detector_type not in SUPPORTED_DETECTOR_TYPES:
            raise ValueError(f"지원하지 않는 rep_detector_type: {rep_detector_type!r}")
        if normalizer_type not in SUPPORTED_NORMALIZER_TYPES:
            raise ValueError(f"지원하지 않는 normalizer_type: {normalizer_type!r}")

        self._type = rep_detector_type
        self._normalizer_type = normalizer_type
        self._slope_window = slope_window
        self._min_rep_frames = min_rep_frames

        self._state: _RepState = _RepState.WAIT_VALLEY
        self._rep_start: int = 0
        self._reps: list[tuple[int, int]] = []
        self._frame_idx: int = 0
        self._prev_signal: float = 0.0
        self._diff_buffer: deque[float] = deque(maxlen=slope_window)
        self._prev_slope: float = 0.0

    def update(self, norm_frame: np.ndarray) -> list[tuple[int, int]]:
        """정규화된 관절 프레임 1개를 입력받아 누적 rep 구간 목록을 반환한다. norm_frame shape=(17,3), dtype=float32."""
        signal = self._extract_knee_signal(norm_frame)
        diff = signal - self._prev_signal
        self._prev_signal = signal
        self._diff_buffer.append(diff)

        curr_slope = float(np.mean(self._diff_buffer))
        self._step(curr_slope)
        self._prev_slope = curr_slope
        self._frame_idx += 1

        return self._valid_reps()

    def finalize(self) -> list[tuple[int, int]]:
        """시퀀스 종료 시 WAIT_PEAK 상태의 미완료 rep을 마감하고 누적 rep 목록을 반환한다."""
        if self._state == _RepState.WAIT_PEAK:
            self._reps.append((self._rep_start, self._frame_idx - 1))
            self._state = _RepState.WAIT_VALLEY
        return self._valid_reps()

    def _extract_knee_signal(self, norm_frame: np.ndarray) -> float:
        """normalizer_type에 따라 단일 프레임에서 무릎 y좌표를 추출한다. norm_frame shape=(17,3), dtype=float32."""
        if self._normalizer_type == "side_left":
            return float(norm_frame[LEFT_KNEE, 0])
        if self._normalizer_type == "side_right":
            return float(norm_frame[RIGHT_KNEE, 0])
        return float((norm_frame[LEFT_KNEE, 0] + norm_frame[RIGHT_KNEE, 0]) / 2.0)

    def _step(self, curr_slope: float) -> None:
        """기울기 부호 전환으로 valley·peak를 감지하고 내부 상태를 갱신한다."""
        prev = self._prev_slope
        if self._state == _RepState.WAIT_VALLEY and prev < 0 and curr_slope > 0:
            self._state = _RepState.WAIT_PEAK
        elif self._state == _RepState.WAIT_PEAK and prev > 0 and curr_slope < 0:
            self._reps.append((self._rep_start, self._frame_idx))
            self._rep_start = self._frame_idx
            self._state = _RepState.WAIT_VALLEY

    def _valid_reps(self) -> list[tuple[int, int]]:
        """min_rep_frames 이상인 rep 구간만 반환한다."""
        return [(s, e) for s, e in self._reps if e - s >= self._min_rep_frames]
