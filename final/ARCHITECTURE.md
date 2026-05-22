# VR 기반 실시간 운동 코치 — 시스템 아키텍처

> 기준: `final/` 폴더 · FastAPI + PyTorch + MySQL + Unity VR

---

## 01 전체 데이터 흐름

```mermaid
flowchart LR
    subgraph IN["📷 입력 클라이언트"]
        WC["webcam_client.py\ns04_webcam/"]
        VC["video_client.py"]
        BR["브라우저\nTF.js MoveNet"]
    end

    subgraph SRV["⚙️ FastAPI 서버  :8000  ·  s02_backend/server.py"]
        WS["/ws/pose\nWebSocket"]
        subgraph PL["FastPosePipeline"]
            direction TB
            P1["① PoseLifterNet\n17×3 → 66 SMPL-X"]
            P2["② PoseRetargeter\nOneEuro + VelClamp"]
            P3["③ PostureAnalyzer\n근육 피로도"]
            P4["④ PreprocessingSession\nDTW · Score · Feedback"]
            P1 --> P2 --> P3 --> P4
        end
        DB[("MySQL\nexercise_sessions")]
    end

    subgraph OUT["📺 출력 클라이언트"]
        V2D["2D 웹 뷰어\ns05_frontend/\nCanvas 스켈레톤"]
        REACT["React 대시보드\nsrc/\n점수링 · 세트카운터"]
        UNITY["Unity VR\ns06_unity_vr/\nSMPL-X 아바타"]
    end

    WC -->|"COCO-17  [y,x,conf]×17"| WS
    VC --> WS
    BR -->|"MoveNet keypoints"| WS

    WS --> PL
    P4 -->|"session_end\nsave_session()"| DB

    WS -->|"broadcast_json()"| V2D
    WS -->|"broadcast_json()"| REACT
    WS -->|"broadcast_json()"| UNITY
```

---

## 02 서버 내부 파이프라인

```mermaid
flowchart TD
    RECV["WS 수신\ndata_type: keypoints"]
    VAL["_validate_keypoints\n17관절 × 3값 검증"]

    subgraph LIFTER["PoseLifterNet  —  MLP 4-layer · 512-dim · GELU"]
        GPU["kpts → GPU tensor\n(1, 17, 3)"]
        FWD["forward()  →  output[66]"]
        SPLIT["global_orient[3]  +  body_pose[63]"]
        GPU --> FWD --> SPLIT
    end

    subgraph RETARGET["PoseRetargeter"]
        VC2["VelocityClamper\n최대 변위 제한"]
        OEF["OneEuroFilterBank\n적응형 저역통과 필터"]
        VC2 --> OEF
    end

    subgraph ANALYZER["PostureAnalyzer"]
        K["무릎각도\n대퇴사두근 · 둔근"]
        B["허리굽음\n척추기립근"]
        C["코어 상태\n복근"]
        K --> B --> C
    end

    subgraph PREPRO["PreprocessingSession  (연결별 독립 인스턴스)"]
        PN["PoseNormalizer\nfront / side_left"]
        RD["RepDetector\nslope 기반 반복 감지"]
        DW["DTWComparator\nvs ExpertPoseCache"]
        SC["ScoreEngine\n0~100점"]
        FE["FeedbackEngine\nbody_part · severity"]
        FP["FeedbackPolicy\nhold_frames 쿨다운"]
        PN --> RD
        PN --> DW
        RD -->|"new_reps"| SC
        DW -->|"dist_matrix"| SC
        DW -->|"joint_distances"| FE
        FE --> FP
    end

    RESP["JSON 응답 조립\nfit · feedback · debug"]
    BC["broadcast_json()\n모든 연결에 전파"]

    RECV --> VAL
    VAL --> GPU
    SPLIT --> VC2
    OEF --> RESP
    C --> RESP
    SC --> RESP
    FP --> RESP
    RESP --> BC
    VAL --> PN
```

---

## 03 전처리 파이프라인 상세

