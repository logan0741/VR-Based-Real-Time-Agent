# 01 — PoseEstimator

## 책임

MoveNet Lightning 모델을 로드하고, 단일 프레임에서 17개 관절 좌표를 추출한다.
전문가 영상과 웹캠 프레임 양쪽에서 공유 사용된다.

---

## 구현 파일

- `backend/pose_estimator.py`
- `backend/utils/keypoints.py` — 관절 인덱스 상수 + 스켈레톤 연결 쌍 정의 (이 단계에서 함께 작성)

---

## 입출력 스펙

| 항목 | 내용 |
|------|------|
| 입력 | 이미지 프레임, shape `(H, W, 3)`, dtype `uint8` |
| 출력 | 관절 좌표, shape `(17, 3)`, dtype `float32` |
| 출력 형식 | 각 행: `[y, x, confidence]` — MoveNet 원본 순서 유지 |
| 모델 | MoveNet Lightning (tensorflow-hub) |

**주의**: 출력 좌표 순서가 `[y, x]`로 OpenCV의 `[x, y]`와 반대임.

---

## 완료 기준

전문가 영상에서 첫 프레임을 읽어 아래 테스트가 통과하면 완료.

```python
import cv2
import numpy as np
from backend.pose_estimator import PoseEstimator

cap = cv2.VideoCapture("assets/expert_videos/squat.mp4")
ret, frame = cap.read()
cap.release()

estimator = PoseEstimator()
estimator.load()
keypoints = estimator.predict(frame)

assert keypoints.shape == (17, 3), f"shape 오류: {keypoints.shape}"
assert keypoints.dtype == np.float32, f"dtype 오류: {keypoints.dtype}"
print("PoseEstimator 테스트 통과")
```
