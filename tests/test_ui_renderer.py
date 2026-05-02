"""07 UIRenderer 테스트 — test_squat.mp4를 실시간 입력으로 시뮬레이션한다."""

import time

import cv2
import numpy as np

from backend.config import EXERCISES
from backend.dtw_comparator import DTWComparator
from backend.expert_cache import ExpertPoseCache
from backend.pose_estimator import PoseEstimator
from backend.pose_normalizer import PoseNormalizer
from backend.rep_detector import RepDetector
from backend.score_engine import ScoreEngine
from backend.ui_renderer import UIRenderer

cfg = EXERCISES["squat"]
EXPERT_VIDEO = "assets/expert_videos/squat.mp4"
TEST_VIDEO   = "assets/test_videos/test_squat.mp4"

print("=" * 55)
print("07 UIRenderer Test")
print("=" * 55)

estimator = PoseEstimator()
estimator.load()

print("\n[Setup] Building expert cache...")
expert_cache = ExpertPoseCache(
    estimator=estimator,
    video_path=EXPERT_VIDEO,
    target_fps=cfg["target_fps"],
    normalizer_type=cfg["normalizer_type"],
    norm_buffer_size=cfg["norm_buffer_size"],
)
expert_cache.build()
print(f"  Expert frames: {len(expert_cache.frames)}")

comparator = DTWComparator(keypoints_used=cfg["keypoints_used"])
detector   = RepDetector(
    rep_detector_type=cfg["rep_detector_type"],
    normalizer_type=cfg["normalizer_type"],
    slope_window=cfg["rep_slope_window"],
    min_rep_frames=cfg["min_rep_frames"],
)
engine = ScoreEngine(
    weights=cfg["weights"],
    max_distance=cfg["max_distance"],
    n_frames=cfg["n_frames"],
)
renderer = UIRenderer(
    expert_frames=expert_cache.frames,
    expert_keypoints=expert_cache.raw_sequence,
    target_fps=cfg["target_fps"],
)
normalizer = PoseNormalizer(cfg["normalizer_type"], cfg["norm_buffer_size"])

cap = cv2.VideoCapture(TEST_VIDEO)
if not cap.isOpened():
    raise FileNotFoundError(f"Cannot open: {TEST_VIDEO}")

print("\n[Test] Starting. Press 'q' to quit.")
renderer.start()

norm_seq: list[np.ndarray] = []
raw_kps:  list[np.ndarray] = []
frame_times: list[float]   = []
rep_scores_final: list[int] = []

while True:
    ret, frame = cap.read()
    if not ret:
        break

    t0 = time.perf_counter()

    kp      = estimator.predict(frame)
    norm_kp = normalizer.normalize(kp)
    raw_kps.append(kp)
    norm_seq.append(norm_kp)

    n = len(norm_seq)

    if n >= cfg["n_frames"]:
        user_seq    = np.stack(norm_seq, axis=0).astype(np.float32)
        dist_matrix = comparator.compare(user_seq, expert_cache.sequence)
        reps        = detector.detect(user_seq)
        score, rep_scores_final = engine.update(dist_matrix, reps)
    else:
        score          = None
        rep_scores_final = []

    elapsed = time.perf_counter() - t0
    frame_times.append(elapsed)

    result = {
        "keypoints":  kp,
        "score":      score,
        "rep_scores": rep_scores_final,
        "fps":        1.0 / max(elapsed, 1e-9),
    }

    renderer.render(frame, result)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()

if frame_times:
    avg_fps = 1.0 / (sum(frame_times) / len(frame_times))
    min_fps = 1.0 / max(frame_times)
    max_fps = 1.0 / max(min(frame_times), 1e-9)
    print(f"\n[Result] Avg FPS : {avg_fps:.1f}")
    print(f"[Result] Min FPS : {min_fps:.1f}")
    print(f"[Result] Max FPS : {max_fps:.1f}")
    print(f"[Result] Rep scores: {rep_scores_final}")
