# 08 — UIRenderer

## 책임

CameraSession에서 전달받은 결과 dict를 바탕으로 전문가 영상·사용자 카메라 프레임에 스켈레톤을 오버레이하고,
점수와 FPS를 OpenCV 윈도우에 표시한다.

---

## UI 구성

| 위치 | 내용 |
|------|------|
| 왼쪽 | 전문가 영상 프레임 + 스켈레톤 오버레이 (독립 반복 재생) |
| 가운데 | 실시간 점수, 최근 5회 점수 목록, FPS |
| 오른쪽 | 웹캠 실시간 프레임 + 스켈레톤 오버레이 |

세 영역을 가로로 이어붙여(`np.hstack`) 단일 `cv2.imshow()` 윈도우로 출력한다.

---

## 스켈레톤 렌더링 규칙

### 관절 색상 구분 (BGR)
| 구분 | 관절 | 색상 |
|------|------|------|
| 중앙 | NOSE, LEFT_EYE, RIGHT_EYE, LEFT_EAR, RIGHT_EAR | 흰색 |
| 좌 | LEFT_SHOULDER, LEFT_ELBOW, LEFT_WRIST, LEFT_HIP, LEFT_KNEE, LEFT_ANKLE | 초록색 |
| 우 | RIGHT_SHOULDER, RIGHT_ELBOW, RIGHT_WRIST, RIGHT_HIP, RIGHT_KNEE, RIGHT_ANKLE | 파란색 |

### 신뢰도 3단계 투명도 (cv2.addWeighted overlay 방식)
| 단계 | confidence 범위 | alpha |
|------|----------------|-------|
| 낮음 | 0.0 ~ 0.3 미만 | 0.3 |
| 중간 | 0.3 ~ 0.6 미만 | 0.6 |
| 높음 | 0.6 ~ 1.0 | 1.0 |

### 연결선 규칙
- 연결선 색상: 시작 관절의 색을 따름
- 좌우를 잇는 연결선: 중앙 색(흰색) 사용
- 연결선 투명도: 두 관절 중 낮은 쪽 alpha를 따름
- 연결 쌍 정의: `backend/utils/keypoints.py`의 `SKELETON_EDGES` 참조

---

## 입출력 스펙

| 항목 | 내용 |
|------|------|
| 입력 | 파이프라인 결과 dict (CLAUDE.md 인터페이스 규칙 참조) |
| 입력 | 사용자 카메라 원본 프레임 (shape `(H, W, 3)`, dtype `uint8`) |
| 입력 | 전문가 영상 프레임 버퍼 `list[np.ndarray]` (앱 시작 시 전체 로드) |
| 출력 | `cv2.imshow()` 단일 윈도우 |

---

## 완료 기준

세션 시작 후 전문가 영상과 카메라 영상 양쪽에 스켈레톤이 표시되고, 가운데 패널에 실시간 점수·최근 5회 점수·FPS가 업데이트되는지 확인.
