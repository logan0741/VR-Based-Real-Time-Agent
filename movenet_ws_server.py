"""
capstone Prototype - Python Side
Pipeline: Webcam → MoveNet (TFLite) → Keypoints → WebSocket → Unity

측정 항목:
  - capture_ms   : 웹캠 프레임 캡처 시간
  - infer_ms     : MoveNet 추론 시간
  - send_ms      : WebSocket 송신 시간
  - total_ms     : 전체 파이프라인 1사이클
  - fps          : 실시간 FPS
"""

import asyncio
import json
import time
import cv2
import numpy as np
import websockets
import tensorflow as tf
import urllib.request
import os

# ── 설정 ──────────────────────────────────────────────────────────────────────
WS_HOST = "localhost"
WS_PORT = 8765
MODEL_URL = (
    "https://tfhub.dev/google/lite-model/movenet/singlepose/lightning/tflite/float16/4"
    "?lite-format=tflite"
)
MODEL_PATH = "movenet_lightning.tflite"
INPUT_SIZE = 192  # lightning: 192, thunder: 256

# MoveNet 17 keypoint 이름 (COCO 순서)
KEYPOINT_NAMES = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
]

# Unity Humanoid에 매핑할 관절 (17개 중 주요 관절만)
UNITY_BONE_MAP = {
    "left_shoulder":  "LeftUpperArm",
    "right_shoulder": "RightUpperArm",
    "left_elbow":     "LeftLowerArm",
    "right_elbow":    "RightLowerArm",
    "left_wrist":     "LeftHand",
    "right_wrist":    "RightHand",
    "left_hip":       "LeftUpperLeg",
    "right_hip":      "RightUpperLeg",
    "left_knee":      "LeftLowerLeg",
    "right_knee":     "RightLowerLeg",
    "left_ankle":     "LeftFoot",
    "right_ankle":    "RightFoot",
    "nose":           "Head",
}

# ── 모델 로드 ──────────────────────────────────────────────────────────────────
def load_movenet():
    if not os.path.exists(MODEL_PATH):
        print(f"[INFO] MoveNet 모델 다운로드 중...")
        # TFHub lite model 직접 URL (float16 tflite)
        alt_url = "https://storage.googleapis.com/download.tensorflow.org/models/tflite/movenet/movenet_singlepose_lightning_tflite_float16_4.tflite"
        try:
            urllib.request.urlretrieve(alt_url, MODEL_PATH)
            print(f"[INFO] 모델 저장 완료: {MODEL_PATH}")
        except Exception as e:
            print(f"[ERROR] 모델 다운로드 실패: {e}")
            print("[INFO] 수동 다운로드 후 movenet_lightning.tflite 로 저장해주세요")
            raise

    interpreter = tf.lite.Interpreter(model_path=MODEL_PATH)
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
    print(f"[INFO] MoveNet 로드 완료 | 입력: {input_details[0]['shape']}")
    return interpreter, input_details, output_details


def run_movenet(interpreter, input_details, output_details, frame_rgb):
    """
    Returns: keypoints array shape (17, 3) → [y, x, confidence]
    """
    img = cv2.resize(frame_rgb, (INPUT_SIZE, INPUT_SIZE))
    img = np.expand_dims(img, axis=0).astype(np.uint8)

    # float16 모델은 float32 입력 허용
    interpreter.set_tensor(input_details[0]['index'], img)
    interpreter.invoke()

    keypoints = interpreter.get_tensor(output_details[0]['index'])
    # shape: (1, 1, 17, 3)
    return keypoints[0][0]  # (17, 3)


def keypoints_to_payload(keypoints_raw, frame_h, frame_w, latency: dict):
    """
    keypoints_raw: (17,3) [y_norm, x_norm, confidence]
    → Unity로 보낼 JSON 페이로드 생성
    """
    bones = {}
    keypoints_list = []

    for i, name in enumerate(KEYPOINT_NAMES):
        y_norm, x_norm, conf = keypoints_raw[i]
        # 픽셀 좌표 (디버그용)
        px = float(x_norm * frame_w)
        py = float(y_norm * frame_h)

        kp = {
            "name": name,
            "x": round(px, 2),
            "y": round(py, 2),
            "x_norm": round(float(x_norm), 4),
            "y_norm": round(float(y_norm), 4),
            "confidence": round(float(conf), 3),
        }
        keypoints_list.append(kp)

        if name in UNITY_BONE_MAP and conf > 0.3:
            bones[UNITY_BONE_MAP[name]] = {
                "x_norm": round(float(x_norm), 4),
                "y_norm": round(float(y_norm), 4),
                "confidence": round(float(conf), 3),
            }

    payload = {
        "timestamp_ms": round(time.time() * 1000),
        "latency": latency,
        "keypoints": keypoints_list,
        "bones": bones,  # Unity Humanoid 직결 매핑
    }
    return payload


# ── WebSocket 서버 ─────────────────────────────────────────────────────────────
connected_clients = set()

