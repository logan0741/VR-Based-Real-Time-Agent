# VR-Based Real-Time Personal Trainer

실시간 AI 자세 교정 및 맞춤형 코칭 시스템.  
웹캠으로 운동 자세를 촬영하면 MediaPipe / TF.js MoveNet으로 2D 관절을 추출하고,
MLP 모델이 3D 포즈를 복원한 뒤 DTW 비교와 기하학적 분석으로 점수·피드백을 실시간 제공합니다.

---

## 데이터 흐름

```
[브라우저 /viewer/]                [Python 웹캠 클라이언트]
  TF.js MoveNet (인브라우저)           MediaPipe (CPU)
        │                                    │
        └──────────┬─────────────────────────┘
                   ▼
         WebSocket /ws/pose
                   │
         FastAPI 서버 (final/s02_backend/server.py)
           ├─ PoseLifterMLP  (2D → 66 SMPL-X 파라미터)
           ├─ PoseRetargeter (OneEuro 필터 + Velocity Clamping)
           ├─ PreprocessingSession (DTW / GeometricScorer → 점수)
           └─ PostureAnalyzer (관절 각도 + 근육 피로도)
                   │
         broadcast → 모든 WebSocket 클라이언트
           ├─ /viewer/   스켈레톤 + 점수 + 피드백
           └─ /app/      React 대시보드 (스켈레톤 + 점수 + 피드백)
```

---

## 디렉토리 구조

```
VR-Based-Real-Time-Agent/
├── final/
│   ├── s01_preprocessing/      # 전처리 파이프라인
│   │   ├── config.py           # 종목별 설정 (스쿼트 등)
│   │   ├── pose_normalizer.py  # 골반 기준 정규화
│   │   ├── dtw_comparator.py   # DTW 관절 거리 계산
│   │   ├── rep_detector.py     # 동작 횟수 감지
│   │   ├── expert_cache.py     # 전문가 포즈 사전 로드
│   │   ├── score_engine.py     # DTW 점수 / GeometricScorer
│   │   └── feedback/           # 피드백 메시지 생성
│   ├── s02_backend/            # FastAPI 서버
│   │   ├── server.py           # 메인 서버
│   │   ├── pose_retargeting.py # 포즈 스무딩
│   │   └── posture_analyzer.py # 근육 피로도 분석
│   ├── s03_database/           # MySQL 세션 저장
│   ├── s04_webcam/             # Python 웹캠 클라이언트
│   ├── s05_frontend/           # 2D 웹 뷰어 (HTML / JS / CSS)
│   ├── s06_unity_vr/           # Unity C# 스크립트
│   ├── assets/
│   │   └── expert_videos/      # ⚠ 별도 배치 필요 (gitignore)
│   └── tools/                  # 유틸리티
├── run_steps.py                # 파이프라인 실행기
├── requirements.txt
└── .env.example                # 환경변수 템플릿
```

---

## 빠른 시작

### 1. 의존성 설치

```powershell
pip install -r requirements.txt
```

### 2. 환경변수 설정

```powershell
copy .env.example .env
```

`.env` 파일을 열어 아래 항목 확인:

```env
FITTER_BACKEND=lifter
LIFTER_CHECKPOINT=<체크포인트 .pt 파일 경로>

SMOOTHING_ENABLED=true
SMOOTHING_MIN_CUTOFF=1.0
SMOOTHING_BETA=0.007
SMOOTHING_MAX_VELOCITY=0.5

DB_ENABLED=false          # MySQL 없이 실행할 경우 false
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=
DB_NAME=vr_fitness

KEYPOINT_FORMAT=movenet_yx
```

### 3. 서버 실행

```powershell
python run_steps.py --server
```

또는 직접 uvicorn:

```powershell
python -m uvicorn final.s02_backend.server:app --host 0.0.0.0 --port 8000
```

### 4. 접속

| 경로 | 설명 |
|------|------|
| `http://localhost:8000/viewer/` | 2D 뷰어 — 인브라우저 TF.js MoveNet 카메라 내장 |
| `http://localhost:8000/app/` | React 대시보드 — 서버 broadcast 수신 |
| `ws://localhost:8000/ws/pose` | WebSocket 엔드포인트 |

