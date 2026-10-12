# VR PT 프로젝트 인계 문서

최종 업데이트: 2026-05-21

---

## 현재 상태 요약

**목표**: 외부 웹캠으로 운동 자세 촬영 → 2D 포즈 추정 → 3D 리프팅 → SMPL-X 아바타(Unity VR + 웹 뷰어) 실시간 자세 피드백

**현재 동작 가능한 것**:
- `final/07_pipeline_web.py` 실행 → FastAPI 서버 + 2D 웹 뷰어 (브라우저에서 웹캠 연결 가능)
- 브라우저에서 TF.js MoveNet으로 웹캠 포즈 캡처 → WebSocket → 서버 → 피드백 표시
- MySQL DB 연결 정상 (`vr_user_db`)
- Stage별 독립 테스트 스크립트 모두 통과

---

## final/ 폴더 구조 (현재 활성 코드)

```
final/
├── s01_preprocessing/     # 전처리 (전처리 개발자 코드 통합)
│   ├── utils/keypoints.py     # COCO-17 관절 인덱스 상수
│   ├── config.py              # 종목별 운동 설정 딕셔너리
│   ├── pose_normalizer.py     # 체형 정규화 (hip 기준)
│   ├── rep_detector.py        # 반복 동작 횟수 감지 (slope sign-change)
│   ├── dtw_comparator.py      # DTW로 사용자 vs 전문가 비교
│   ├── score_engine.py        # DTW 거리 → 0-100 점수 변환
│   └── expert_cache.py        # 전문가 영상 정규화 시퀀스 캐시
│
├── s02_backend/           # FastAPI 서버 + 추론
│   ├── server.py              # 메인 서버 (WebSocket /ws/pose, 뷰어 서빙)
│   ├── pose_retargeting.py    # OneEuro + 속도 클램핑 스무딩
│   ├── posture_analyzer.py    # 관절 각도 + 근육 피로 분석
│   └── config.py              # .env 로더
│
├── s03_database/          # MySQL 세션 저장
│   └── database.py            # DatabaseSettings, ExerciseSessionRepository
│
├── s04_webcam/            # 외부 웹캠 클라이언트 (서버와 별도 터미널)
│   └── webcam_client.py       # MediaPipe → COCO-17 → WebSocket 전송
│
├── s05_frontend/          # 2D 웹 뷰어 (브라우저 직접 실행 가능)
│   ├── index.html             # TF.js MoveNet 웹캠 캡처 포함
│   ├── viewer.js              # WebSocket 수신 → Canvas 스켈레톤 + 피드백
│   └── style.css
│
├── s06_unity_vr/          # Unity C# 스크립트 (Unity 프로젝트에 수동 추가)
│   ├── FitnessAvatarController.cs   # SMPL-X 본 적용 (axis-angle → 좌표계 변환)
│   └── WebSocketClient.cs           # Unity ↔ FastAPI 연결
│
├── 01_test_preprocessing.py   # Stage 01 독립 테스트
├── 02_test_backend.py         # Stage 02 독립 테스트
├── 03_test_database.py        # Stage 03 독립 테스트
├── 04_test_webcam.py          # Stage 04 독립 테스트 (서버 실행 중일 때)
├── 07_pipeline_web.py         # 전체 파이프라인 실행 (웹 전용)
└── 08_pipeline_full.py        # 전체 파이프라인 실행 (Unity 포함)
```

> `final/backend/`, `final/client/`, `final/frontend/`, `final/unity/` 는 구버전 폴더 (삭제 예정)

---

## 실행 방법

### 1. 서버 시작
```powershell
cd C:\Project\VR-Based-Real-Time-Agent
python final/07_pipeline_web.py
# 접속: http://localhost:8000/viewer/
# Quest 3: http://<PC_IP>:8000/viewer/
```

### 2. 웹캠 클라이언트 (별도 터미널, 선택)
```powershell
python -m final.s04_webcam.webcam_client
# 또는 브라우저에서 직접 웹캠 버튼 클릭
```

### 3. Stage별 테스트
```powershell
python final/01_test_preprocessing.py   # 전처리 모듈 테스트
python final/02_test_backend.py         # 백엔드 모듈 테스트
python final/03_test_database.py        # DB 연결 테스트
python final/04_test_webcam.py          # WebSocket 연결 테스트 (서버 켜야 함)
```

---

