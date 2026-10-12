"""
MP4에서 MediaPipe로 2D keypoints를 추출하여 expert JSON으로 저장.
저장된 JSON을 서버가 /api/expert-smplx에서 MLP에 통과시켜 강사 SMPL-X 파라미터 생성.
"""

import cv2
import json
import sys
import mediapipe as mp

MP_TO_COCO = [
    0,   # Nose
    2,   # Left Eye
    5,   # Right Eye
    7,   # Left Ear
    8,   # Right Ear
    11,  # Left Shoulder
    12,  # Right Shoulder
    13,  # Left Elbow
    14,  # Right Elbow
    15,  # Left Wrist
    16,  # Right Wrist
    23,  # Left Hip
    24,  # Right Hip
    25,  # Left Knee
    26,  # Right Knee
    27,  # Left Ankle
    28,  # Right Ankle
]

def extract(video_path: str, out_path: str, sample_every: int = 2):
    mp_pose = mp.solutions.pose
    pose = mp_pose.Pose(
        static_image_mode=False,
        min_detection_confidence=0.4,
        min_tracking_confidence=0.4,
    )

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"[ERROR] 파일을 열 수 없음: {video_path}")
        sys.exit(1)

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    print(f"[INFO] {video_path}  {w:.0f}x{h:.0f}  {fps:.1f}fps  {total}frames")

    frames = []
    idx = 0
    detected = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        if idx % sample_every != 0:
            idx += 1
            continue

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res = pose.process(rgb)

        if res.pose_landmarks:
            lms = res.pose_landmarks.landmark

            # video_client.py와 동일한 좌표 변환 (MLP 학습 시 입력 형식)
            lh, rh = lms[23], lms[24]
            ls, rs = lms[11], lms[12]
            center_x = (lh.x + rh.x) / 2.0
            center_y = (lh.y + rh.y) / 2.0
            torso_h = abs((lh.y + rh.y) / 2.0 - (ls.y + rs.y) / 2.0)
            TARGET_TORSO = 400.0
            actual_torso_px = torso_h * h
            scale = TARGET_TORSO / max(actual_torso_px, 1.0)

            kp = []
            for mp_idx in MP_TO_COCO:
                lm = lms[mp_idx]
                x = (lm.x - center_x) * w * scale + 960.0
                y = (lm.y - center_y) * h * scale + 540.0
                z = lm.z * w * scale
                kp.append([x, y, z])

            frames.append(kp)
            detected += 1

        idx += 1
        if idx % 100 == 0:
            print(f"  {idx}/{total} frames processed, {detected} detected...", end="\r")

    cap.release()
    print(f"\n[INFO] 완료: {detected}프레임 추출 → {out_path}")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(frames, f)

    print(f"[INFO] 저장 완료: {len(frames)}프레임")


if __name__ == "__main__":
    video = r"스쿼트 데이터 셋.mp4"
    out   = "squat_expert_keypoints.json"
    extract(video, out, sample_every=2)  # 2프레임마다 1개 (fps/2)
