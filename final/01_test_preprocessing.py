"""Stage 01: 전처리 독립 테스트 - PoseNormalizer, RepDetector, ScoreEngine, DTWComparator"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np

def test_pose_normalizer():
    from final.s01_preprocessing.pose_normalizer import PoseNormalizer
    kpts = np.zeros((17, 3), dtype=np.float32)
    kpts[5] = [0.3, 0.5, 0.9]   # left_shoulder
    kpts[6] = [0.3, 0.5, 0.9]   # right_shoulder
    kpts[11] = [0.6, 0.5, 0.9]  # left_hip
    kpts[12] = [0.6, 0.5, 0.9]  # right_hip
    for i in range(17):
        kpts[i] = [0.1 * i, 0.1 * i, 0.9]
    normalizer = PoseNormalizer("side_left", buffer_size=7)
    result = normalizer.normalize(kpts)
    assert result.shape == (17, 3), f"shape 오류: {result.shape}"
    print("[OK] PoseNormalizer")

def test_rep_detector():
    from final.s01_preprocessing.rep_detector import RepDetector
    detector = RepDetector(
        rep_detector_type="squat",
        normalizer_type="side_left",
        slope_window=5,
        min_rep_frames=3,
    )
    kpts = np.zeros((17, 3), dtype=np.float32)
    for i in range(50):
        kpts[13, 0] = 0.5 + 0.3 * np.sin(i * 0.3)  # left_knee y 진동
        detector.update(kpts)
    print("[OK] RepDetector: reps =", len(detector._reps))

def test_score_engine():
    from final.s01_preprocessing.score_engine import ScoreEngine
    engine = ScoreEngine(weights=[1.0] * 8, max_distance=1.0, n_frames=10)
    dist_matrix = np.random.rand(20, 8).astype(np.float32) * 0.5
    score, rep_scores = engine.update(dist_matrix, [])
    assert 0 <= score <= 100, f"점수 범위 오류: {score}"
    print("[OK] ScoreEngine: score =", score)

def test_dtw_comparator():
    try:
        from final.s01_preprocessing.dtw_comparator import DTWComparator
        keypoints_used = [5, 6, 11, 12, 13, 14, 15, 16]
        comparator = DTWComparator(keypoints_used=keypoints_used)
        user_seq = np.random.rand(15, 17, 3).astype(np.float32)
        expert_seq = np.random.rand(20, 17, 3).astype(np.float32)
        result = comparator.compare(user_seq, expert_seq)
        assert result.shape == (15, 8), f"출력 shape 오류: {result.shape}"
        print("[OK] DTWComparator: output shape =", result.shape)
    except ImportError:
        print("[SKIP] DTWComparator - dtaidistance 미설치. pip install dtaidistance")

if __name__ == "__main__":
    print("=" * 50)
    print("  Stage 01: 전처리 테스트")
    print("=" * 50)
    test_pose_normalizer()
    test_rep_detector()
    test_score_engine()
    test_dtw_comparator()
    print("\n[DONE] Stage 01 전처리 테스트 완료")
