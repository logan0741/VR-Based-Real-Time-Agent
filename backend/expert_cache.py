"""전문가 영상의 정규화된 관절 시퀀스를 앱 시작 시 1회 계산하여 메모리에 보관한다."""

import cv2
import numpy as np

from backend.pose_estimator import PoseEstimator
from backend.pose_normalizer import PoseNormalizer

INITIAL_SAMPLE_OFFSET: float = 0.0


class ExpertPoseCache:
    """전문가 영상 전체를 처리하여 정규화 시퀀스를 캐시하는 클래스."""

    def __init__(
        self,
        estimator: PoseEstimator,
        video_path: str,
        target_fps: int,
        normalizer_type: str,
        norm_buffer_size: int,
    ) -> None:
        """외부에서 주입된 PoseEstimator와 영상 설정을 저장한다."""
        self._estimator = estimator
        self._video_path = video_path
        self._target_fps = target_fps
        self._normalizer_type = normalizer_type
        self._norm_buffer_size = norm_buffer_size
        self._sequence: np.ndarray | None = None
        self._raw_sequence: np.ndarray | None = None
        self._frames: list[np.ndarray] | None = None

    def build(self) -> None:
        """전문가 영상을 처리하여 정규화 시퀀스를 생성한다. 이미 빌드된 경우 재계산하지 않는다."""
        if self._sequence is not None:
            return

        cap = cv2.VideoCapture(self._video_path)
        if not cap.isOpened():
            raise FileNotFoundError(f"전문가 영상 파일을 열 수 없습니다: {self._video_path!r}")

        original_fps: float = cap.get(cv2.CAP_PROP_FPS)
        print(f"[ExpertPoseCache] 원본 영상 fps: {original_fps:.2f} → 샘플링 fps: {self._target_fps}")

        normalizer = PoseNormalizer(self._normalizer_type, self._norm_buffer_size)
        sample_interval: float = original_fps / self._target_fps
        norm_frames: list[np.ndarray] = []
        raw_frames: list[np.ndarray] = []
        video_frames: list[np.ndarray] = []
        next_sample: float = INITIAL_SAMPLE_OFFSET
        frame_idx: int = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx >= next_sample:
                keypoints = self._estimator.predict(frame)
                normalized = normalizer.normalize(keypoints)
                norm_frames.append(normalized)
                raw_frames.append(keypoints)
                video_frames.append(frame.copy())
                next_sample += sample_interval
            frame_idx += 1

        cap.release()

        if not norm_frames:
            raise RuntimeError(f"전문가 영상에서 유효한 프레임을 추출하지 못했습니다: {self._video_path!r}")

        self._sequence = np.stack(norm_frames, axis=0).astype(np.float32)
        self._raw_sequence = np.stack(raw_frames, axis=0).astype(np.float32)
        self._frames = video_frames
        print(f"[ExpertPoseCache] 캐시 완료: {self._sequence.shape[0]}프레임 (shape={self._sequence.shape})")

    @property
    def sequence(self) -> np.ndarray:
        """캐시된 정규화 시퀀스를 반환한다. shape=(N,17,3), dtype=float32."""
        if self._sequence is None:
            raise RuntimeError("sequence 접근 전 build()를 먼저 호출하세요.")
        return self._sequence

    @property
    def raw_sequence(self) -> np.ndarray:
        """캐시된 원본 keypoints 시퀀스를 반환한다. shape=(N,17,3), dtype=float32."""
        if self._raw_sequence is None:
            raise RuntimeError("raw_sequence 접근 전 build()를 먼저 호출하세요.")
        return self._raw_sequence

    @property
    def frames(self) -> list[np.ndarray]:
        """캐시된 전문가 영상 프레임 목록을 반환한다. 각 shape=(H,W,3), dtype=uint8."""
        if self._frames is None:
            raise RuntimeError("frames 접근 전 build()를 먼저 호출하세요.")
        return self._frames
