"""관절 좌표 정규화: 체형 차이를 제거하여 비교 가능한 좌표계로 변환."""

from collections import deque

import numpy as np

from backend.utils.keypoints import (
    LEFT_HIP, LEFT_SHOULDER,
    RIGHT_HIP, RIGHT_SHOULDER,
)

SUPPORTED_TYPES: frozenset[str] = frozenset({"front", "side_left", "side_right"})
MIN_SCALE: float = 1e-6


class PoseNormalizer:
    """촬영 방향별 기준 관절을 이용해 체형 차이를 제거하는 정규화기."""

    def __init__(self, normalizer_type: str, buffer_size: int) -> None:
        """정규화 타입과 평활화 버퍼 크기를 설정한다."""
        if normalizer_type not in SUPPORTED_TYPES:
            raise ValueError(f"지원하지 않는 normalizer_type: {normalizer_type!r}")
        self._type = normalizer_type
        self._buffer: deque[tuple[float, float, float]] = deque(maxlen=buffer_size)

    def normalize(self, keypoints: np.ndarray) -> np.ndarray:
        """단일 프레임 관절 좌표를 정규화한다. shape=(17,3), dtype=float32, 각 행=[y,x,conf]."""
        origin_y, origin_x, scale = self._compute_reference(keypoints)
        self._buffer.append((origin_y, origin_x, scale))

        avg_origin_y = float(np.mean([b[0] for b in self._buffer]))
        avg_origin_x = float(np.mean([b[1] for b in self._buffer]))
        avg_scale = float(np.mean([b[2] for b in self._buffer]))

        if avg_scale < MIN_SCALE:
            raise ValueError("정규화 스케일이 0에 가깝습니다. 기준 관절을 감지할 수 없습니다.")

        result = keypoints.copy()
        result[:, 0] = (keypoints[:, 0] - avg_origin_y) / avg_scale
        result[:, 1] = (keypoints[:, 1] - avg_origin_x) / avg_scale
        return result.astype(np.float32)

    def reset(self) -> None:
        """버퍼를 초기화한다. 새 세션 시작 시 호출한다."""
        self._buffer.clear()

    def _compute_reference(self, keypoints: np.ndarray) -> tuple[float, float, float]:
        """현재 프레임의 원점(y, x)과 몸통 길이 스케일을 계산한다. shape=(17,3), dtype=float32."""
        if self._type == "front":
            hip_y = (keypoints[LEFT_HIP, 0] + keypoints[RIGHT_HIP, 0]) / 2.0
            hip_x = (keypoints[LEFT_HIP, 1] + keypoints[RIGHT_HIP, 1]) / 2.0
            shoulder_y = (keypoints[LEFT_SHOULDER, 0] + keypoints[RIGHT_SHOULDER, 0]) / 2.0
            shoulder_x = (keypoints[LEFT_SHOULDER, 1] + keypoints[RIGHT_SHOULDER, 1]) / 2.0
        elif self._type == "side_left":
            hip_y = keypoints[LEFT_HIP, 0]
            hip_x = keypoints[LEFT_HIP, 1]
            shoulder_y = keypoints[LEFT_SHOULDER, 0]
            shoulder_x = keypoints[LEFT_SHOULDER, 1]
        else:
            hip_y = keypoints[RIGHT_HIP, 0]
            hip_x = keypoints[RIGHT_HIP, 1]
            shoulder_y = keypoints[RIGHT_SHOULDER, 0]
            shoulder_x = keypoints[RIGHT_SHOULDER, 1]

        scale = float(np.sqrt((shoulder_y - hip_y) ** 2 + (shoulder_x - hip_x) ** 2))
        return hip_y, hip_x, scale
