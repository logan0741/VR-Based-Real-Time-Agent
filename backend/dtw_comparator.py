"""사용자와 전문가 정규화 시퀀스를 DTW로 비교하여 프레임별 관절 거리를 계산한다."""

import numpy as np
from dtaidistance import dtw_ndim

YX_DIM: int = 2


class DTWComparator:
    """관절별 개별 DTW로 사용자·전문가 포즈 시퀀스를 비교하는 클래스."""

    def __init__(self, keypoints_used: list[int]) -> None:
        """비교에 사용할 관절 인덱스 목록을 설정한다."""
        self._keypoints_used = keypoints_used

    def compare(
        self, user_seq: np.ndarray, expert_seq: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        """DTW 워핑 경로 기준 프레임별 관절 거리와 매칭된 전문가 프레임 인덱스를 반환한다. user_seq shape=(M,17,3), 출력 dist shape=(M,K), best_expert_idx shape=(M,), dtype=float32/int32."""
        if user_seq.shape[0] == 0:
            raise ValueError("사용자 시퀀스가 비어 있습니다.")
        if expert_seq.shape[0] == 0:
            raise ValueError("전문가 시퀀스가 비어 있습니다.")

        user_kp: np.ndarray = user_seq[:, self._keypoints_used, :YX_DIM]    # (M, K, 2)
        expert_kp: np.ndarray = expert_seq[:, self._keypoints_used, :YX_DIM]  # (N, K, 2)

        M: int = user_kp.shape[0]
        K: int = len(self._keypoints_used)
        result = np.zeros((M, K), dtype=np.float32)
        expert_idx_accum: list[list[int]] = [[] for _ in range(M)]

        for k in range(K):
            path = dtw_ndim.warping_path(user_kp[:, k, :], expert_kp[:, k, :])
            frame_dists: list[list[float]] = [[] for _ in range(M)]

            for user_idx, expert_idx in path:
                dist = float(np.linalg.norm(user_kp[user_idx, k] - expert_kp[expert_idx, k]))
                frame_dists[user_idx].append(dist)
                expert_idx_accum[user_idx].append(expert_idx)

            for m in range(M):
                if not frame_dists[m]:
                    raise RuntimeError(f"프레임 {m} 관절 {k}에 DTW 경로 매핑이 없습니다.")
                result[m, k] = float(np.mean(frame_dists[m]))

        best_expert_indices = np.array(
            [int(round(float(np.mean(expert_idx_accum[m])))) for m in range(M)],
            dtype=np.int32,
        )
        return result, best_expert_indices
