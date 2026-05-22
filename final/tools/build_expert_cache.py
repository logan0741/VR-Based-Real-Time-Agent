"""오프라인 전문가 포즈 캐시 빌더.

TensorFlow가 설치된 환경에서 1회 실행하면 각 전문가 영상 옆에 .npy 파일을 저장한다.
이후 서버는 TF 없이 .npy 파일만 로드해 동작한다.

실행:
    python final/tools/build_expert_cache.py
    python final/tools/build_expert_cache.py --exercise squat
    python final/tools/build_expert_cache.py --force   # 기존 .npy 덮어쓰기
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from final.s01_preprocessing.config import EXERCISES
from final.s01_preprocessing.pose_estimator import PoseEstimator
from final.s01_preprocessing.pose_normalizer import PoseNormalizer
from final.s01_preprocessing.expert_cache import ExpertPoseCache, _npy_path_for


def build(exercise: str, cfg: dict, force: bool) -> None:
    """단일 종목 전문가 영상을 처리하고 .npy 파일을 저장한다."""
    video_path = cfg["video_path"]
    npy_path = _npy_path_for(video_path)

    if not Path(video_path).exists():
        print(f"[SKIP] 영상 없음: {video_path}")
        return

    if npy_path.exists() and not force:
        print(f"[SKIP] 이미 존재 (--force로 덮어쓰기 가능): {npy_path.name}")
        return

    print(f"\n[BUILD] {exercise} - {Path(video_path).name}")

    estimator = PoseEstimator()
    estimator.load()

    cache = ExpertPoseCache(
        video_path=video_path,
        target_fps=cfg["target_fps"],
        normalizer_type=cfg["normalizer_type"],
        norm_buffer_size=cfg["norm_buffer_size"],
        estimator=estimator,
    )
    cache.build()
    print(f"[DONE] {npy_path.name} 저장 완료 (shape={cache.sequence.shape})")


def main() -> int:
    parser = argparse.ArgumentParser(description="전문가 포즈 .npy 캐시 빌더")
    parser.add_argument("--exercise", default=None, help="특정 종목만 빌드 (기본: 전체)")
    parser.add_argument("--force", action="store_true", help="기존 .npy 파일 덮어쓰기")
    args = parser.parse_args()

    targets = (
        {args.exercise: EXERCISES[args.exercise]}
        if args.exercise
        else EXERCISES
    )

    if args.exercise and args.exercise not in EXERCISES:
        print(f"[ERROR] 알 수 없는 종목: {args.exercise!r}")
        print(f"  지원 종목: {list(EXERCISES.keys())}")
        return 1

    print("=" * 55)
    print("  전문가 포즈 캐시 빌더")
    print(f"  대상: {list(targets.keys())}")
    print(f"  덮어쓰기: {'예' if args.force else '아니오'}")
    print("=" * 55)

    for exercise, cfg in targets.items():
        if not cfg.get("implemented", False):
            print(f"\n[SKIP] {exercise} - implemented=False (백엔드 미구현)")
            continue
        try:
            build(exercise, cfg, args.force)
        except Exception as exc:
            print(f"[ERROR] {exercise} 빌드 실패: {exc}")

    print("\n[완료] 서버는 이제 TF 없이 .npy 파일만으로 동작합니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
