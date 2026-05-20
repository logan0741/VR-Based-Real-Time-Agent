import argparse
from pathlib import Path
import urllib.error

import cv2
import numpy as np

from backend.config import EXERCISES
from backend.dtw_comparator import DTWComparator
from backend.expert_cache import ExpertPoseCache
from backend.pose_estimator import PoseEstimator
from backend.pose_normalizer import PoseNormalizer
from backend.rep_detector import RepDetector
from backend.score_engine import ScoreEngine
from backend.ui_renderer import PANEL_HEIGHT, UIRenderer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the PT analysis demo.")
    parser.add_argument(
        "--video",
        default=None,
        help="Path to an input video. If omitted, webcam 0 is used.",
    )
    parser.add_argument(
        "--exercise",
        default="squat",
        choices=sorted(EXERCISES.keys()),
        help="Exercise configuration to use.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional path to save the rendered output video.",
    )
    parser.add_argument(
        "--no-feedback",
        action="store_true",
        help="Disable the real-time feedback module.",
    )
    parser.add_argument(
        "--loops",
        type=int,
        default=1,
        help="Number of times to loop the input video (ignored for webcam).",
    )
    return parser.parse_args()


def build_output_path(video_arg: str | None, output_arg: str | None) -> Path:
    if output_arg is not None:
        path = Path(output_arg)
    elif video_arg is not None:
        path = Path("assets/output_videos") / f"{Path(video_arg).stem}_output.mp4"
    else:
        path = Path("assets/output_videos") / "webcam_output.mp4"

    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def open_capture(video_arg: str | None) -> cv2.VideoCapture:
    if video_arg is None:
        cap = cv2.VideoCapture(0)
    else:
        cap = cv2.VideoCapture(video_arg)

    if not cap.isOpened():
        source = "webcam(0)" if video_arg is None else video_arg
        raise FileNotFoundError(f"Cannot open input source: {source}")
    return cap


def validate_video_fps(cap: cv2.VideoCapture, video_arg: str | None, target_fps: int) -> None:
    """영상 파일 입력의 FPS가 target_fps와 일치하는지 검증한다. 웹캠 입력은 건너뜀."""
    if video_arg is None:
        return
    actual_fps = cap.get(cv2.CAP_PROP_FPS)
    if abs(actual_fps - target_fps) > 0.5:
        raise ValueError(
            f"입력 영상 FPS({actual_fps:.2f})가 target_fps({target_fps})와 다릅니다.\n"
            f"        영상을 {target_fps}fps로 변환 후 다시 실행하세요."
        )


