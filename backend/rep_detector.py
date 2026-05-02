"""정규화된 관절 시퀀스에서 운동 1회 구간을 감지한다."""

from enum import Enum, auto

import numpy as np

from backend.utils.keypoints import LEFT_KNEE, RIGHT_KNEE

SUPPORTED_DETECTOR_TYPES: frozenset[str] = frozenset({"squat"})
SUPPORTED_NORMALIZER_TYPES: frozenset[str] = frozenset({"front", "side_left", "side_right"})


class _RepState(Enum):
    WAIT_VALLEY = auto()
    WAIT_PEAK = auto()


class RepDetector:
    """종목별 감지 방법으로 운동 1회 구간 목록을 반환하는 클래스."""

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

    def detect(self, sequence: np.ndarray) -> list[tuple[int, int]]:
        """정규화된 관절 시퀀스에서 운동 1회 구간 목록을 반환한다. shape=(M,17,3), dtype=float32."""
        if sequence.shape[0] < self._slope_window + 1:
            raise ValueError(
                f"시퀀스 길이({sequence.shape[0]})가 slope_window({self._slope_window})보다 너무 짧습니다."
            )
        if self._type == "squat":
            return self._detect_squat(sequence)
        raise ValueError(f"지원하지 않는 rep_detector_type: {self._type!r}")

    def _detect_squat(self, sequence: np.ndarray) -> list[tuple[int, int]]:
        """스쿼트 1회 구간을 감지한다. shape=(M,17,3), dtype=float32."""
        signal = self._extract_knee_signal(sequence)
        slopes = self._compute_slopes(signal)
        return self._run_state_machine(slopes)

    def _extract_knee_signal(self, sequence: np.ndarray) -> np.ndarray:
        """normalizer_type에 따라 무릎 y좌표 시퀀스를 추출한다. shape=(M,), dtype=float32."""
        if self._normalizer_type == "side_left":
            return sequence[:, LEFT_KNEE, 0].astype(np.float32)
        if self._normalizer_type == "side_right":
            return sequence[:, RIGHT_KNEE, 0].astype(np.float32)
        return ((sequence[:, LEFT_KNEE, 0] + sequence[:, RIGHT_KNEE, 0]) / 2.0).astype(np.float32)

    def _compute_slopes(self, signal: np.ndarray) -> np.ndarray:
        """n프레임 윈도우 평균 기울기를 계산한다. shape=(M,), dtype=float32."""
        diffs = np.diff(signal, prepend=signal[0])
        M = len(signal)
        slopes = np.zeros(M, dtype=np.float32)
        for i in range(M):
            start = max(0, i - self._slope_window + 1)
            slopes[i] = float(np.mean(diffs[start : i + 1]))
        return slopes

    def _run_state_machine(self, slopes: np.ndarray) -> list[tuple[int, int]]:
        """기울기 부호 전환으로 valley·peak를 감지하고 rep 구간 목록을 반환한다."""
        reps: list[tuple[int, int]] = []
        state = _RepState.WAIT_VALLEY
        rep_start: int = 0

        for i in range(1, len(slopes)):
            prev = slopes[i - 1]
            curr = slopes[i]

            if state == _RepState.WAIT_VALLEY and prev < 0 and curr > 0:
                state = _RepState.WAIT_PEAK

            elif state == _RepState.WAIT_PEAK and prev > 0 and curr < 0:
                reps.append((rep_start, i))
                rep_start = i
                state = _RepState.WAIT_VALLEY

        if state == _RepState.WAIT_PEAK:
            reps.append((rep_start, len(slopes) - 1))

        return [(s, e) for s, e in reps if e - s >= self._min_rep_frames]