```mermaid
flowchart LR
    subgraph BOOT["서버 시작 시 1회 로드  (공유 리소스)"]
        direction TB
        EPC["ExpertPoseCache\n전문가 영상 읽기\nsquat_full.mp4\n→ keypoints (N,17,3)"]
        DTWIN["DTWComparator\n종목별 keypoints_used 선택"]
        FBE["FeedbackEngine\nbody_parts · threshold 로드"]
    end

    subgraph CONN["연결별  PreprocessingSession"]
        direction TB
        PN2["PoseNormalizer\n어깨-골반 기준 정규화"]
        NBUF["norm_buffer\n누적 시퀀스"]
        RD2["RepDetector\n힙Y 슬로프 감지\nmin_rep_frames=24"]
        DM["dist_matrix\n3프레임마다 갱신"]
        GEO["GeometricScorer\nsquat_front\n무릎 · 발목 정렬 검사"]
        SC2["ScoreEngine\n가중 평균 0~100"]
        FP2["FeedbackPolicy\nfps×3 쿨다운"]
    end

    OUT2(["rep_count · score\nmessage · body_part · severity"])

    EPC -->|"expert_cache.sequence"| DTWIN
    DTWIN --> DM
    FBE --> FP2

    PN2 --> NBUF
    NBUF --> DM
    PN2 --> RD2
    RD2 -->|"new_reps"| SC2
    DM -->|"dist_matrix"| SC2
    DM -->|"joint_distances"| FBE
    GEO -->|"squat 정면 모드"| SC2
    SC2 --> FP2
    FP2 --> OUT2
```

---

## 04 DB ERD

```mermaid
erDiagram
    exercise_sessions {
        bigint      id            PK "AUTO_INCREMENT"
        varchar     session_id    UK "uuid4().hex"
        varchar     user_id          "사용자 식별자"
        varchar     exercise_type    "squat / hammer_curl 등"
        datetime    started_at       "세션 시작 UTC DATETIME(6)"
        datetime    ended_at         "세션 종료 UTC DATETIME(6)"
        int         duration_ms      "총 운동 시간 ms"
        int         frame_count      "처리 프레임 수"
        float       avg_score        "평균 점수 0~100"
        float       best_score       "최고 점수"
        float       worst_score      "최저 점수"
        varchar     final_label      "마지막 피드백 레이블"
        json        summary_json     "전체 summary NULL 허용"
        timestamp   created_at       "DEFAULT CURRENT_TIMESTAMP"
    }
```

**인덱스**

| 인덱스명 | 컬럼 | 용도 |
|----------|------|------|
| `idx_user_started` | `(user_id, started_at)` | 사용자별 세션 조회 |
| `idx_exercise_started` | `(exercise_type, started_at)` | 종목별 세션 조회 |

- 중복 방지: `ON DUPLICATE KEY UPDATE` (session_id 기준)
- DB 비활성화: `.env` 에서 `DB_ENABLED=false` → save_session() 스킵, 서버 정상 동작

---

## 05 REST & WebSocket API

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `WS` | `/ws/pose` | 실시간 포즈 스트림 — `keypoints` · `session_start` · `session_end` · `reset` |
| `GET` | `/` | index.html (2D 뷰어) |
| `GET` | `/viewer/` | `s05_frontend/` Static 서빙 (no-cache) |
| `GET` | `/app/` | `dist/` React 빌드 Static 서빙 |
| `GET` | `/api/health` | 서버 · DB 연결 상태 확인 |
| `POST` | `/api/reset` | OneEuro 스무딩 필터 초기화 |
| `POST` | `/api/session/start` | 세션 시작 `{ user_id, exercise_type }` |
| `POST` | `/api/session/end` | 세션 종료 → DB 저장 → summary 반환 |
| `GET` | `/api/expert` | 전문가 원본 keypoints JSON (raw) |
| `GET` | `/api/expert-keypoints` | 전문가 2D keypoints (N×17×3) — React 스켈레톤용 |
| `GET` | `/api/expert-smplx` | 전문가 SMPL-X params (PoseLifterNet 캐싱) — Unity용 |

---

## 06 WebSocket 메시지 프로토콜

**Client → Server**

```json
// 포즈 프레임 전송
{ "data_type": "keypoints", "frame_id": "cam_42",
  "payload": [[y,x,conf], ...] }

// 세션 제어
{ "data_type": "session_start", "user_id": "user01", "exercise_type": "squat" }
{ "data_type": "session_end" }
{ "data_type": "reset" }
```

**Server → Client (broadcast)**

