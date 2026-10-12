# Changelog

All notable changes to this project will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [2026-04-29] — 파이프라인 정리 및 포즈 리타겟팅 적용

### Added
- **`model_3d/pose_retargeting.py`** — 3D 포즈 리타겟팅/스무딩 모듈 신규 추가
  - OneEuro Filter: 적응형 저역통과 필터로 느린 움직임은 강하게 스무딩, 빠른 움직임은 통과
  - Velocity Clamping: 비정상적으로 큰 관절 이동을 제한하여 순간이동 방지
  - `PoseRetargeter` 클래스: body_pose(63), global_orient(3), joints_3d(17×3) 각각 독립 스무딩
  - 환경 변수로 파라미터 조정 가능 (SMOOTHING_MIN_CUTOFF, SMOOTHING_BETA 등)

- **`viewer_2d/`** — 2D 웹 스켈레톤 뷰어 신규 추가
  - `index.html` — WebSocket + Canvas 기반 실시간 스켈레톤 렌더링
  - `viewer.js` — COCO-17 관절/뼈대 드로잉 엔진, FPS/레이턴시 표시
  - `style.css` — 다크 글래스모피즘 UI 테마
  - Quest 3 VR 브라우저에서 직접 접속 가능 (http://<PC_IP>:8000/viewer/)
  - 전문가 vs 사용자 포즈 좌우 패널 비교
  - 근육 피로도 히트맵 실시간 표시
  - 점수 링 애니메이션

- **`run_steps.py`** — 아키텍처 다이어그램 기반 단계별 파이프라인 실행기
  - `--check`: 환경/의존성 확인
  - `--server`: 실시간 서버 + 2D 뷰어 시작
  - `--train`: 학습 파이프라인 실행
  - `--export-unity`: Unity 내보내기 파이프라인
  - `--step N`: 개별 단계 실행 (1~8)
  - `--all`: 전체 오프라인 분석

- **`CHANGELOG.md`** — 이 변경 로그 파일

### Changed
- **`model_3d/server_app/server.py`** — 리타겟팅 모듈 통합, 정적 파일 서빙 추가
  - `FastPosePipeline`에 `PoseRetargeter` 통합: MLP 추론 후 자동 스무딩 적용
  - FastAPI 정적 파일 서빙: `/viewer/` 경로로 2D 뷰어 자동 호스팅
  - `GET /` 루트 경로에서 2D 뷰어로 리다이렉트
  - `POST /api/reset` 엔드포인트: 스무딩 필터 초기화
  - WebSocket 응답에 `keypoints_2d` 필드 추가 (2D 뷰어용)
  - WebSocket에서 `data_type: "reset"` 메시지 처리 추가
  - `host` 변경: `127.0.0.1` → `0.0.0.0` (Quest VR 브라우저 접속 가능)
  - 디버그 정보에 `smoothing_enabled`, `smoothing_frame` 추가

- **`README.md`** — 기술 문서로 전면 재작성
  - Mermaid 아키텍처 다이어그램 추가
  - 디렉토리 구조 설명
  - Quick Start 가이드 (4단계)
  - 4개 파이프라인 (실시간/학습/Unity 내보내기/오프라인 분석) 설명
  - 핵심 모듈 참조 테이블
  - 환경 변수 전체 목록

### Architecture Notes
- **파이프라인 구조는 기존 아키텍처 다이어그램과 동일**하게 유지
- 변경점은 UI Layer만: Unity → 웹 2D 뷰어 (Quest 브라우저) + Unity 병행
- PoseNormalizer 뒤에 PoseRetargeter(스무딩 레이어) 추가
- 서버 API는 동일: Unity AvatarController.cs와 2D 뷰어 모두 같은 WebSocket/JSON 사용

### Not Changed (유지된 파일들)
- `model_3d/pipeline.py` — 프레임 처리 엔진 (그대로)
- `model_3d/pipeline_cli.py` — CLI QA 러너 (그대로)
- `model_3d/lifter_model.py` — PoseLifterMLP 모델 (그대로)
- `model_3d/fitter.py` — SMPL-X 최적화 피터 (그대로)
- `model_3d/analyzer.py` — 스쿼트 분석 (그대로)
- `model_3d/diagnostics.py` — QA 진단 (그대로)
- `model_3d/train_lifter.py` — 학습 스크립트 (그대로)
- `model_3d/train_fitness_lifter.py` — 피트니스 학습 래퍼 (그대로)
- `model_3d/export_fitness_unity.py` — Unity 내보내기 (그대로)
- `model_3d/server_app/posture_analyzer.py` — 자세 분석기 (그대로)
- `model_3d/server_app/clients/*` — 모든 클라이언트 (그대로)
- `unity/FitnessPoseViewer/` — Unity 프로젝트 (그대로, Phase 2)
- `play_squat.py` — 스쿼트 재생 (그대로)

---

## [2026-04-13] — 3D 아바타 스쿼트 애니메이션

### Added
- `model_3d/server_app/server.py` — FastPosePipeline (MLP 추론 서버)
- `model_3d/server_app/posture_analyzer.py` — 근육 피로도 분석
- `model_3d/server_app/clients/video_client.py` — 영상 → 서버 스트리밍
- `model_3d/server_app/clients/webcam_client.py` — 웹캠 실시간 입력
- `unity/FitnessPoseViewer/Assets/Scripts/AvatarController.cs` — SMPL-X 아바타 제어

---

## [2026-04-09] — SMPL-X 파이프라인 구축

### Added
- `model_3d/` 패키지 전체 구조
- SMPL-X 최적화 피터 (`fitter.py`)
- 2D→3D PoseLifterMLP (`lifter_model.py`)
- 피트니스 데이터셋 학습 파이프라인 (`train_lifter.py`, `train_fitness_lifter.py`)
- Unity 시퀀스 내보내기 (`export_fitness_unity.py`)
- QA 진단 시스템 (`diagnostics.py`)

---

## [2026-03] — 프로젝트 초기 설정

### Added
- 프로젝트 기획서 및 README 초안
- 데이터셋 조사 (Fit3D, AthletePose3D, MM-Fit)
- 환경 구성 (.env, requirements.txt)
