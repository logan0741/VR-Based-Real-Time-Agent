# Backend

FastAPI WebSocket 서버. SMPL-X 포즈 피팅 및 MySQL 세션 저장 담당.

## 구조

- `model_3d/server_app/server.py` — 메인 서버 (WebSocket /ws/pose)
- `model_3d/server_app/database.py` — MySQL 세션 저장
- `model_3d/server_app/posture_analyzer.py` — 관절 각도 / 피로도 분석
- `model_3d/fitter.py` — SMPL-X OptimizationFitter
- `model_3d/pose_retargeting.py` — OneEuro 스무딩

## 환경변수 (.env)

| 변수 | 값 | 설명 |
|------|-----|------|
| FITTER_BACKEND | optimization | SMPL-X 피팅 모드 |
| SMPLX_MODEL_PATH | smplx_locked_head/neutral/model.npz | SMPL-X 모델 경로 |
| DB_NAME | vr_user_db | MySQL 데이터베이스 |
| SMOOTHING_ENABLED | true | OneEuro 필터 활성화 |

## WebSocket 프로토콜

**Client → Server**
```json
{"data_type": "keypoints", "frame_id": "f0", "payload": [[y,x,conf], ...17개]}
```

**Server → Client**
```json
{
  "status": "ok",
  "fit": {
    "backend": "optimization",
    "global_orient": [rx, ry, rz],
    "body_pose": [rx,ry,rz, ... x21],
    "joints_3d": [[x,y,z], ... x17]
  },
  "feedback": {"score": 85, "label": "양호", "muscle_fatigue": {...}},
  "keypoints_2d": [[y,x,conf], ...17개]
}
```

## 좌표계

SMPL-X 기준: 오른손 좌표계 (X-Right, Y-Up, Z-Back)  
Unity 변환: X축 반전 + 각도 부호 반전 (공식 SMPLX.cs QuatFromRodrigues 방식)
