"""04 DTWComparator 테스트."""

import numpy as np

from backend.config import EXERCISES
from backend.dtw_comparator import DTWComparator
from backend.expert_cache import ExpertPoseCache
from backend.pose_estimator import PoseEstimator

cfg = EXERCISES["squat"]
K = len(cfg["keypoints_used"])

print("=" * 55)
print("04 DTWComparator 테스트")
print("=" * 55)

estimator = PoseEstimator()
estimator.load()

cache = ExpertPoseCache(
    estimator=estimator,
    video_path=cfg["video_path"],
    target_fps=cfg["target_fps"],
    normalizer_type=cfg["normalizer_type"],
    norm_buffer_size=cfg["norm_buffer_size"],
)
cache.build()
expert_seq = cache.sequence  # (N, 17, 3)

comparator = DTWComparator(cfg["keypoints_used"])

# ── 케이스 1: shape·dtype 검증 ────────────────────────────────────────────────
user_seq = expert_seq[: cfg["n_frames"]]  # (n_frames, 17, 3)
distances = comparator.compare(user_seq, expert_seq)

assert distances.shape == (cfg["n_frames"], K), f"shape 오류: {distances.shape}"
assert distances.dtype == np.float32, f"dtype 오류: {distances.dtype}"
assert distances.min() >= 0.0, f"음수 거리 발생: {distances.min():.6f}"
print(f"출력 shape: {distances.shape}  dtype: {distances.dtype}")

# ── 케이스 2: 동일 시퀀스(전체) 거리 0 수렴 검증 ─────────────────────────────
dist_self = comparator.compare(expert_seq, expert_seq)
mean_self = float(dist_self.mean())
print(f"동일 시퀀스 평균 거리: {mean_self:.8f}  (0이어야 함)")
assert mean_self < 1e-5, f"동일 시퀀스 거리가 0이 아님: {mean_self:.8f}"

# ── 케이스 3: M=1 경계값 ─────────────────────────────────────────────────────
single_frame = expert_seq[:1]  # (1, 17, 3)
dist_single = comparator.compare(single_frame, expert_seq)
assert dist_single.shape == (1, K), f"단일 프레임 shape 오류: {dist_single.shape}"
print(f"단일 프레임 shape: {dist_single.shape}")

# ── 케이스 4: 빈 시퀀스 예외 검증 ────────────────────────────────────────────
try:
    comparator.compare(np.zeros((0, 17, 3), dtype=np.float32), expert_seq)
    assert False, "ValueError가 발생해야 합니다."
except ValueError as e:
    print(f"빈 시퀀스 예외 정상 발생: {e}")

print(">> DTWComparator 테스트 통과")
