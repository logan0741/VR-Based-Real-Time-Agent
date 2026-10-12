"""
run_pipeline.py — 전체 파이프라인 실행
──────────────────────────────────────
Step 1~4 를 순차적으로 실행합니다.
혹은 개별 단계만 실행:
  python run_pipeline.py --step 2
  python run_pipeline.py --step 3
  python run_pipeline.py --step 4
"""

import argparse
import sys
import time


def run_step(step_num: int):
    print(f"\n{'▓' * 60}")
    print(f"  ▶  Step {step_num} 시작")
    print(f"{'▓' * 60}")
    start = time.time()

    if step_num == 1:
        from step1_check_env import main
        main()
    elif step_num == 2:
        from step2_run_inference import main
        main()
    elif step_num == 3:
        from step3_analyze import main
        main()
    elif step_num == 4:
        from step4_visualize import main
        main()
    else:
        print(f"  ❌  잘못된 step 번호: {step_num}")
        sys.exit(1)

    elapsed = time.time() - start
    print(f"\n  ⏱️  Step {step_num} 완료 ({elapsed:.1f}초)")


def main():
    parser = argparse.ArgumentParser(
        description="HPE 라이브러리 비교 실험 파이프라인"
    )
    parser.add_argument(
        "--step", type=int, default=0,
        help="특정 단계만 실행 (1~4). 지정 안하면 전체 순차 실행"
    )
    parser.add_argument(
        "--skip-check", action="store_true",
        help="Step 1 (환경 점검) 건너뛰기"
    )
    args = parser.parse_args()

    print()
    print("╔═══════════════════════════════════════════════════════╗")
    print("║          HPE 라이브러리 비교 실험 파이프라인            ║")
    print("║   MoveNet vs MediaPipe vs MMPose                     ║")
    print("╚═══════════════════════════════════════════════════════╝")

    if args.step > 0:
        run_step(args.step)
    else:
        steps = [1, 2, 3, 4]
        if args.skip_check:
            steps = [2, 3, 4]

        for s in steps:
            run_step(s)

    print()
    print("╔═══════════════════════════════════════════════════════╗")
    print("║  🏁  전체 파이프라인 완료!                              ║")
    print("║  결과:  experiments/hpe_comparison/results/           ║")
    print("║    ├─ raw/       → 프레임별 키포인트 CSV               ║")
    print("║    ├─ charts/    → 시각화 차트 PNG                    ║")
    print("║    └─ report/    → 요약 CSV + 상세 JSON               ║")
    print("╚═══════════════════════════════════════════════════════╝")


if __name__ == "__main__":
    main()
