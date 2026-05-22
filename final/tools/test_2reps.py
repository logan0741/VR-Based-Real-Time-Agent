"""서버 WebSocket 2회 rep 통합 테스트.

스쿼트 동작을 시뮬레이션하는 keypoints를 전송하여
rep_count=2, score 유효성, feedback.message 수신을 검증한다.

실행 (서버 켜진 상태에서):
    python final/tools/test_2reps.py
    python final/tools/test_2reps.py --port 8001
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time

import websocket


def make_squat_keypoints(phase: float) -> list:
    """phase 0~1로 스쿼트 동작을 모사한 COCO-17 keypoints를 반환한다 (MoveNet yx 형식)."""
    # 내려갈 때(0->0.5) 무릎 y 증가, 올라올 때(0.5->1) 감소
    depth = 0.5 * (1 - math.cos(phase * 2 * math.pi))

    kpts = [
        [0.10, 0.50, 0.95],  # 0 nose
        [0.12, 0.48, 0.90],  # 1 left_eye
        [0.12, 0.52, 0.90],  # 2 right_eye
        [0.14, 0.45, 0.85],  # 3 left_ear
        [0.14, 0.55, 0.85],  # 4 right_ear
        [0.25, 0.42, 0.95],  # 5 left_shoulder
        [0.25, 0.58, 0.95],  # 6 right_shoulder
        [0.38, 0.40, 0.90],  # 7 left_elbow
        [0.38, 0.60, 0.90],  # 8 right_elbow
        [0.50, 0.40, 0.85],  # 9 left_wrist
        [0.50, 0.60, 0.85],  # 10 right_wrist
        [0.45, 0.44, 0.95],  # 11 left_hip
        [0.45, 0.56, 0.95],  # 12 right_hip
        [0.45 + depth * 0.25, 0.42, 0.95],  # 13 left_knee (내려갈수록 y 증가)
        [0.45 + depth * 0.25, 0.58, 0.95],  # 14 right_knee
        [0.75, 0.42, 0.90],  # 15 left_ankle
        [0.75, 0.58, 0.90],  # 16 right_ankle
    ]
    return kpts


def run_test(port: int) -> bool:
    url = f"ws://127.0.0.1:{port}/ws/pose"
    print(f"\n[TEST] 연결: {url}")

    results = []
    errors = []

    def on_message(ws_app, message):
        data = json.loads(message)
        if data.get("status") != "ok":
            return
        fb = data.get("feedback", {})
        rep_count = fb.get("rep_count", 0)
        score = fb.get("score", 0)
        msg = fb.get("message", "")
        results.append({"rep_count": rep_count, "score": score, "message": msg})
        if rep_count > 0:
            print(f"  frame={len(results):3d}  rep={rep_count}  score={score}  msg={msg[:30]}")

    def on_error(ws_app, error):
        errors.append(str(error))

    ws = websocket.WebSocket()
    try:
        ws.connect(url, timeout=5)
    except Exception as e:
        print(f"[FAIL] 연결 실패: {e}")
        return False

    # session_start
    ws.send(json.dumps({"data_type": "session_start", "user_id": "test", "exercise_type": "squat"}))
    time.sleep(0.2)

    # 2회 스쿼트 시뮬레이션: 각 rep = 48프레임(약 1.6초 @ 30fps)
    # slope_window=15 때문에 첫 사이클은 state machine 동기화에 사용됨 → 3사이클 필요
    FRAMES_PER_REP = 48
    TOTAL_FRAMES = FRAMES_PER_REP * 3 + 24  # 3사이클 + 여유 (2회 rep 보장)

    print(f"[TEST] {TOTAL_FRAMES}프레임 전송 중 (2회 rep 시뮬레이션)...")
    for i in range(TOTAL_FRAMES):
        phase = (i % FRAMES_PER_REP) / FRAMES_PER_REP
        kpts = make_squat_keypoints(phase)
        ws.send(json.dumps({
            "data_type": "keypoints",
            "frame_id": f"test_{i}",
            "payload": kpts,
        }))
        raw = ws.recv()
        data = json.loads(raw)
        if data.get("status") == "ok":
            fb = data.get("feedback", {})
            rep_count = fb.get("rep_count", 0)
            score = fb.get("score", 0)
            msg = fb.get("message", "")
            results.append({"rep_count": rep_count, "score": score, "message": msg})
            if rep_count > 0 and (len(results) == 1 or results[-2]["rep_count"] != rep_count):
                print(f"  [REP #{rep_count}] frame={i}  score={score}  msg={msg[:40]}")

    ws.close()

    # 검증
    final = results[-1] if results else {}
    final_reps = final.get("rep_count", 0)
    final_score = final.get("score", 0)
    all_scores = [r["score"] for r in results]

    print(f"\n{'='*50}")
    print(f"  최종 rep_count : {final_reps}")
    print(f"  최종 score     : {final_score}")
    print(f"  score 범위     : {min(all_scores)} ~ {max(all_scores)}")
    print(f"  총 프레임      : {len(results)}")

    ok = True
    if final_reps < 2:
        print(f"  [FAIL] rep_count={final_reps} (기대: 2 이상)")
        ok = False
    else:
        print(f"  [PASS] rep 감지 OK")

    if not (0 <= final_score <= 100):
        print(f"  [FAIL] score 범위 오류: {final_score}")
        ok = False
    else:
        print(f"  [PASS] score 범위 OK")

    if not final.get("message"):
        print(f"  [FAIL] feedback.message 없음")
        ok = False
    else:
        print(f"  [PASS] message: {final['message'][:50]}")

    print(f"{'='*50}")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    ok = run_test(args.port)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
