"""01~03 단계 통합 테스트."""

import cv2
import numpy as np

from backend.config import EXERCISES
from backend.expert_cache import ExpertPoseCache
from backend.pose_estimator import PoseEstimator
from backend.pose_normalizer import PoseNormalizer
from backend.utils.keypoints import LEFT_HIP, LEFT_SHOULDER

cfg = EXERCISES["squat"]

# ── 01 PoseEstimator ──────────────────────────────────────────────────────────
print("=" * 55)
print("01 PoseEstimator 테스트")
print("=" * 55)

cap = cv2.VideoCapture(cfg["video_path"])
if not cap.isOpened():
    raise FileNotFoundError(f"영상 파일 없음: {cfg['video_path']!r}")
ret, frame = cap.read()
cap.release()
assert ret, "첫 프레임 읽기 실패"

estimator = PoseEstimator()
estimator.load()
keypoints = estimator.predict(frame)

assert keypoints.shape == (17, 3), f"shape 오류: {keypoints.shape}"
assert keypoints.dtype == np.float32, f"dtype 오류: {keypoints.dtype}"
assert keypoints[:, 2].min() >= 0.0 and keypoints[:, 2].max() <= 1.0, (
    f"confidence 범위 오류: {keypoints[:, 2].min():.3f} ~ {keypoints[:, 2].max():.3f}"
)
print(f"shape: {keypoints.shape}  dtype: {keypoints.dtype}")
print(f"confidence 범위: {keypoints[:, 2].min():.3f} ~ {keypoints[:, 2].max():.3f}")
print(">> PoseEstimator 테스트 통과\n")

# ── 02 PoseNormalizer ─────────────────────────────────────────────────────────
print("=" * 55)
print("02 PoseNormalizer 테스트")
print("=" * 55)

normalizer = PoseNormalizer(cfg["normalizer_type"], cfg["norm_buffer_size"])
normalized = normalizer.normalize(keypoints)

assert normalized.shape == (17, 3), f"shape 오류: {normalized.shape}"
assert normalized.dtype == np.float32, f"dtype 오류: {normalized.dtype}"
assert normalized[:, 2].tolist() == keypoints[:, 2].tolist(), "confidence 값이 변경됨"

hip_y = float(normalized[LEFT_HIP, 0])
hip_x = float(normalized[LEFT_HIP, 1])
torso_len = float(np.sqrt(
    (normalized[LEFT_SHOULDER, 0] - normalized[LEFT_HIP, 0]) ** 2 +
    (normalized[LEFT_SHOULDER, 1] - normalized[LEFT_HIP, 1]) ** 2
))

assert abs(hip_y) < 1e-5, f"힙 y 원점 오류: {hip_y:.8f}"
assert abs(hip_x) < 1e-5, f"힙 x 원점 오류: {hip_x:.8f}"
assert abs(torso_len - 1.0) < 1e-5, f"몸통 길이 오류: {torso_len:.8f}"
print(f"힙 위치  y={hip_y:.8f}  x={hip_x:.8f}")
print(f"몸통 길이: {torso_len:.8f}")
print(">> PoseNormalizer 테스트 통과\n")

# ── 03 ExpertPoseCache ────────────────────────────────────────────────────────
print("=" * 55)
print("03 ExpertPoseCache 테스트")
print("=" * 55)

cache = ExpertPoseCache(
    estimator=estimator,
    video_path=cfg["video_path"],
    target_fps=cfg["target_fps"],
    normalizer_type=cfg["normalizer_type"],
    norm_buffer_size=cfg["norm_buffer_size"],
)
cache.build()
cache.build()  # 가드 검증: 두 번째 호출은 재계산 없이 반환되어야 함

seq = cache.sequence
assert seq.ndim == 3, f"차원 오류: {seq.ndim}"
assert seq.shape[1] == 17 and seq.shape[2] == 3, f"shape 오류: {seq.shape}"
assert seq.dtype == np.float32, f"dtype 오류: {seq.dtype}"
assert seq.shape[0] >= 1, f"프레임 수 오류: {seq.shape[0]}"
print(f"시퀀스 shape: {seq.shape}")
print(">> ExpertPoseCache 테스트 통과")
