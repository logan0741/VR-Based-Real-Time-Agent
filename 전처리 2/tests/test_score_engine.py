"""06 ScoreEngine 테스트."""

import numpy as np

from backend.config import EXERCISES
from backend.dtw_comparator import DTWComparator
from backend.expert_cache import ExpertPoseCache
from backend.pose_estimator import PoseEstimator
from backend.rep_detector import RepDetector
from backend.score_engine import ScoreEngine

cfg = EXERCISES["squat"]

EXPERT_VIDEO = "assets/expert_videos/squat.mp4"
TEST_VIDEO   = "assets/test_videos/test_squat.mp4"

PRINT_INTERVAL: int = 10

print("=" * 55)
print("06 ScoreEngine 테스트")
print("=" * 55)

estimator = PoseEstimator()
estimator.load()


def build_sequence(video_path: str) -> np.ndarray:
    """지정 영상을 처리하여 정규화 시퀀스를 반환한다. shape=(N,17,3), dtype=float32."""
    cache = ExpertPoseCache(
        estimator=estimator,
        video_path=video_path,
        target_fps=cfg["target_fps"],
        normalizer_type=cfg["normalizer_type"],
        norm_buffer_size=cfg["norm_buffer_size"],
    )
    cache.build()
    return cache.sequence


print("\n[준비] 시퀀스 추출 중...")
expert_seq = build_sequence(EXPERT_VIDEO)
user_seq   = build_sequence(TEST_VIDEO)
print(f"  전문가 시퀀스: {expert_seq.shape[0]} 프레임  ({EXPERT_VIDEO})")
print(f"  사용자 시퀀스: {user_seq.shape[0]} 프레임  ({TEST_VIDEO})")

print("\n[준비] DTW 거리 행렬 계산 중...")
comparator = DTWComparator(keypoints_used=cfg["keypoints_used"])
dist_matrix = comparator.compare(user_seq, expert_seq)
print(f"  dist_matrix shape: {dist_matrix.shape}  (프레임 수 × 관절 수)")

print("\n[준비] Rep 구간 감지 중...")
detector = RepDetector(
    rep_detector_type=cfg["rep_detector_type"],
    normalizer_type=cfg["normalizer_type"],
    slope_window=cfg["rep_slope_window"],
    min_rep_frames=cfg["min_rep_frames"],
)
reps = detector.detect(user_seq)
print(f"  감지된 rep 수: {len(reps)}")
for i, (s, e) in enumerate(reps):
    print(f"    Rep {i + 1}: frame {s} ~ {e}  (길이 {e - s})")

engine = ScoreEngine(
    weights=cfg["weights"],
    max_distance=cfg["max_distance"],
    n_frames=cfg["n_frames"],
)

# ── 케이스 1: 프레임별 실시간 점수 추이 ──────────────────────────────────────
print("\n[케이스 1] 프레임별 실시간 점수 추이 (10프레임 간격)")
M = dist_matrix.shape[0]
rep_boundaries = {e: i + 1 for i, (s, e) in enumerate(reps)}
prev_rep_count = 0

for frame in range(1, M + 1):
    completed_reps = [(s, e) for s, e in reps if e <= frame]
    realtime, rep_scores = engine.update(dist_matrix[:frame], completed_reps)

    if frame % PRINT_INTERVAL == 0 or frame == M:
        print(f"  frame {frame:>4}: 실시간 점수 = {realtime:>3}")

    if len(rep_scores) > prev_rep_count:
        rep_num = len(rep_scores)
        print(f"  ★ Rep {rep_num} 완료  → 1회 점수 = {rep_scores[-1]}")
        prev_rep_count = len(rep_scores)

assert 0 <= realtime <= 100, f"실시간 점수 범위 초과: {realtime}"
print(">> 케이스 1 통과")

# ── 케이스 2: 회차별 점수 누적 확인 ──────────────────────────────────────────
print("\n[케이스 2] 최종 회차별 점수 목록")
_, final_rep_scores = engine.update(dist_matrix, reps)
print(f"  누적 rep 점수: {final_rep_scores}")
assert len(final_rep_scores) >= 1, f"회차 점수가 1개 이상이어야 함: {len(final_rep_scores)}개"
for score in final_rep_scores:
    assert 0 <= score <= 100, f"회차 점수 범위 초과: {score}"
print(">> 케이스 2 통과")

# ── 케이스 3: 빈 rep 구간 예외 ───────────────────────────────────────────────
print("\n[케이스 3] 빈 rep 구간 예외")
fresh_engine = ScoreEngine(
    weights=cfg["weights"],
    max_distance=cfg["max_distance"],
    n_frames=cfg["n_frames"],
)
try:
    fresh_engine.update(dist_matrix, [(5, 5)])
    assert False, "ValueError가 발생해야 합니다."
except ValueError as e:
    print(f"  예외 정상 발생: {e}")
print(">> 케이스 3 통과")

print("\n>> ScoreEngine 전체 테스트 통과")
