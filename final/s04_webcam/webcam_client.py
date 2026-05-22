import asyncio
import json
import time
import cv2
import mediapipe as mp
import websockets

# MediaPipe to COCO 17 Mapping
MP_TO_COCO = [
    0,   # 0: Nose (MP 0)
    2,   # 1: Left Eye (MP 2)
    5,   # 2: Right Eye (MP 5)
    7,   # 3: Left Ear (MP 7)
    8,   # 4: Right Ear (MP 8)
    11,  # 5: Left Shoulder (MP 11)
    12,  # 6: Right Shoulder (MP 12)
    13,  # 7: Left Elbow (MP 13)
    14,  # 8: Right Elbow (MP 14)
    15,  # 9: Left Wrist (MP 15)
    16,  # 10: Right Wrist (MP 16)
    23,  # 11: Left Hip (MP 23)
    24,  # 12: Right Hip (MP 24)
    25,  # 13: Left Knee (MP 25)
    26,  # 14: Right Knee (MP 26)
    27,  # 15: Left Ankle (MP 27)
    28,  # 16: Right Ankle (MP 28)
]

SERVER_URL = "ws://127.0.0.1:8000/ws/pose"

async def main():
    print(f"Connecting to {SERVER_URL}...")

    mp_pose = mp.solutions.pose
    pose = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5, model_complexity=0)
    cap = cv2.VideoCapture(0)  # 웹캠 0번 켜기

    if not cap.isOpened():
        print("웹캠을 찾을 수 없습니다!")
        return

    print("웹캠이 켜졌습니다. Unity와 실시간 연동을 시작합니다. (종료: 웹캠 화면에서 'q' 또는 터미널에서 Ctrl+C)")

    async with websockets.connect(SERVER_URL) as ws:
        # session_start: 서버가 exercise별 preprocessing 세션을 초기화하도록 알림
        await ws.send(json.dumps({
            "data_type": "session_start",
            "user_id": "webcam_user",
            "exercise_type": "squat",
        }))

        frame_idx = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            # BGR -> RGB 변환
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = pose.process(rgb_frame)

            if results.pose_landmarks:
                landmarks = results.pose_landmarks.landmark

                # Payload: 서버 KEYPOINT_FORMAT=movenet_yx → [y, x, conf] 순서
                payload = []
                for mp_idx in MP_TO_COCO:
                    lm = landmarks[mp_idx]
                    payload.append([lm.y, lm.x, lm.visibility])

                # JSON 전송
                msg = {
                    "data_type": "keypoints",
                    "frame_id": f"webcam-{frame_idx}",
                    "payload": payload
                }

                await ws.send(json.dumps(msg))

                # 골격 그리기 (MediaPipe 기본 제공 유틸리티 대신 직접 표시)
                mp.solutions.drawing_utils.draw_landmarks(
                    frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)

            # 웹캠 화면 피드백
            cv2.imshow('Real-Time Avatar Camera', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

            frame_idx += 1

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    asyncio.run(main())
