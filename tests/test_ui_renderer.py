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
EXPERT_VIDEO  = "assets/expert_videos/squat.mp4"
TEST_VIDEO    = "assets/test_videos/test_squat.mp4"
FPS_LOG_EVERY = 30  # N프레임마다 구간 FPS 출력

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
prev_rep_count: int = 0
score: int | None  = None
window_dist_matrix: np.ndarray | None = None

# 단계별 누적 시간
t_predict:  list[float] = []
t_normalize: list[float] = []
t_dtw:      list[float] = []
t_detector: list[float] = []

# 구간 FPS 측정용
segment_start_time: float = time.perf_counter()
segment_start_frame: int  = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break

    t0 = time.perf_counter()

    t_a = time.perf_counter()
    kp  = estimator.predict(frame)
    t_predict.append(time.perf_counter() - t_a)

    t_a     = time.perf_counter()
    norm_kp = normalizer.normalize(kp)
    t_normalize.append(time.perf_counter() - t_a)

    raw_kps.append(kp)
    norm_seq.append(norm_kp)

    n = len(norm_seq)

    t_a  = time.perf_counter()
    reps = detector.update(norm_kp)
    t_detector.append(time.perf_counter() - t_a)

    if n >= cfg["n_frames"] and n % cfg["dtw_interval"] == 0:
        t_a                = time.perf_counter()
        window_seq         = np.stack(norm_seq[-cfg["n_frames"]:], axis=0).astype(np.float32)
        window_dist_matrix = comparator.compare(window_seq, expert_cache.sequence)
        t_dtw.append(time.perf_counter() - t_a)

        new_rep_matrices: list[np.ndarray] = []
        for start, end in reps[prev_rep_count:]:
            rep_seq = np.stack(norm_seq[start:end], axis=0).astype(np.float32)
            new_rep_matrices.append(comparator.compare(rep_seq, expert_cache.sequence))
        prev_rep_count = len(reps)

        score, rep_scores_final = engine.update(window_dist_matrix, new_rep_matrices)

    elapsed = time.perf_counter() - t0
    frame_times.append(elapsed)

    result = {
        "keypoints":  kp,
        "score":      score,
        "rep_scores": rep_scores_final,
        "fps":        1.0 / max(elapsed, 1e-9),
    }

    renderer.render(frame, result)

    # N프레임마다 구간 FPS 출력
    if n % FPS_LOG_EVERY == 0:
        now             = time.perf_counter()
        segment_elapsed = now - segment_start_time
        segment_frames  = n - segment_start_frame
        seg_fps         = segment_frames / max(segment_elapsed, 1e-9)
        print(f"  [FPS] frame {segment_start_frame:>4}~{n:>4} : {seg_fps:.1f} fps")
        segment_start_time  = now
        segment_start_frame = n

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

reps = detector.finalize()
new_rep_matrices: list[np.ndarray] = []
for start, end in reps[prev_rep_count:]:
    rep_seq = np.stack(norm_seq[start:end], axis=0).astype(np.float32)
    new_rep_matrices.append(comparator.compare(rep_seq, expert_cache.sequence))
if new_rep_matrices:
    _, rep_scores_final = engine.update(window_dist_matrix, new_rep_matrices)

cap.release()
cv2.destroyAllWindows()

if frame_times:
    avg_fps = 1.0 / (sum(frame_times) / len(frame_times))
    min_fps = 1.0 / max(frame_times)
    max_fps = 1.0 / max(min(frame_times), 1e-9)
    print(f"\n[Result] Avg FPS     : {avg_fps:.1f}")
    print(f"[Result] Min FPS     : {min_fps:.1f}")
    print(f"[Result] Max FPS     : {max_fps:.1f}")
    print(f"[Result] Rep scores  : {rep_scores_final}")

def _avg_ms(times: list[float]) -> str:
    if not times:
        return "-"
    return f"{sum(times) / len(times) * 1000:.1f} ms"

print(f"\n[Timing] predict    : {_avg_ms(t_predict)}")
print(f"[Timing] normalize  : {_avg_ms(t_normalize)}")
print(f"[Timing] DTW        : {_avg_ms(t_dtw)}")
print(f"[Timing] detector   : {_avg_ms(t_detector)}")
