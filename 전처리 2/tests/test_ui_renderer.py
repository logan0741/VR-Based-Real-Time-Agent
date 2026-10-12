"""07 UIRenderer 테스트 — test_squat.mp4를 실시간 입력으로 시뮬레이션한다."""

import time
from pathlib import Path

import cv2
import numpy as np

from backend.config import EXERCISES
from backend.dtw_comparator import DTWComparator
from backend.expert_cache import ExpertPoseCache
from backend.feedback import FeedbackEngine, FeedbackPolicy
from backend.pose_estimator import PoseEstimator
from backend.pose_normalizer import PoseNormalizer
from backend.rep_detector import RepDetector
from backend.score_engine import ScoreEngine
from backend.ui_renderer import PANEL_HEIGHT, UIRenderer

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
    frame_height=PANEL_HEIGHT,
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
feedback_engine = FeedbackEngine("squat", "side")
feedback_policy = FeedbackPolicy()
normalizer = PoseNormalizer(cfg["normalizer_type"], cfg["norm_buffer_size"])

cap = cv2.VideoCapture(TEST_VIDEO)
if not cap.isOpened():
    raise FileNotFoundError(f"Cannot open: {TEST_VIDEO}")

print("\n[Test] Starting. Press 'q' to quit.")
renderer.start()

output_dir = Path("assets/output_videos")
output_dir.mkdir(parents=True, exist_ok=True)
output_path = str(output_dir / f"{Path(TEST_VIDEO).stem}_output.mp4")
writer: cv2.VideoWriter | None = None

norm_seq: list[np.ndarray] = []
raw_kps:  list[np.ndarray] = []
frame_times: list[float]   = []
rep_scores_final: list[int] = []
prev_rep_count: int = 0
score: int | None  = None
window_dist_matrix: np.ndarray | None = None
feedback_message: str = "측정 중입니다."

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

    feedback_candidate: dict[str, object] | None = None
    if window_dist_matrix is not None:
        expert_idx = min(n - 1, expert_cache.sequence.shape[0] - 1)
        feedback_candidate = feedback_engine.analyze(
            user_raw_keypoints=kp,
            user_norm_keypoints=norm_kp,
            expert_norm_keypoints=expert_cache.sequence[expert_idx],
            joint_distances=window_dist_matrix[-1],
        )
    feedback_message = feedback_policy.update(n, feedback_candidate)

    elapsed = time.perf_counter() - t0
    frame_times.append(elapsed)

    result = {
        "keypoints":  kp,
        "score":      score,
        "rep_scores": rep_scores_final,
        "feedback":   feedback_message,
        "fps":        1.0 / max(elapsed, 1e-9),
    }

    canvas = renderer.render(frame, result)
    if writer is None:
        h, w = canvas.shape[:2]
        writer = cv2.VideoWriter(
            output_path,
            cv2.VideoWriter_fourcc(*"mp4v"),
            cfg["target_fps"],
            (w, h),
        )
    writer.write(canvas)

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
reps_final = reps
new_rep_matrices: list[np.ndarray] = []
for start, end in reps[prev_rep_count:]:
    rep_seq = np.stack(norm_seq[start:end], axis=0).astype(np.float32)
    new_rep_matrices.append(comparator.compare(rep_seq, expert_cache.sequence))
if new_rep_matrices:
    _, rep_scores_final = engine.update(window_dist_matrix, new_rep_matrices)

if writer is not None:
    writer.release()
    print(f"\n[Output] 저장 완료: {output_path}")

cap.release()
cv2.destroyAllWindows()

if frame_times:
    avg_fps = 1.0 / (sum(frame_times) / len(frame_times))
    min_fps = 1.0 / max(frame_times)
    max_fps = 1.0 / max(min(frame_times), 1e-9)
    rep_frame_counts = [end - start for start, end in reps_final]
    print(f"\n[Result] Avg FPS        : {avg_fps:.1f}")
    print(f"[Result] Min FPS        : {min_fps:.1f}")
    print(f"[Result] Max FPS        : {max_fps:.1f}")
    print(f"[Result] Rep scores     : {rep_scores_final}")
    print(f"[Result] Rep frames     : {rep_frame_counts}")

def _avg_ms(times: list[float]) -> str:
    if not times:
        return "-"
    return f"{sum(times) / len(times) * 1000:.1f} ms"

print(f"\n[Timing] predict    : {_avg_ms(t_predict)}")
print(f"[Timing] normalize  : {_avg_ms(t_normalize)}")
print(f"[Timing] DTW        : {_avg_ms(t_dtw)}")
print(f"[Timing] detector   : {_avg_ms(t_detector)}")

# n_frames 후보별 실시간 점수 vs 회차별 점수 비교
N_FRAMES_CANDIDATES: list[int] = [10, 15, 20, 30, 40, 50, 60]
norm_arr    = np.stack(norm_seq, axis=0).astype(np.float32)
weights_arr = np.array(cfg["weights"], dtype=np.float32)
weights_arr /= weights_arr.sum()

print(f"\n[Analysis] n_frames 후보 비교 (회차별 점수 기준: {rep_scores_final})")
print(f"  {'n_frames':>10} | {'rep별 실시간 평균':>24} | {'rep별 차이':>20} | {'평균 차이':>8}")
print("  " + "-" * 72)

for n_test in N_FRAMES_CANDIDATES:
    if len(norm_seq) < n_test:
        continue

    frame_rt: dict[int, int] = {}
    for i in range(n_test, len(norm_seq) + 1, cfg["dtw_interval"]):
        window = norm_arr[i - n_test : i]
        dm     = comparator.compare(window, expert_cache.sequence)
        dist   = float(np.mean(dm @ weights_arr))
        frame_rt[i - 1] = max(0, round(100 * (1.0 - dist / cfg["max_distance"])))

    rep_rt_avgs: list[int] = []
    for start, end in reps_final:
        in_rep = [v for k, v in frame_rt.items() if start <= k <= end]
        rep_rt_avgs.append(round(sum(in_rep) / len(in_rep)) if in_rep else 0)

    diffs    = [abs(rt - pr) for rt, pr in zip(rep_rt_avgs, rep_scores_final)]
    avg_diff = sum(diffs) / len(diffs) if diffs else 0.0

    print(f"  n_frames={n_test:>2} | {str(rep_rt_avgs):>24} | {str(diffs):>20} | {avg_diff:>8.1f}")
