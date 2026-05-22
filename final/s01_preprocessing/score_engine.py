"""DTW 거리 행렬과 Rep 구간으로 실시간 점수 및 회차별 점수를 계산한다."""
from __future__ import annotations

import numpy as np

PERFECT_SCORE: int = 100
MIN_SCORE: int = 0

# ── 정면 촬영 기하학적 스코어러 ──────────────────────────────────────────────

_GEO_FEEDBACK: dict[str, str] = {
    "ok":              "자세가 안정적입니다. 계속 유지하세요!",
    "knee_caving":     "무릎이 안쪽으로 모이고 있어요. 발 끝 방향으로 밀어내세요.",
    "knee_asymmetry":  "좌우 무릎 균형이 맞지 않아요. 좌우를 동일하게 맞춰주세요.",
    "trunk_lean":      "상체가 옆으로 기울고 있어요. 정면을 바라보고 바르게 세우세요.",
}


class GeometricScorer:
    """DTW 없이 관절 좌표만으로 자세를 평가하는 기하학적 스코어러.

    정면 촬영처럼 전문가 시퀀스와 뷰 방향이 다를 때 사용한다.
    """

    @staticmethod
    def _angle_deg(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
        """점 a-b-c 에서 b의 관절 각도(도)."""
        ba = a - b
        bc = c - b
        cos_val = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-8)
        return float(np.degrees(np.arccos(np.clip(cos_val, -1.0, 1.0))))

    @classmethod
    def squat_front(cls, kpts: np.ndarray) -> tuple[int, str]:
        """정면 스쿼트 기하학적 평가. kpts: (17,3) [y,x,conf] normalized 0-1.

        Returns
        -------
        score : 0-100
        feedback_key : _GEO_FEEDBACK 키
        """
        from .utils.keypoints import (
            LEFT_HIP, RIGHT_HIP, LEFT_KNEE, RIGHT_KNEE,
            LEFT_ANKLE, RIGHT_ANKLE, LEFT_SHOULDER, RIGHT_SHOULDER,
        )

        lh = kpts[LEFT_HIP, :2]
        rh = kpts[RIGHT_HIP, :2]
        lk = kpts[LEFT_KNEE, :2]
        rk = kpts[RIGHT_KNEE, :2]
        la = kpts[LEFT_ANKLE, :2]
        ra = kpts[RIGHT_ANKLE, :2]
        ls = kpts[LEFT_SHOULDER, :2]
        rs = kpts[RIGHT_SHOULDER, :2]

        # ── 좌우 무릎 각도 (대칭성) ──
        l_ang = cls._angle_deg(lh, lk, la)
        r_ang = cls._angle_deg(rh, rk, ra)
        sym_score = max(0.0, 1.0 - abs(l_ang - r_ang) / 30.0)

        # ── 무릎-발목 정렬 (정면에서 무릎이 발 끝 위에 있어야 함) ──
        ankle_width = abs(la[1] - ra[1]) + 1e-6
        l_drift = abs(lk[1] - la[1])
        r_drift = abs(rk[1] - ra[1])
        knee_track_score = max(0.0, 1.0 - (l_drift + r_drift) / ankle_width)

        # ── 상체 좌우 기울기 ──
        hip_w = abs(lh[1] - rh[1]) + 1e-6
        trunk_lean = abs((ls[1] + rs[1]) / 2 - (lh[1] + rh[1]) / 2) / hip_w
        trunk_score = max(0.0, 1.0 - trunk_lean * 2.5)

        raw = sym_score * 0.35 + knee_track_score * 0.40 + trunk_score * 0.25
        score = int(np.clip(raw * 100, 0, 100))

        # ── 피드백 키 결정 (가장 나쁜 항목 우선) ──
        if knee_track_score < 0.5:
            key = "knee_caving"
        elif sym_score < 0.6:
            key = "knee_asymmetry"
        elif trunk_score < 0.5:
            key = "trunk_lean"
        else:
            key = "ok"

        return score, key

    @staticmethod
    def geo_feedback_message(key: str) -> str:
        return _GEO_FEEDBACK.get(key, "측정 중입니다.")


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

    def update(
        self,
        window_dist_matrix: np.ndarray,
        new_rep_matrices: list[np.ndarray],
    ) -> tuple[int, list[int]]:
        """슬라이딩 윈도우 dist_matrix와 새 회차 dist_matrix 목록으로 실시간 점수와 누적 회차 점수 목록을 반환한다. window_dist_matrix shape=(M,K), dtype=float32."""
        if window_dist_matrix.ndim != 2:
            raise ValueError(f"window_dist_matrix는 2차원이어야 합니다: ndim={window_dist_matrix.ndim}")
        if window_dist_matrix.shape[1] != len(self._weights):
            raise ValueError(
                f"window_dist_matrix 열 수({window_dist_matrix.shape[1]})와 weights 길이({len(self._weights)})가 다릅니다."
            )

        for rep_dm in new_rep_matrices:
            self._rep_scores.append(self._score_rep(rep_dm))

        return self._realtime_score(window_dist_matrix), list(self._rep_scores)

    def _realtime_score(self, dist_matrix: np.ndarray) -> int:
        """최근 n_frames 구간의 가중 평균 거리를 선형 변환하여 실시간 점수를 반환한다. dist_matrix shape=(M,K), dtype=float32."""
        window: np.ndarray = dist_matrix[-self._n_frames:]
        return self._to_score(float(np.mean(window @ self._weights)))

    def _score_rep(self, rep_dist_matrix: np.ndarray) -> int:
        """rep 구간 dist_matrix의 가중 평균 거리를 선형 변환하여 1회 점수를 반환한다. rep_dist_matrix shape=(M,K), dtype=float32."""
        if rep_dist_matrix.shape[0] == 0:
            raise ValueError("rep dist_matrix가 비어 있습니다.")
        return self._to_score(float(np.mean(rep_dist_matrix @ self._weights)))

    def _to_score(self, distance: float) -> int:
        """거리를 0~100 점수로 선형 변환한다."""
        return max(MIN_SCORE, round(PERFECT_SCORE * (1.0 - distance / self._max_distance)))
