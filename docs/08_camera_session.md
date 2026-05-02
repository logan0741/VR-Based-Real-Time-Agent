# 07 — CameraSession

## 책임

내장 카메라에서 프레임을 직접 캡처하고, 01~06 파이프라인을 순서대로 실행하여 결과 dict를 UIRenderer로 전달한다.
세션 시작·종료를 키보드로 제어하며, 캡처 → PoseEstimator → PoseNormalizer 구간의 FPS를 측정한다.

---

## 파이프라인 실행 순서

프레임 캡처 → PoseEstimator → PoseNormalizer → (시퀀스 누적) → DTWComparator → RepDetector → ScoreEngine → UIRenderer

---

## 입출력 스펙

| 항목 | 내용 |
|------|------|
| 입력 | 내장 카메라 (`cv2.VideoCapture(0)`) |
| 출력 | 파이프라인 결과 dict (CLAUDE.md 인터페이스 규칙 참조) |

### 세션 동작
- **시작**: `s` 키 입력 → 카메라 열기 + 파이프라인 초기화 + 회차 점수 목록 초기화
- **종료**: `q` 키 입력 → 카메라 해제 + 최종 회차 점수 출력

### 사용자 시퀀스 윈도우 관리
파이프라인 실행 직전, 누적된 사용자 시퀀스를 최근 `n_frames`로 슬라이싱하여 DTWComparator에 전달한다.

### FPS 측정 범위
프레임 캡처 → PoseEstimator → PoseNormalizer 구간의 처리 속도를 초당 프레임 수로 계산하여 결과 dict의 `fps` 필드로 전달한다.

### 전문가 영상 반복 재생
앱 시작 시 전문가 영상 전체 프레임을 메모리에 로드한다.
매 프레임마다 순서대로 접근하며, 끝나면 처음으로 돌아간다.

---

## 완료 기준

`s` 키로 세션 시작 후 OpenCV 윈도우에 결과가 표시되고, `q` 키로 정상 종료되며, 결과 dict에 `keypoints`, `score`, `rep_scores`, `fps` 필드가 모두 포함되는지 확인.
