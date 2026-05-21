"""Stage 04: 웹캠 + 서버 WebSocket 연결 테스트"""
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SERVER_URL = "ws://127.0.0.1:8000/ws/pose"
TEST_KPTS = [[0.3 + i * 0.02, 0.5, 0.9] for i in range(17)]

async def test_websocket():
    try:
        import websockets
    except ImportError:
        print("[SKIP] websockets 미설치. pip install websockets")
        return

    print(f"  서버 {SERVER_URL} 에 연결 시도...")
    try:
        async with websockets.connect(SERVER_URL, open_timeout=3) as ws:
            await ws.send(json.dumps({
                "data_type": "keypoints",
                "frame_id": "test_0",
                "payload": TEST_KPTS,
            }))
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            assert resp.get("status") == "ok", f"응답 오류: {resp}"
            fb = resp.get("feedback", {})
            print(f"[OK] WebSocket 연결 및 응답 확인")
            print(f"     score={fb.get('score')}  label={fb.get('label')}")
    except Exception as e:
        print(f"[FAIL] 연결 실패: {e}")
        print("       02_test_backend.py 또는 07_pipeline_web.py 로 서버를 먼저 시작하세요.")

def test_webcam_import():
    try:
        import cv2, mediapipe
        print("[OK] cv2 + mediapipe 임포트")
    except ImportError as e:
        print(f"[WARN] {e} — pip install opencv-python mediapipe")

if __name__ == "__main__":
    print("=" * 50)
    print("  Stage 04: 웹캠 + WebSocket 테스트")
    print("=" * 50)
    test_webcam_import()
    asyncio.run(test_websocket())
    print("\n[DONE] Stage 04 테스트 완료")