```json
{
  "status": "ok",
  "frame_id": "cam_42",
  "session_id": "a3f9...",
  "keypoints_2d": [[y,x,conf], ...],
  "fit": {
    "backend": "lifter",
    "global_orient": [rx, ry, rz],
    "body_pose":     [j0x, j0y, j0z, ...]
  },
  "feedback": {
    "score":          85,
    "label":          "자세가 안정적입니다.",
    "body_part":      "knee",
    "severity":       0.3,
    "rep_count":      5,
    "rep_scores":     [82, 78, 90, 85, 88],
    "muscle_fatigue": {
      "left_quad": "high", "right_quad": "med",
      "lower_back": "low", "abs": "low"
    }
  },
  "debug": { "inference_ms": 4.2, "smoothing_enabled": true, "smoothing_frame": 120 }
}
```

---

## 07 지원 종목

| 종목 | 뷰 | 스코어 방식 | 전문가 영상 | 상태 |
|------|----|------------|------------|------|
| `squat` | front (정면) | `GeometricScorer.squat_front` | squat_full.mp4 | ✅ 구현됨 |
| `hammer_curl` | side_left | DTW | hammer_curl.mp4 | ⏳ stub |
| `pullup` | front | DTW | pull_up.mp4 | ⏳ stub |
| `lateral_raise` | front | DTW | lateral_raise.mp4 | ⏳ stub |

---

## 08 모듈 구조 (final/)

```
final/
├── s01_preprocessing/
│   ├── config.py              EXERCISES 딕셔너리 (종목별 설정)
│   ├── pose_estimator.py      MediaPipe 포즈 추정
│   ├── pose_normalizer.py     관절 정규화 (front / side_left)
│   ├── rep_detector.py        slope 기반 반복횟수 감지
│   ├── expert_cache.py        전문가 영상 → keypoints 추출·캐싱
│   ├── dtw_comparator.py      사용자 vs 전문가 DTW 거리 행렬
│   ├── score_engine.py        DTW 거리 → 0~100점, GeometricScorer
│   └── feedback/
│       ├── feedback_engine.py   DTW 거리 → 자세 피드백 메시지
│       ├── feedback_policy.py   hold_frames 쿨다운 출력 정책
│       ├── feedback_templates.py 종목별 피드백 문구
│       └── feedback_config.py   body_parts · threshold 설정
│
├── s02_backend/
│   ├── server.py              FastAPI app, WS · REST 엔드포인트
│   ├── posture_analyzer.py    관절각도 → 근육 피로도 상태머신
│   ├── pose_retargeting.py    OneEuro · VelocityClamper · PoseRetargeter
│   └── config.py              env 헬퍼 (env_bool 등)
│
├── s03_database/
│   └── database.py            DatabaseSettings · ExerciseSessionRepository
│                              init_schema() · save_session() · health()
│
├── s04_webcam/
│   └── webcam_client.py       웹캠 → /ws/pose 전송
│
├── s05_frontend/              (Quest 3 브라우저 직접 실행 가능)
│   ├── index.html             2D 뷰어 레이아웃
│   ├── viewer.js              WS 연결 · Canvas 렌더링 · TF.js MoveNet · 전문가 스켈레톤 루프
│   └── style.css
│
├── s06_unity_vr/
│   ├── WebSocketClient.cs         서버 연결 · JSON 수신·파싱
│   ├── FitnessAvatarController.cs axis-angle → Quaternion → SMPL-X 뼈대 적용
│   └── UIManager.cs               점수 · 피드백 UI
│
├── assets/expert_videos/
│   ├── squat_full.mp4         ✅ 구현
│   ├── hammer_curl.mp4        ⏳ 미구현
│   ├── pull_up.mp4            ⏳ 미구현
│   └── lateral_raise.mp4     ⏳ 미구현
│
├── 07_pipeline_web.py         웹 전용 파이프라인 실행 진입점
├── 08_pipeline_full.py        전체 파이프라인 실행 진입점
└── 01~04_test_*.py            단계별 단위 테스트
```

---

## 09 Unity 좌표계 변환

```
SMPL-X (Python)                Unity (C#)
오른손 좌표계                    왼손 좌표계
X-left · Y-up · Z-forward       X-right · Y-up · Z-forward

변환 규칙 (FitnessAvatarController.cs)
  axis-angle 벡터의 X, Z 성분을 반전
  → Quaternion 생성 후 initialRotation * q * Euler(offset) 적용
  → Update() 에서 Slerp(lerpFactor=0.5) 로 부드러운 보간
```
