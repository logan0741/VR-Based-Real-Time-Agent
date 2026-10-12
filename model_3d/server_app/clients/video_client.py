import asyncio
import json
import time
import argparse
import sys
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

async def main(video_path):
    print(f"Connecting to {SERVER_URL}...")
    
    mp_pose = mp.solutions.pose
    pose = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"❌ 동영상을 열 수 없습니다! 파일 경로를 다시 확인해주세요: {video_path}")
        print("사용법: python video_client.py --video \"내동영상영상.mp4\"")
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    if not fps or fps < 1:
        fps = 30.0
    frame_delay = 1.0 / fps

    print(f"✅ [{video_path}] 로드 완료! (재생 속도: {fps:.1f} FPS)")
    print("분석 시작! 원본 영상 화면과 Unity 아바타를 비교해 보세요. (종료: 영상 클릭 후 'q' 입력)")

    async with websockets.connect(SERVER_URL, ping_interval=None) as ws:
        # 백그라운드 소비용 루프 (에러 방지)
        async def consume_messages():
            try:
                while True:
                    await ws.recv()
            except Exception:
                pass
        asyncio.create_task(consume_messages())

        frame_idx = 0
        
        while cap.isOpened():
            start_time = time.time()
            ret, frame = cap.read()
            if not ret:
                print("\n영상이 끝났습니다.")
                break

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = pose.process(rgb_frame)

            if results.pose_landmarks:
                landmarks = results.pose_landmarks.landmark
                
                # 원본 비디오 데이터 수집
                w_orig = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                h_orig = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                
                # --- AI 모델(FastMLP)을 위한 스케일 정규화(Normalization) 트릭 ---
                # 1. 사람의 핵심이 되는 양쪽 골반(Hip) 좌표를 찾아 무게중심(Center) 계산
                left_hip = landmarks[23]
                right_hip = landmarks[24]
                center_x = (left_hip.x + right_hip.x) / 2.0
                center_y = (left_hip.y + right_hip.y) / 2.0
                
                # 2. 어깨(Shoulder)와 골반(Hip)의 거리를 측정하여 사람의 크기 스케일 파악
                left_shoulder = landmarks[11]
                torso_height = abs((left_hip.y + right_hip.y)/2.0 - (left_shoulder.y + landmarks[12].y)/2.0)
                
                # 모델이 학습될 때 예상했던 평균 Torso 크기(픽셀)를 맞추기 위한 비율 계산
                # (훈련 데이터 1920x1080 환경에서 사람의 가슴-골반 길이는 대략 350~450 픽셀이었음)
                TARGET_TORSO = 400.0
                actual_torso_pixel = torso_height * h_orig
                scale_factor = TARGET_TORSO / max(actual_torso_pixel, 1.0)
                
                payload = []
                for mp_idx in MP_TO_COCO:
                    lm = landmarks[mp_idx]
                    
                    # 3. 모델이 좋아하는 좌표계로 조작 (Translation & Scaling)
                    # MediaPipe 비율좌표 -> 골반 중심(0,0) 이동 -> 스케일 뻥튀기 -> 모델이 훈련때 보던 가상의 중앙(960, 540)으로 전송
                    shifted_x = (lm.x - center_x) * w_orig * scale_factor
                    shifted_y = (lm.y - center_y) * h_orig * scale_factor
                    
                    # 최종 좌표: 모델이 기대하는 1920x1080 화면 정중앙 (960, 540) 부근에 위치시킴
                    final_x = shifted_x + 960.0
                    final_y = shifted_y + 540.0
                    
                    # Z축 좌표: 골반(Z=0) 기준으로 깊이값 정규화 
                    final_z = lm.z * w_orig * scale_factor

                    payload.append([final_x, final_y, final_z])

                msg = {
                    "data_type": "keypoints",
                    "frame_id": f"video-{frame_idx}",
                    "payload": payload
                }
                
                # 서버로 전송 (FastMLP를 거쳐 Unity로 즉각 브로드캐스트)
                await ws.send(json.dumps(msg))

                # 발표용 시각화 (원본 영상 위에 뼈대 그리기)
                mp.solutions.drawing_utils.draw_landmarks(
                    frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)

            # 영상 띄우기
            cv2.imshow('Original Video to Avatar (Press q to exit)', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
            frame_idx += 1
            
            # 동영상 배속을 원래 속도(1배속)에 맞추기 위한 대기 로직
            elapsed = time.time() - start_time
            sleep_time = frame_delay - elapsed
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            else:
                await asyncio.sleep(0.001)

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract video pose and send to Unity")
    parser.add_argument("--video", type=str, default="sample_video.mp4", help="Path to your MP4 video file")
    args = parser.parse_args()
    
    try:
        asyncio.run(main(args.video))
    except KeyboardInterrupt:
        print("\n스트리밍 종료.")