async def ws_handler(websocket):
    connected_clients.add(websocket)
    client_addr = websocket.remote_address
    print(f"[WS] Unity 클라이언트 연결: {client_addr}")
    try:
        await websocket.wait_closed()
    finally:
        connected_clients.discard(websocket)
        print(f"[WS] Unity 클라이언트 해제: {client_addr}")


async def broadcast(payload_json: str):
    if connected_clients:
        await asyncio.gather(
            *[ws.send(payload_json) for ws in connected_clients],
            return_exceptions=True,
        )


# ── 메인 파이프라인 ────────────────────────────────────────────────────────────
async def capture_loop(interpreter, input_details, output_details):
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERROR] 웹캠을 열 수 없습니다")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)

    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))

    print(f"[CAM] 해상도: {frame_w}x{frame_h}")
    print("[INFO] 파이프라인 시작. q 누르면 종료")

    # latency 통계용
    stats = {"capture": [], "infer": [], "send": [], "total": []}
    frame_count = 0
    fps_timer = time.time()

    while True:
        t0 = time.perf_counter()

        # ── 1. 웹캠 캡처 ───────────────────────────────────────
        t_cap_start = time.perf_counter()
        ret, frame_bgr = cap.read()
        t_cap_end = time.perf_counter()
        if not ret:
            break

        capture_ms = (t_cap_end - t_cap_start) * 1000

        # ── 2. MoveNet 추론 ────────────────────────────────────
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        t_inf_start = time.perf_counter()
        keypoints_raw = run_movenet(interpreter, input_details, output_details, frame_rgb)
        t_inf_end = time.perf_counter()
        infer_ms = (t_inf_end - t_inf_start) * 1000

        # ── 3. 페이로드 생성 ───────────────────────────────────
        latency_info = {
            "capture_ms": round(capture_ms, 2),
            "infer_ms":   round(infer_ms, 2),
        }
        payload = keypoints_to_payload(keypoints_raw, frame_h, frame_w, latency_info)

        # ── 4. WebSocket 송신 ──────────────────────────────────
        t_send_start = time.perf_counter()
        payload_json = json.dumps(payload)
        await broadcast(payload_json)
        t_send_end = time.perf_counter()
        send_ms = (t_send_end - t_send_start) * 1000

        t1 = time.perf_counter()
        total_ms = (t1 - t0) * 1000

        # latency 업데이트
        payload["latency"]["send_ms"]  = round(send_ms, 2)
        payload["latency"]["total_ms"] = round(total_ms, 2)

        # 통계 누적
        stats["capture"].append(capture_ms)
        stats["infer"].append(infer_ms)
        stats["send"].append(send_ms)
        stats["total"].append(total_ms)
        frame_count += 1

        # ── 5. 시각화 (OpenCV 창) ──────────────────────────────
        draw_frame = frame_bgr.copy()
        for kp in payload["keypoints"]:
            if kp["confidence"] > 0.3:
                cv2.circle(draw_frame, (int(kp["x"]), int(kp["y"])), 5, (0, 255, 0), -1)

        # FPS 계산
        elapsed = time.time() - fps_timer
        if elapsed >= 1.0:
            fps = frame_count / elapsed
            frame_count = 0
            fps_timer = time.time()

            # 콘솔 latency 출력
            def avg(lst): return sum(lst[-30:]) / len(lst[-30:]) if lst else 0
            print(
                f"[LATENCY] FPS={fps:.1f} | "
                f"capture={avg(stats['capture']):.1f}ms | "
                f"infer={avg(stats['infer']):.1f}ms | "
                f"send={avg(stats['send']):.1f}ms | "
                f"total={avg(stats['total']):.1f}ms"
            )
        else:
            fps = 0

        cv2.putText(draw_frame,
            f"infer:{infer_ms:.1f}ms total:{total_ms:.1f}ms",
            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)

        cv2.imshow("KKLL - MoveNet Prototype", draw_frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

        # asyncio에 제어권 양보
        await asyncio.sleep(0)

    cap.release()
    cv2.destroyAllWindows()

    # 최종 통계 출력
    print("\n── 최종 latency 통계 ──────────────────────────")
    for key, vals in stats.items():
        if vals:
            print(f"  {key:10s}: avg={np.mean(vals):.2f}ms  "
                  f"min={np.min(vals):.2f}ms  max={np.max(vals):.2f}ms  "
                  f"p95={np.percentile(vals, 95):.2f}ms")


async def main():
    print("[INFO] MoveNet 모델 로드 중...")
    interpreter, input_details, output_details = load_movenet()

    print(f"[WS] 서버 시작: ws://{WS_HOST}:{WS_PORT}")
    ws_server = await websockets.serve(ws_handler, WS_HOST, WS_PORT)

    try:
        await capture_loop(interpreter, input_details, output_details)
    finally:
        ws_server.close()
        await ws_server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
