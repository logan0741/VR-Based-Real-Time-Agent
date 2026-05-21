"""
Pipeline Test: 전체 시스템 컴포넌트 검증

테스트 항목:
  1. Python 의존성 확인
  2. DB 연결 및 테이블 확인
  3. SMPL-X 모델 로딩 확인
  4. WebSocket 왕복 테스트 (서버가 실행 중이어야 함)
  5. Unity 전송 포맷 출력

실행:
    # 서버 실행 후:
    python final/pipeline_test.py
    python final/pipeline_test.py --no-ws   # WebSocket 테스트 건너뜀
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def check(name: str, ok: bool, detail: str = "") -> bool:
    status = "✅" if ok else "❌"
    print(f"  {status} {name}" + (f" — {detail}" if detail else ""))
    return ok


def test_dependencies() -> bool:
    print("\n[1] 의존성 확인")
    results = []
    for pkg in ["torch", "fastapi", "uvicorn", "mediapipe", "cv2", "websockets", "pymysql", "smplx", "numpy"]:
        try:
            __import__(pkg)
            results.append(check(pkg, True))
        except ImportError:
            results.append(check(pkg, False, "pip install 필요"))
    return all(results)


def test_db() -> bool:
    print("\n[2] DB 연결 확인")
    try:
        import pymysql
        env_path = PROJECT_ROOT / ".env"
        db_name = "vr_user_db"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("DB_NAME="):
                    db_name = line.split("=", 1)[1].strip()

        conn = pymysql.connect(
            host="127.0.0.1", port=3306, user="root", password="",
            database=db_name, charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )
        with conn:
            with conn.cursor() as cur:
                cur.execute("SHOW TABLES LIKE 'exercise_sessions'")
                table_exists = cur.fetchone() is not None
                cur.execute("SELECT COUNT(*) as cnt FROM exercise_sessions") if table_exists else None
                count = cur.fetchone()["cnt"] if table_exists else 0

        check("MySQL 연결", True, f"database={db_name}")
        check("exercise_sessions 테이블", table_exists, f"저장된 세션: {count}개")
        return table_exists
    except Exception as exc:
        check("MySQL 연결", False, str(exc))
        return False


def test_smplx_model() -> bool:
    print("\n[3] SMPL-X 모델 확인")
    model_path = PROJECT_ROOT / "smplx_locked_head" / "neutral" / "model.npz"
    check("model.npz 존재", model_path.exists(), str(model_path))
    if not model_path.exists():
        return False
    try:
        os.environ["FITTER_BACKEND"] = "optimization"
        os.environ["SMPLX_MODEL_PATH"] = str(model_path)
        os.environ["USE_CUDA"] = "false"
        from model_3d.fitter import OptimizationPoseFitter
        fitter = OptimizationPoseFitter()
        check("OptimizationPoseFitter 로딩", True, f"device={fitter.device}")
        return True
    except Exception as exc:
        check("OptimizationPoseFitter 로딩", False, str(exc))
        return False


async def test_websocket() -> bool:
    print("\n[4] WebSocket 왕복 테스트")
    try:
        import websockets
        kpts = [[0.3 + i * 0.01, 0.5, 0.9] for i in range(17)]
        t0 = time.perf_counter()
        async with websockets.connect("ws://127.0.0.1:8000/ws/pose") as ws:
            await ws.send(json.dumps({"data_type": "keypoints", "frame_id": "test", "payload": kpts}))
            raw = await asyncio.wait_for(ws.recv(), timeout=30)
            elapsed = (time.perf_counter() - t0) * 1000
            data = json.loads(raw)

        fit = data.get("fit", {})
        ok = data.get("status") == "ok"
        check("서버 응답", ok, f"{elapsed:.0f}ms")
        check("fit.backend", True, fit.get("backend", "없음"))
        check("global_orient (3값)", len(fit.get("global_orient", [])) == 3,
              str([round(v, 3) for v in fit.get("global_orient", [])]))
        check("body_pose (63값)", len(fit.get("body_pose", [])) == 63)
        check("joints_3d (17×3)", len(fit.get("joints_3d", [])) == 17)
        check("feedback.muscle_fatigue", "muscle_fatigue" in data.get("feedback", {}))
        check("keypoints_2d echo", "keypoints_2d" in data)

        print("\n  [Unity 전송 포맷 샘플]")
        print(f"  global_orient : {[round(v,4) for v in fit.get('global_orient', [])]}")
        print(f"  body_pose[0:6]: {[round(v,4) for v in fit.get('body_pose', [])[:6]]}")
        print(f"  inference_ms  : {data.get('debug', {}).get('inference_ms')}ms")

        return ok
    except Exception as exc:
        check("WebSocket 연결", False, str(exc))
        print("  → 서버가 실행 중인지 확인: python final/pipeline_full.py")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline component test")
    parser.add_argument("--no-ws", action="store_true", help="WebSocket 테스트 건너뜀")
    args = parser.parse_args()

    print("=" * 55)
    print("  VR PT — Pipeline Test")
    print("=" * 55)

    results = [
        test_dependencies(),
        test_db(),
        test_smplx_model(),
    ]

    if not args.no_ws:
        results.append(asyncio.run(test_websocket()))

    passed = sum(results)
    total = len(results)
    print(f"\n{'=' * 55}")
    print(f"  결과: {passed}/{total} 통과")
    if passed == total:
        print("  ✅ 모든 테스트 통과")
    else:
        print("  ❌ 실패 항목 확인 필요")
    print("=" * 55)
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
