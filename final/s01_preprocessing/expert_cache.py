"""전문가 영상의 정규화된 관절 시퀀스를 앱 시작 시 1회 계산하여 메모리에 보관한다."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import cv2
import numpy as np

try:
    from .pose_estimator import PoseEstimator
except ImportError:
    PoseEstimator = None  # TensorFlow 미설치 시 npy 경로로만 사용 가능

from .pose_normalizer import PoseNormalizer

INITIAL_SAMPLE_OFFSET: float = 0.0


def _npy_path_for(video_path: str) -> Path:
    """비디오 경로에서 .npy 캐시 경로를 계산한다 (확장자만 교체)."""
    return Path(video_path).with_suffix(".npy")


class ExpertPoseCache:
    """전문가 영상 전체를 처리하여 정규화 시퀀스를 캐시하는 클래스.

    빌드 우선순위:
      1. 비디오 경로 옆 .npy 캐시 파일이 있으면 TF 없이 즉시 로드
      2. estimator가 주입된 경우 영상에서 직접 추출 후 .npy 저장
      3. 둘 다 없으면 RuntimeError
    """

    def __init__(
        self,
        video_path: str,
        target_fps: int,
        normalizer_type: str,
        norm_buffer_size: int,
        estimator: Optional[object] = None,
    ) -> None:
        """영상 설정을 저장한다. estimator는 TF 환경에서만 필요하다."""
        self._video_path = video_path
        self._target_fps = target_fps
        self._normalizer_type = normalizer_type
        self._norm_buffer_size = norm_buffer_size
        self._estimator = estimator
        self._sequence: np.ndarray | None = None
        self._raw_sequence: np.ndarray | None = None
        self._frames: list[np.ndarray] | None = None

    def build(self) -> None:
        """정규화 시퀀스를 생성한다. 이미 빌드된 경우 재계산하지 않는다."""
        if self._sequence is not None:
            return

        npy_path = _npy_path_for(self._video_path)
        if npy_path.exists():
            self._load_from_npy(npy_path)
            return

        if self._estimator is None:
            raise RuntimeError(
                f".npy 캐시 파일이 없고 PoseEstimator도 없습니다.\n"
                f"  캐시 위치: {npy_path}\n"
                f"  해결: final/tools/build_expert_cache.py 를 TF 환경에서 실행하세요."
            )

        self._build_from_video()
        self._save_npy(npy_path)

    def _load_from_npy(self, npy_path: Path) -> None:
        """사전 계산된 .npy 파일에서 정규화 시퀀스를 로드한다."""
        data: dict = np.load(str(npy_path), allow_pickle=True).item()
        self._sequence = data["sequence"].astype(np.float32)
        self._raw_sequence = data.get("raw_sequence", np.zeros_like(self._sequence))
        self._frames = []
        print(f"[ExpertPoseCache] .npy 로드: {npy_path.name} ({self._sequence.shape[0]}프레임)")

    def _build_from_video(self) -> None:
        """PoseEstimator를 사용해 영상에서 직접 정규화 시퀀스를 생성한다."""
        cap = cv2.VideoCapture(self._video_path)
        if not cap.isOpened():
            raise FileNotFoundError(f"전문가 영상 파일을 열 수 없습니다: {self._video_path!r}")

        original_fps: float = cap.get(cv2.CAP_PROP_FPS)
        print(f"[ExpertPoseCache] 영상 처리 시작: fps {original_fps:.2f} → {self._target_fps}")

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
        print(f"[ExpertPoseCache] 추출 완료: {self._sequence.shape[0]}프레임")

    def _save_npy(self, npy_path: Path) -> None:
        """생성된 시퀀스를 .npy 파일로 저장해 다음 실행부터 TF 없이 로드 가능하게 한다."""
        np.save(str(npy_path), {
            "sequence": self._sequence,
            "raw_sequence": self._raw_sequence,
        })
        print(f"[ExpertPoseCache] .npy 저장: {npy_path}")

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
