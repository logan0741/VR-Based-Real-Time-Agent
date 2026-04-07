"""
step1_check_env.py — 환경 점검 & 샘플 영상 생성
──────────────────────────────────────────────────
• 필수 패키지 설치 여부 확인
• 테스트용 영상이 없으면 웹캠으로 간단 녹화 지원
"""

import sys
import importlib
from pathlib import Path

from config import INPUT_VIDEO_DIR, MODELS_TO_RUN, get_video_list


# ─────────────────────────────────────────────────────
# 1) 패키지 설치 확인
# ─────────────────────────────────────────────────────
REQUIRED = {
    "cv2":        "opencv-python",
    "numpy":      "numpy",
    "pandas":     "pandas",
    "matplotlib": "matplotlib",
    "scipy":      "scipy",
    "tqdm":       "tqdm",
    "tabulate":   "tabulate",
}

MODEL_DEPS = {
    "mediapipe":        {"mediapipe": "mediapipe"},
    "movenet_lightning": {"tensorflow": "tensorflow-cpu", "tensorflow_hub": "tensorflow-hub"},
    "movenet_thunder":   {"tensorflow": "tensorflow-cpu", "tensorflow_hub": "tensorflow-hub"},
    "mmpose":           {"mmpose": "mmpose (via openmim)"},
}


def check_packages():
    print("=" * 55)
    print("  📦  패키지 설치 상태 확인")
    print("=" * 55)

    missing = []

    # 기본 패키지
    for mod, pkg in REQUIRED.items():
        try:
            importlib.import_module(mod)
            print(f"  ✅  {pkg}")
        except ImportError:
            print(f"  ❌  {pkg}  ← pip install {pkg}")
            missing.append(pkg)

    # 모델별 패키지
    for model in MODELS_TO_RUN:
        deps = MODEL_DEPS.get(model, {})
        for mod, pkg in deps.items():
            try:
                importlib.import_module(mod)
                print(f"  ✅  {pkg}  (for {model})")
            except ImportError:
                print(f"  ❌  {pkg}  (for {model})  ← 설치 필요")
                missing.append(pkg)

    print()
    if missing:
        print(f"  ⚠️  누락 패키지 {len(missing)}개 — 위 안내대로 설치 후 재실행하세요.")
        return False
    else:
        print("  🎉  모든 패키지 정상!")
        return True


# ─────────────────────────────────────────────────────
# 2) 입력 영상 확인
# ─────────────────────────────────────────────────────
def check_videos():
    print()
    print("=" * 55)
    print("  🎬  입력 영상 확인")
    print("=" * 55)

    videos = get_video_list()
    if videos:
        print(f"  발견된 영상 {len(videos)}개:")
        for v in videos:
            print(f"    • {v.name}")
        return True
    else:
        print(f"  ⚠️  입력 영상이 없습니다!")
        print(f"      → {INPUT_VIDEO_DIR} 폴더에 .mp4 파일을 넣어주세요.")
        print()
        ans = input("  웹캠으로 테스트 영상을 녹화할까요? (y/n): ").strip().lower()
        if ans == "y":
            record_sample_videos()
            return True
        return False


# ─────────────────────────────────────────────────────
# 3) 웹캠 녹화 (선택)
# ─────────────────────────────────────────────────────
def record_sample_videos():
    """간단한 웹캠 녹화: 정적(5초) + 동적(15초) 영상"""
    import cv2

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("  ❌  웹캠을 열 수 없습니다.")
        return

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")

    sessions = [
        ("static_pose.mp4", 5,  "정지 자세를 5초간 유지하세요 (예: 차렷)"),
        ("dynamic_squat.mp4", 15, "스쿼트를 천천히 반복하세요 (15초)"),
    ]

    for filename, duration, instruction in sessions:
        out_path = INPUT_VIDEO_DIR / filename
        writer = cv2.VideoWriter(str(out_path), fourcc, fps, (w, h))

        print()
        print(f"  📹  [{filename}] {instruction}")
        print(f"       SPACE 로 녹화 시작 / 자동으로 {duration}초 후 종료")
        print(f"       (ESC 로 건너뛰기)")

        # 대기 루프
        recording = False
        frame_count = 0
        max_frames = int(fps * duration)

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            display = frame.copy()
            if recording:
                remaining = duration - frame_count / fps
                cv2.putText(display, f"REC  {remaining:.1f}s",
                            (20, 40), cv2.FONT_HERSHEY_SIMPLEX,
                            1.0, (0, 0, 255), 2)
                writer.write(frame)
                frame_count += 1
                if frame_count >= max_frames:
                    break
            else:
                cv2.putText(display, "SPACE to start / ESC to skip",
                            (20, 40), cv2.FONT_HERSHEY_SIMPLEX,
                            0.7, (0, 255, 0), 2)

            cv2.imshow("HPE Recorder", display)
            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC
                break
            if key == 32 and not recording:  # SPACE
                recording = True

        writer.release()
        if frame_count > 0:
            print(f"  💾  저장: {out_path}  ({frame_count} frames)")
        else:
            out_path.unlink(missing_ok=True)
            print(f"  ⏭️  건너뜀")

    cap.release()
    cv2.destroyAllWindows()

    # config.py 에 태그 자동 세팅 안내
    print()
    print("  ℹ️  config.py 의 VIDEO_TAGS 에 아래를 추가하면 분석이 더 정확합니다:")
    print('      VIDEO_TAGS = {"static_pose.mp4": "static", "dynamic_squat.mp4": "dynamic"}')


# ─────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────
def main():
    print()
    print("╔══════════════════════════════════════════════╗")
    print("║   Step 1: 환경 점검 & 데이터 준비            ║")
    print("╚══════════════════════════════════════════════╝")
    print()

    ok_pkg = check_packages()
    ok_vid = check_videos()

    print()
    print("─" * 55)
    if ok_pkg and ok_vid:
        print("  ✅  환경 준비 완료! → python step2_run_inference.py")
    else:
        print("  ⚠️  위 문제를 해결한 후 다시 실행해주세요.")
    print("─" * 55)


if __name__ == "__main__":
    main()
