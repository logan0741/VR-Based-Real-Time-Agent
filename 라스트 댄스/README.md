# 라스트 댄스

이 폴더는 `last-dance` 브랜치의 현재 개발 상태를 나중에 다시 이어받기 쉽게 정리한 작업 폴더다.

실행 코드는 기존 위치를 유지한다.

- viewer: `final/s05_frontend/`
- backend: `final/s02_backend/`
- preprocessing: `final/s01_preprocessing/`
- app: `src/`
- build output: `dist/`

이 폴더는 다음 목적이다.

1. 전체 파이프라인을 빠르게 이해한다.
2. 어느 기능을 고치려면 어느 파일을 봐야 하는지 찾는다.
3. rep count, feedback, expert pose sync 같은 핵심 로직을 단계별로 수정한다.
4. 수정 후 최소 검증 순서를 지킨다.

## 읽는 순서

1. `01_pipeline.md`
2. `02_step_by_step_code_map.md`
3. `03_rep_count_rules.md`
4. `04_feedback_and_result.md`
5. `05_verification_checklist.md`
6. `config_reference/rep_thresholds.json`

## 현재 중요한 원칙

- rep count는 피드백 결과로 세지 않는다.
- rep count는 운동별 각도와 최소 가동범위 기준으로 센다.
- 실시간 피드백은 짧고 가볍게 유지한다.
- 최종 피드백은 운동 종료 후 자세히 만든다.
- app/viewer의 전문가 포즈는 서버의 `expert_phase_ms`를 기준으로 맞춘다.
- 푸시 전에는 같은 검증을 최소 2회 이상 반복한다.

## 실제 코드 분할 상태

rep count:

- `final/s01_preprocessing/rep_rules.py`: 운동별 threshold
- `final/s01_preprocessing/joint_angles.py`: 관절 각도 계산
- `final/s01_preprocessing/rep_signals.py`: 운동별 keypoint -> angle signal 변환
- `final/s01_preprocessing/rep_detector.py`: rep 상태 머신

server progress:

- `final/s02_backend/session_progress.py`: 세트/횟수 진행 상태 계산
- `final/s02_backend/server.py`: WebSocket, pipeline 연결, broadcast

app progress:

- `src/utils/workoutProgress.ts`: app fallback progress 계산
- `src/App.tsx`: 상태 관리와 화면 연결