def main() -> int:
    args = parse_args()
    cfg = EXERCISES[args.exercise]
    expert_video = cfg["video_path"]
    output_path = build_output_path(args.video, args.output)

    print("=" * 55)
    print("PT Analysis Demo")
    print("=" * 55)
    print(f"[Input] {'webcam(0)' if args.video is None else args.video}")
    print(f"[Expert] {expert_video}")
    print(f"[Output] {output_path}")
    print(f"[Feedback] {'disabled' if args.no_feedback else 'enabled'}")

    estimator = PoseEstimator()
    try:
        estimator.load()
    except urllib.error.URLError as exc:
        print("\n[Error] Failed to download the MoveNet model from TensorFlow Hub.")
        print("        Check your internet connection and try again.")
        print(f"        Details: {exc}")
        return 1

    print("\n[Setup] Building expert cache...")
    expert_cache = ExpertPoseCache(
        estimator=estimator,
        video_path=expert_video,
        target_fps=cfg["target_fps"],
        normalizer_type=cfg["normalizer_type"],
        norm_buffer_size=cfg["norm_buffer_size"],
        frame_height=PANEL_HEIGHT,
    )
    expert_cache.build()
    print(f"  Expert frames: {len(expert_cache.frames)}")

    comparator = DTWComparator(keypoints_used=cfg["keypoints_used"])
    detector = RepDetector(
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
    feedback_enabled = not args.no_feedback
    feedback_engine = None
    feedback_policy = None
    if feedback_enabled:
        try:
            from backend.feedback import FeedbackEngine, FeedbackPolicy
        except ModuleNotFoundError as exc:
            if exc.name is None or not exc.name.startswith("backend.feedback"):
                raise
            feedback_enabled = False
            print("[Feedback] module not found; disabled")
        else:
            feedback_engine = FeedbackEngine(args.exercise, cfg["view"])
            feedback_policy = FeedbackPolicy(update_interval=cfg["target_fps"] * 2)
    normalizer = PoseNormalizer(cfg["normalizer_type"], cfg["norm_buffer_size"])

    cap = open_capture(args.video)
    validate_video_fps(cap, args.video, cfg["target_fps"])
    writer: cv2.VideoWriter | None = None
    norm_seq: list[np.ndarray] = []
    rep_scores_final: list[int] = []
    prev_rep_count = 0
    score: int | None = None
    window_dist_matrix: np.ndarray | None = None
    feedback_message: str = "측정 중입니다." if feedback_enabled else "Feedback disabled."

    print("\n[Run] Press 'q' to quit.")
    renderer.start()

    loop_count = 0
    max_loops = args.loops if args.video is not None else 1

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                loop_count += 1
                if loop_count >= max_loops:
                    break
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            kp = estimator.predict(frame)
            norm_kp = normalizer.normalize(kp)
            norm_seq.append(norm_kp)
            n = len(norm_seq)

            reps = detector.update(norm_kp)

            feedback_candidate: dict[str, object] | None = None

            if n >= cfg["n_frames"] and n % cfg["dtw_interval"] == 0:
                window_seq = np.stack(norm_seq[-cfg["n_frames"]:], axis=0).astype(np.float32)
                window_dist_matrix, best_expert_idx = comparator.compare(window_seq, expert_cache.sequence)

                new_rep_matrices: list[np.ndarray] = []
                for start, end in reps[prev_rep_count:]:
                    rep_seq = np.stack(norm_seq[start:end], axis=0).astype(np.float32)
                    rep_dist_matrix, _ = comparator.compare(rep_seq, expert_cache.sequence)
                    new_rep_matrices.append(rep_dist_matrix)
                prev_rep_count = len(reps)

                score, rep_scores_final = engine.update(window_dist_matrix, new_rep_matrices)

                if feedback_enabled:
                    assert feedback_engine is not None
                    expert_kp = expert_cache.sequence[int(best_expert_idx[-1])]
                    feedback_candidate = feedback_engine.analyze(
                        user_raw_keypoints=kp,
                        user_norm_keypoints=norm_kp,
                        expert_norm_keypoints=expert_kp,
                        joint_distances=window_dist_matrix[-1],
                    )

            if feedback_enabled:
                assert feedback_policy is not None
                feedback_message = feedback_policy.update(n, feedback_candidate)

            result = {
                "keypoints": kp,
                "score": score,
                "rep_scores": rep_scores_final,
                "feedback": feedback_message,
                "fps": 0.0,
            }
            canvas = renderer.render(frame, result)

            if writer is None:
                h, w = canvas.shape[:2]
                writer = cv2.VideoWriter(
                    str(output_path),
                    cv2.VideoWriter_fourcc(*"mp4v"),
                    cfg["target_fps"],
                    (w, h),
                )
            writer.write(canvas)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        reps_final = detector.finalize()
        new_rep_matrices = []
        for start, end in reps_final[prev_rep_count:]:
            rep_seq = np.stack(norm_seq[start:end], axis=0).astype(np.float32)
            new_rep_matrices.append(comparator.compare(rep_seq, expert_cache.sequence))
        if window_dist_matrix is not None and new_rep_matrices:
            _, rep_scores_final = engine.update(window_dist_matrix, new_rep_matrices)
    finally:
        cap.release()
        if writer is not None:
            writer.release()
        cv2.destroyAllWindows()

    print(f"\n[Done] Output saved to: {output_path}")
    print(f"[Done] Rep scores: {rep_scores_final}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
