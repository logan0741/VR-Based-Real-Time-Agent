# CONTEXT.md — 프로젝트 맥락

## 프로젝트 개요

노트북 내장 카메라로 사용자의 운동 영상을 실시간으로 촬영하고, 사전 준비된 전문가 영상과 비교하여 0~100점으로 채점하는 PT 보조 프로그램.

- 첫 번째 지원 운동: 스쿼트 (이후 종목 추가 예정)
- 피드백 모듈: 현재 구현 범위 밖 — 점수 산출까지만 구현
- 실행: `uv run python main.py` → OpenCV 윈도우 출력

---

## 데이터 흐름

```
전문가 영상 (파일)          사용자 내장 카메라 (실시간)
      ↓                        ↓
 VideoLoader           cv2.VideoCapture(0)
      ↓                        ↓
      └──── PoseEstimator ─────┘
                  ↓
            PoseNormalizer
             ↙         ↘
   ExpertPoseCache    사용자 정규화 시퀀스
             ↘         ↙
           DTWComparator
                  ↓
            RepDetector
                  ↓
            ScoreEngine
                  ↓
           UIRenderer (OpenCV 윈도우)
```

---

## 운동 종목 확장 구조

종목 설정은 `backend/config.py`에서 딕셔너리로 관리한다. 종목 추가 시 이 파일만 수정한다.

종목별 필드:
- `video_path` — 전문가 영상 경로
- `normalizer_type` — 촬영 방향: `"front"` / `"side_left"` / `"side_right"`
- `keypoints_used` — DTW 비교에 사용할 관절 인덱스 목록
- `weights` — 관절별 점수 가중치 (동일 가중치는 모두 1.0)
- `target_fps` — 전문가 영상 샘플링 및 사용자 처리 목표 fps
- `n_frames` — 실시간 점수 산출에 사용할 프레임 수 (CameraSession에서 윈도우 슬라이싱에도 사용)
- `max_distance` — 선형 변환 기준 최대 거리 (이 값 이상이면 0점)
- `rep_detector_type` — 운동 1회 감지 방법
- `norm_buffer_size` — 정규화 기준값 평활화 버퍼 크기
- `rep_slope_window` — 1회 감지용 기울기 계산 윈도우 프레임 수 (초기값 5였으나 노이즈로 15로 조정)
- `min_rep_frames` — 유효 rep 최소 프레임 수 (미만이면 노이즈로 버림)

---

## 영상 파일 목록

| 경로 | 내용 |
|------|------|
| `assets/expert_videos/squat_full.mp4` | 스쿼트 4회 전문가 영상 — config `video_path` 기본값 |
| `assets/expert_videos/squat.mp4` | 스쿼트 1회 전문가 영상 |
| `assets/test_videos/test_squat.mp4` | 스쿼트 4회 테스트 영상 |

---

## 구현 순서

| 단계 | 파일 | 모듈 | 상태 |
|------|------|------|------|
| 01 | `docs/01_pose_estimator.md` | PoseEstimator | 완료 |
| 02 | `docs/02_pose_normalizer.md` | PoseNormalizer | 완료 |
| 03 | `docs/03_expert_cache.md` | ExpertPoseCache | 완료 |
| 04 | `docs/04_dtw_comparator.md` | DTWComparator | 완료 |
| 05 | `docs/05_rep_detector.md` | RepDetector | 완료 |
| 06 | `docs/06_score_engine.md` | ScoreEngine | 완료 |
| 07 | `docs/07_ui_renderer.md` | UIRenderer | **미작성** |
| 08 | `docs/08_camera_session.md` | CameraSession | **미작성** |

---

## 주요 설계 결정 (구현 과정 확정)

- MoveNet 출력 좌표 순서: `[y, x]` — OpenCV의 `[x, y]`와 반대
- 정규화 기준 관절은 `normalizer_type`으로 고정 — 세션 중 기준 변경 없음
- PoseEstimator는 앱 시작 시 1회 로드 후 ExpertPoseCache·CameraSession이 공유 (의존성 주입)
- ExpertPoseCache는 내부에서 별도 PoseNormalizer 인스턴스 생성 — 세션용 인스턴스와 버퍼 분리
- 실시간 사용자 시퀀스 윈도우 슬라이싱(`n_frames`)은 07단계 CameraSession에서 담당
- 카메라는 07단계(CameraSession)에서 처음 연결 — 01~06단계 테스트는 전문가 영상 사용
- RepDetector 감지 신호: 힙 y가 아닌 **무릎 y** (정규화 후 힙은 항상 원점이라 신호 없음)
- RepDetector 경계: valley+peak 상태 머신 — WAIT_VALLEY → WAIT_PEAK, peak에서 rep 기록
- 마지막 rep 처리: WAIT_PEAK 상태에서 시퀀스 종료 시 자동 마감 (마지막 상승 후 앉지 않아도 기록)

---

## 테스트 실행 방법

```bash
PYTHONPATH=. uv run python tests/test_XXX.py
```

---

## 미결 사항 (TODO.md 참조)

- 점수 보정 (`max_distance`, `weights`) — 08단계 완성 후 실제 환경에서 조정
- 방향 포함 차이 행렬 (`diff_matrix`) — 피드백 단계에서 DTWComparator 확장