## 핵심 기술 정보

### WebSocket 프로토콜
- **엔드포인트**: `ws://host:8000/ws/pose`
- **클라이언트 → 서버**: `{"data_type": "keypoints", "frame_id": "cam_N", "payload": [[y,x,conf]×17]}`
- **서버 → 클라이언트**: `{"status": "ok", "fit": {"global_orient": [3], "body_pose": [63]}, "feedback": {"score": 0-100, "label": "...", "details": {...}}}`

### 관절 좌표 포맷
- COCO-17, shape `(17, 3)`, 각 행 `[y, x, confidence]`, 정규화 0-1
- 환경변수: `KEYPOINT_FORMAT=movenet_yx`

### 백엔드 모드
- `FITTER_BACKEND=lifter`: PoseLifterMLP (~5ms, 웹캠 실시간용, 현재 기본값)
- `FITTER_BACKEND=optimization`: SMPL-X Adam 피팅 (~540ms, Unity 고정밀용)

### 좌표계
- SMPL-X: right-handed, axis-angle 포맷 (방향=회전축, 크기=라디안)
- Unity: left-handed, `FitnessAvatarController.cs`에서 X축 flip 처리

---

## 환경 설정 (.env 핵심 항목)

```bash
FITTER_BACKEND=lifter
LIFTER_CHECKPOINT=model_3d/artifacts/checkpoints/fitness_pose_lifter_latest_best.pt
DB_ENABLED=true
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=vr_user_db
SMOOTHING_ENABLED=true
KEYPOINT_FORMAT=movenet_yx
```

---

## 미완성 / 다음 작업

### 1. s01_preprocessing ↔ s02_backend 연결 (미완성)
- 현재 `s02_backend/server.py`는 `posture_analyzer.py`(관절 각도 분석)만 사용
- `s01_preprocessing`의 PoseNormalizer, RepDetector, DTWComparator, ScoreEngine이 서버 파이프라인에 **미연결**
- 연결하면: 웹캠 프레임 → 정규화 → 반복 횟수 감지 + DTW 점수 → 실시간 피드백
- **연결 위치**: `s02_backend/server.py`의 WebSocket 핸들러 내부

### 2. ExpertPoseCache 준비 (미완성)
- `s01_preprocessing/expert_cache.py`의 `ExpertPoseCache.build()`는 TensorFlow + PoseEstimator 필요
- 전문가 영상(`전처리/assets/expert_videos/squat_full.mp4`)을 오프라인으로 사전 처리하여 `.npy`로 저장하는 스크립트 필요
- TF 없이 실행하려면 사전 계산된 expert sequence `.npy` 파일을 로드하는 방식으로 변경

### 3. 구버전 폴더 정리
- `final/backend/`, `final/client/`, `final/frontend/`, `final/unity/` 삭제 가능
- 현재 `final/s0X_*` 폴더로 대체 완료

### 4. 브라우저 웹캠 30fps 최적화 (중단됨)
- 현재: 매 프레임 서버 응답 대기 후 스켈레톤 그림
- 개선안: `viewer.js` detectLoop에서 로컬 keypoints로 스켈레톤 즉시 그리고, 서버 응답은 피드백 오버레이에만 사용
- 파일: `final/s05_frontend/viewer.js`의 `detectLoop()` 함수

---

## 알려진 문제

| 문제 | 원인 | 해결 |
|------|------|------|
| Python 3.8 type hint 오류 | `list[tuple]` 구문은 3.9+만 지원 | `from __future__ import annotations` 추가 완료 |
| dtaidistance 최신 버전 빌드 실패 | pyproject.toml 스펙 충돌 | `dtaidistance==2.3.12` 설치 |
| 포트 8000 충돌 | 이전 서버가 백그라운드 실행 중 | `taskkill /F /PID <PID>` 또는 `netstat -ano | findstr :8000` |

---

## 전처리 코드 출처

`final/s01_preprocessing/`의 모든 파일은 `전처리/backend/` 폴더 코드 기반.
변경 사항은 **경로 수정만** (로직 변경 없음):
- `from backend.xxx import` → `from .xxx import` (상대 임포트)
- `"assets/expert_videos/..."` 경로 → `Path(__file__).parents[2] / "전처리" / ...` (절대 경로)
- 모든 파일 상단에 `from __future__ import annotations` 추가 (Python 3.8 호환)