Quest 3에서 접속할 경우 PC와 같은 Wi-Fi 연결 후:

```
http://<PC_IP>:8000/viewer/
```

PC IP 확인: `ipconfig`

---

## 입력 방식

### 방법 A: 브라우저 카메라 (권장)

`/viewer/` 접속 후 **웹캠 시작** 버튼 클릭 → TF.js MoveNet이 브라우저에서 직접 관절을 감지해 서버로 전송합니다. Python 클라이언트 불필요.

### 방법 B: Python 웹캠 클라이언트

MediaPipe 기반 웹캠 클라이언트를 별도 터미널에서 실행:

```powershell
python -m final.s04_webcam.webcam_client
```

---

## 외부 접속 (Cloudflare Tunnel)

서버를 먼저 실행한 뒤, 별도 터미널에서:

```powershell
cloudflared tunnel run
```

또는 `run_steps.py`로 한 번에:

```powershell
python run_steps.py --cloudflare
```

---

## 사전 배치가 필요한 파일

이 파일들은 라이선스 문제로 git에 포함되지 않으므로 별도로 준비해야 합니다.

| 파일 | 경로 | 용도 |
|------|------|------|
| PoseLifterMLP 체크포인트 | `.env`의 `LIFTER_CHECKPOINT` 경로 | 2D→3D 포즈 리프팅 |
| 스쿼트 전문가 영상 | `final/assets/expert_videos/squat_full.mp4` | DTW 비교 기준 |
| 해머컬 영상 | `final/assets/expert_videos/hammer_curl.mp4` | (선택) |
| 레터럴 레이즈 영상 | `final/assets/expert_videos/lateral_raise.mp4` | (선택) |
| 풀업 영상 | `final/assets/expert_videos/pull_up.mp4` | (선택) |

> 전문가 영상 `.npy` 캐시가 없으면 서버 시작 시 `squat_full.mp4`에서 자동 생성됩니다.

---

## WebSocket 프로토콜

**클라이언트 → 서버**

```json
{
  "data_type": "keypoints",
  "frame_id": "cam_1",
  "payload": [[y, x, conf], ...]
}
```

- `payload`: COCO-17 관절 17개, `[y/height, x/width, confidence]` 형식 (0~1 정규화)

**서버 → 클라이언트 (broadcast)**

```json
{
  "status": "ok",
  "frame_id": "cam_1",
  "keypoints_2d": [[y, x, conf], ...],
  "fit": {
    "global_orient": [3개 axis-angle],
    "body_pose": [63개 axis-angle]
  },
  "feedback": {
    "score": 85,
    "message": "자세가 안정적입니다.",
    "body_part": "ok",
    "rep_count": 3,
    "rep_scores": [82, 79, 85],
    "muscle_fatigue": {"left_quad": "low", ...}
  },
  "debug": {
    "inference_ms": 6.2,
    "smoothing_enabled": true,
    "smoothing_frame": 42
  }
}
```

---

## 지원 종목

| 종목 | ID | 상태 |
|------|----|------|
| 스쿼트 (정면) | `squat` | 구현 완료 — 기하학적 스코어링 + DTW |
| 해머컬 | `hammer_curl` | 미구현 (stub 반환) |
| 풀업 | `pullup` | 미구현 (stub 반환) |
| 레터럴 레이즈 | `lateral_raise` | 미구현 (stub 반환) |

---

## Unity 연동

`final/s06_unity_vr/` 의 C# 스크립트를 Unity 프로젝트 `Assets/Scripts/`에 복사:

- `WebSocketClient.cs` — FastAPI WebSocket 연결, JSON 파싱
- `FitnessAvatarController.cs` — `global_orient` + `body_pose`를 SMPL-X 리그 본에 적용

Unity WebSocket URL 설정:
```
ws://<PC_IP>:8000/ws/pose          (LAN)
wss://<cloudflare-domain>/ws/pose  (외부)
```

---

## 팀

| 이름 | 역할 |
|------|------|
| 김보경 | 온디바이스 환경 구축, 데이터 수집 |
| 김건희 | 데이터 정규화 로직 설계, Unity 환경 구성 |
| 이경호 | 데이터 가공, 피드백 모델 설계 |
| 임규보 | 운동 분류 모델 설계, 통신 환경 구축 |
