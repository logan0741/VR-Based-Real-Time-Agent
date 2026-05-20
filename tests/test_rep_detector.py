"""05 RepDetector 테스트."""

import numpy as np

from backend.config import EXERCISES
from backend.expert_cache import ExpertPoseCache
from backend.pose_estimator import PoseEstimator
from backend.rep_detector import RepDetector

cfg = EXERCISES["squat"]

print("=" * 55)
print("05 RepDetector 테스트")
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


detector = RepDetector(
    rep_detector_type=cfg["rep_detector_type"],
    normalizer_type=cfg["normalizer_type"],
    slope_window=cfg["rep_slope_window"],
    min_rep_frames=cfg["min_rep_frames"],
)

# ── 케이스 1: 4회 영상 → 4개 구간 감지 ──────────────────────────────────────
print("\n[케이스 1] squat_full.mp4 (4회)")
seq_full = build_sequence("assets/expert_videos/squat_full.mp4")
reps_full = detector.detect(seq_full)
print(f"감지된 구간 수: {len(reps_full)}")
for i, (s, e) in enumerate(reps_full):
    print(f"  Rep {i + 1}: frame {s} ~ {e}  (길이 {e - s})")
assert len(reps_full) == 4, f"4회 영상에서 4개 구간이 감지되어야 함: {len(reps_full)}개"
print(">> 케이스 1 통과")

# ── 케이스 2: 1회 영상 → 1개 구간 감지 (WAIT_PEAK 상태 종료 케이스) ──────────
print("\n[케이스 2] squat.mp4 (1회)")
seq_single = build_sequence("assets/expert_videos/squat.mp4")
reps_single = detector.detect(seq_single)
print(f"감지된 구간 수: {len(reps_single)}")
for i, (s, e) in enumerate(reps_single):
    print(f"  Rep {i + 1}: frame {s} ~ {e}  (길이 {e - s})")
assert len(reps_single) == 1, f"1회 영상에서 1개 구간이 감지되어야 함: {len(reps_single)}개"
print(">> 케이스 2 통과")

# ── 케이스 3: 짧은 시퀀스 → ValueError ──────────────────────────────────────
print("\n[케이스 3] 짧은 시퀀스 예외")
try:
    short_seq = np.zeros((cfg["rep_slope_window"], 17, 3), dtype=np.float32)
    detector.detect(short_seq)
    assert False, "ValueError가 발생해야 합니다."
except ValueError as e:
    print(f"예외 정상 발생: {e}")
print(">> 케이스 3 통과")

print("\n>> RepDetector 전체 테스트 통과")
