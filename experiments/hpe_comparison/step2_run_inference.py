"""
step2_run_inference.py — 모델별 추론 실행 & 결과 저장
──────────────────────────────────────────────────────
각 영상 × 각 모델에 대해:
  1) 프레임마다 추론 수행 (inference time 기록)
  2) COCO 17 포맷으로 통일된 키포인트 좌표 + 신뢰도 저장
  3) CSV로 내보내기 → results/raw/{모델}_{영상이름}.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
from tqdm import tqdm

from config import (
    MODELS_TO_RUN, RAW_DIR, WARMUP_FRAMES,
    MEDIAPIPE_COMPLEXITY, MEDIAPIPE_MIN_DETECTION, MEDIAPIPE_MIN_TRACKING,
    MOVENET_LIGHTNING_URL, MOVENET_THUNDER_URL,
    MOVENET_LIGHTNING_SIZE, MOVENET_THUNDER_SIZE,
    MMPOSE_MODEL,
    get_video_list,
)
from utils import (
    VideoReader, Timer,
    mediapipe_to_coco, movenet_to_coco,
    build_csv_header, keypoints_to_row, save_csv,
)


# ══════════════════════════════════════════════════════
#  모델 래퍼 클래스들
# ══════════════════════════════════════════════════════
class MediaPipeRunner:
    """MediaPipe BlazePose 래퍼"""

    def __init__(self):
        import mediapipe as mp
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=MEDIAPIPE_COMPLEXITY,
            min_detection_confidence=MEDIAPIPE_MIN_DETECTION,
            min_tracking_confidence=MEDIAPIPE_MIN_TRACKING,
        )
        self.name = "mediapipe"

    def infer(self, frame_bgr: np.ndarray) -> np.ndarray | None:
        """BGR 프레임 → COCO 17 키포인트 or None"""
        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        results = self.pose.process(rgb)
        if results.pose_landmarks is None:
            return None
        return mediapipe_to_coco(results.pose_landmarks.landmark, w, h)

    def close(self):
        self.pose.close()


class MoveNetRunner:
    """MoveNet (Lightning / Thunder) 래퍼"""

    def __init__(self, variant: str = "lightning"):
        import tensorflow as tf
        import tensorflow_hub as hub

        if variant == "lightning":
            url = MOVENET_LIGHTNING_URL
            self.input_size = MOVENET_LIGHTNING_SIZE
            self.name = "movenet_lightning"
        else:
            url = MOVENET_THUNDER_URL
            self.input_size = MOVENET_THUNDER_SIZE
            self.name = "movenet_thunder"

        print(f"  ⏳  MoveNet({variant}) 모델 로딩 중…")
        self.model = hub.load(url)
        self.movenet = self.model.signatures["serving_default"]
        print(f"  ✅  로딩 완료")

    def infer(self, frame_bgr: np.ndarray) -> np.ndarray | None:
        import tensorflow as tf

        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        img = tf.image.resize_with_pad(
            tf.expand_dims(rgb, axis=0), self.input_size, self.input_size
        )
        img = tf.cast(img, dtype=tf.int32)
        outputs = self.movenet(img)
        kps = outputs["output_0"].numpy()  # (1,1,17,3)
        return movenet_to_coco(kps, w, h)

    def close(self):
        pass


class MMPoseRunner:
    """MMPose RTMPose 래퍼 (선택)"""

    def __init__(self):
        try:
            from mmpose.apis import MMPoseInferencer
        except ImportError:
            raise ImportError(
                "mmpose가 설치되지 않았습니다. "
                "pip install -U openmim && mim install mmengine mmcv mmdet mmpose"
            )
        print(f"  ⏳  MMPose({MMPOSE_MODEL}) 모델 로딩 중…")
        self.inferencer = MMPoseInferencer(MMPOSE_MODEL)
        self.name = "mmpose"
        print(f"  ✅  로딩 완료")

    def infer(self, frame_bgr: np.ndarray) -> np.ndarray | None:
        h, w = frame_bgr.shape[:2]
        result = next(self.inferencer(frame_bgr, return_vis=False))
        preds = result.get("predictions", [[]])
        if not preds or not preds[0]:
            return None
        kps_raw = np.array(preds[0][0]["keypoints"])       # (17, 2)
        scores = np.array(preds[0][0]["keypoint_scores"])   # (17,)
        kps = np.zeros((17, 3), dtype=np.float32)
        kps[:, :2] = kps_raw
        kps[:, 2] = scores
        return kps

    def close(self):
        pass


# ══════════════════════════════════════════════════════
#  모델 팩토리
# ══════════════════════════════════════════════════════
def create_runner(model_name: str):
    if model_name == "mediapipe":
        return MediaPipeRunner()
    elif model_name == "movenet_lightning":
        return MoveNetRunner("lightning")
    elif model_name == "movenet_thunder":
        return MoveNetRunner("thunder")
    elif model_name == "mmpose":
        return MMPoseRunner()
    else:
        raise ValueError(f"지원하지 않는 모델: {model_name}")


# ══════════════════════════════════════════════════════
#  메인 추론 루프
# ══════════════════════════════════════════════════════
def run_inference_for_model(runner, video_path: Path):
    """단일 모델 × 단일 영상 추론"""
    vr = VideoReader(video_path)
    print(f"\n  🎬  영상: {video_path.name}  ({vr.info['original_size']}, "
          f"{vr.fps:.1f}fps, {vr.total_frames} frames)")

    header = build_csv_header()
    rows = []
    skipped = 0

    for idx, frame in enumerate(tqdm(vr, total=len(vr),
                                     desc=f"    {runner.name}", ncols=80)):
        with Timer() as t:
            kps = runner.infer(frame)

        if idx < WARMUP_FRAMES:
            continue  # 웜업 프레임은 저장하지 않음

        if kps is None:
            skipped += 1
            continue

        rows.append(keypoints_to_row(idx, t.elapsed_ms, kps))

    # CSV 저장
    stem = video_path.stem
    csv_path = RAW_DIR / f"{runner.name}_{stem}.csv"
    save_csv(rows, header, csv_path)

    if skipped:
        print(f"  ⚠️  감지 실패 프레임: {skipped}")

    return csv_path


def main():
    print()
    print("╔══════════════════════════════════════════════╗")
    print("║   Step 2: 모델별 추론 실행                    ║")
    print("╚══════════════════════════════════════════════╝")

    videos = get_video_list()
    if not videos:
        print("  ❌  입력 영상이 없습니다. step1 을 먼저 실행하세요.")
        sys.exit(1)

    print(f"\n  📋  대상 모델: {MODELS_TO_RUN}")
    print(f"  📋  대상 영상: {[v.name for v in videos]}")

    results_map = {}  # {모델: [csv_paths]}

    for model_name in MODELS_TO_RUN:
        print(f"\n{'━' * 55}")
        print(f"  🤖  모델: {model_name}")
        print(f"{'━' * 55}")

        try:
            runner = create_runner(model_name)
        except Exception as e:
            print(f"  ❌  모델 로딩 실패: {e}")
            continue

        csv_paths = []
        for vpath in videos:
            try:
                p = run_inference_for_model(runner, vpath)
                csv_paths.append(p)
            except Exception as e:
                print(f"  ❌  추론 실패 ({vpath.name}): {e}")

        runner.close()
        results_map[model_name] = csv_paths

    print(f"\n{'═' * 55}")
    print(f"  ✅  추론 완료! 결과 → {RAW_DIR}")
    print(f"  👉  다음 단계: python step3_analyze.py")
    print(f"{'═' * 55}")


if __name__ == "__main__":
    main()
