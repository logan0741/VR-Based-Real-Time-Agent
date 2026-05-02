"""DTW 거리 행렬과 Rep 구간으로 실시간 점수 및 회차별 점수를 계산한다."""

import numpy as np

PERFECT_SCORE: int = 100
MIN_SCORE: int = 0


class ScoreEngine:
    """프레임별 관절 거리를 가중 평균하여 실시간·회차별 점수를 산출하는 클래스."""

    def __init__(
        self,
        weights: list[float],
        max_distance: float,
        n_frames: int,
    ) -> None:
        """관절 가중치, 최대 거리 기준, 실시간 점수 산출 프레임 수를 설정한다."""
        if not weights:
            raise ValueError("weights가 비어 있습니다.")
        if max_distance <= 0:
            raise ValueError(f"max_distance는 0보다 커야 합니다: {max_distance}")
        if n_frames <= 0:
            raise ValueError(f"n_frames는 0보다 커야 합니다: {n_frames}")

        weight_sum = sum(weights)
        self._weights: np.ndarray = np.array(weights, dtype=np.float32) / weight_sum
        self._max_distance: float = max_distance
        self._n_frames: int = n_frames
        self._rep_scores: list[int] = []
        self._scored_count: int = 0

    def update(
        self,
        dist_matrix: np.ndarray,
        reps: list[tuple[int, int]],
    ) -> tuple[int, list[int]]:
        """dist_matrix와 rep 구간으로 실시간 점수와 누적 회차 점수 목록을 반환한다. dist_matrix shape=(M,K), dtype=float32."""
        if dist_matrix.ndim != 2:
            raise ValueError(f"dist_matrix는 2차원이어야 합니다: ndim={dist_matrix.ndim}")
        if dist_matrix.shape[1] != len(self._weights):
            raise ValueError(
                f"dist_matrix 열 수({dist_matrix.shape[1]})와 weights 길이({len(self._weights)})가 다릅니다."
            )

        for start, end in reps[self._scored_count:]:
            self._rep_scores.append(self._score_rep(dist_matrix, start, end))
        self._scored_count = len(reps)

        return self._realtime_score(dist_matrix), list(self._rep_scores)

    def _realtime_score(self, dist_matrix: np.ndarray) -> int:
        """최근 n_frames 구간의 가중 평균 거리를 선형 변환하여 실시간 점수를 반환한다. dist_matrix shape=(M,K), dtype=float32."""
        window: np.ndarray = dist_matrix[-self._n_frames:]
        return self._to_score(float(np.mean(window @ self._weights)))

    def _score_rep(self, dist_matrix: np.ndarray, start: int, end: int) -> int:
        """rep 구간 전체 프레임의 가중 평균 거리를 선형 변환하여 1회 점수를 반환한다. dist_matrix shape=(M,K), dtype=float32."""
        segment: np.ndarray = dist_matrix[start:end]
        if segment.shape[0] == 0:
            raise ValueError(f"rep 구간이 비어 있습니다: start={start}, end={end}")
        return self._to_score(float(np.mean(segment @ self._weights)))

    def _to_score(self, distance: float) -> int:
        """거리를 0~100 점수로 선형 변환한다."""
        return max(MIN_SCORE, round(PERFECT_SCORE * (1.0 - distance / self._max_distance)))
