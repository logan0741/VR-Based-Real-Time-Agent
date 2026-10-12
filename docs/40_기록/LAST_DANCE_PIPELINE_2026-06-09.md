# Last Dance Pipeline

이 문서는 `last-dance` 브랜치에 푸시된 현재 실시간 운동 분석 파이프라인을 정리한 기록이다. 목적은 이후 작업자가 코드 전체를 다시 뒤지지 않고도 app, viewer, backend, preprocessing, feedback, expert pose 흐름을 빠르게 이어받을 수 있게 하는 것이다.

## 현재 목표

- 핸드폰의 viewer 웹에서 카메라를 켜고 사용자 자세를 2D keypoint로 추출한다.
- viewer가 keypoint를 WebSocket으로 서버에 전송한다.
- 서버는 운동 종류, 세트/횟수 목표, 전문가 포즈, 실시간 피드백, 횟수 카운트를 관리한다.
- VR 기기 또는 app 웹은 서버에서 받은 사용자 자세와 전문가 포즈를 표시한다.
- 실시간 화면에서는 레이턴시를 우선하고, 운동 종료 후 최종 피드백은 더 자세하게 제공한다.

## 전체 흐름

1. 사용자가 app 웹에서 운동을 선택한다.
2. app은 `/api/session-control` 또는 WebSocket 제어 메시지로 현재 운동 상태를 서버에 반영한다.
3. viewer는 서버의 세션 제어 상태를 받아 선택된 운동에 맞는 전문가 포즈를 로드한다.
4. viewer에서 카메라를 시작하면 MoveNet 기반 2D keypoint가 생성된다.
5. viewer는 keypoint frame을 `/ws/pose` WebSocket으로 서버에 전송한다.
6. 서버는 frame을 저장하고 rep detector, feedback engine, expert pose 상태를 갱신한다.
7. app은 WebSocket으로 최신 사용자 포즈, 운동 상태, 피드백, expert phase를 받는다.
8. app과 viewer는 같은 `expert_phase_ms` 기준으로 전문가 포즈 프레임을 재생한다.
9. 운동 종료 시 app은 누적된 피드백 샘플을 기반으로 최종 자세 분석을 만든다.

## 주요 디렉터리

- `final/s05_frontend/`
  - 핸드폰 viewer 웹.
  - 카메라 실행, MoveNet 로드, 사용자 keypoint 추출, 서버 전송, 전문가 포즈 표시를 담당한다.

- `final/s02_backend/`
  - 현재 메인 FastAPI/WebSocket 서버.
  - viewer와 app 사이의 pose relay, session control, rep count, feedback, expert phase sync를 담당한다.

- `final/s01_preprocessing/`
  - 운동별 설정, rep detector, 실시간 feedback engine이 들어 있다.
  - 실시간성 때문에 DTW 전체 연산보다 가벼운 2D keypoint 기반 판정 위주로 사용한다.

- `src/`
  - app 웹 React 코드.
  - 운동 선택, 사용자/전문가 skeleton 표시, 세트/횟수 UI, 최종 피드백 화면을 담당한다.

- `dist/`
  - 현재 app 빌드 산출물.
  - 서버 배포 또는 정적 serving에서 사용하는 결과물이다.

- `final/assets/expert_videos/`
  - 전문가 포즈 캐시.
  - `pull_up.npy`, `hammer_curl.npy`, `lateral_raise.npy`가 포함되어 TFHub fetch 없이 서버가 전문가 포즈를 로드할 수 있게 했다.

- `viewer_3d_web/`, `src/components/Skeleton3D*`, `src/hooks/useExpertPose3d.ts`
  - 3D/SMPLX 실험 흔적.
  - 현재 최종 방향은 2D 우선이지만, 이후 Unity/3D 검토를 위해 남겨둔 코드다.

## 실시간 경로

실시간 화면은 레이턴시를 줄이는 것이 최우선이다.

- viewer는 카메라 frame에서 2D keypoint만 추출한다.
- 서버는 받은 keypoint를 즉시 app으로 relay한다.
- 무거운 DTW 전체 비교는 실시간 hot path에서 줄이거나 제외한다.
- 실시간 피드백은 짧은 문장과 낮은 계산량 기준으로 제공한다.
- app과 viewer의 전문가 포즈는 서버 timestamp 기반 `expert_phase_ms`로 맞춘다.

## 운동 선택 동기화

운동 선택은 app이 기준이다.

- app에서 운동을 바꾸면 서버의 session control이 갱신된다.
- viewer는 WebSocket 메시지와 `/api/session-control` polling으로 현재 운동을 따라간다.
- viewer의 전문가 포즈도 app에서 선택한 운동에 맞게 바뀌어야 한다.
- 운동 변경 직후 이전 전문가 포즈가 잠깐 남는 문제를 줄이기 위해 서버의 `expert_started_at_ms`, `expert_phase_ms`를 함께 사용한다.

## Rep Count

현재 rep count는 `final/s01_preprocessing/rep_detector.py`와 `final/s01_preprocessing/config.py` 설정을 따른다.

현재 반영된 방향:

- 프레임을 억지로 낮추지 않는다.
- 판정 민감도를 조절해서 실시간성을 유지한다.
- squat, pullup, hammer_curl, lateral_raise 기준을 완화했다.
- hammer_curl, lateral_raise는 구현 상태를 `True`로 올렸다.
- lateral_raise는 어깨와 손목의 y 좌표 차이를 신호로 사용한다.

주의:

- app UI의 reps/set과 서버의 최종 rep count가 따로 놀면 안 된다.
- 이후 작업에서는 app 더미 카운터가 남아 있는지 우선 확인해야 한다.
- 최종 기준은 서버가 계산한 rep count로 통일하는 것이 맞다.

## Feedback

피드백은 두 종류로 분리한다.

### 실시간 피드백

- 짧고 빠르게 표시한다.
- 한국어 문장으로 보여야 하며 변수명이나 enum key가 그대로 노출되면 안 된다.
- 너무 긴 요약은 app 화면에서 방해가 되므로 피한다.
- 스쿼트만 "측정 중입니다."로 고정되는 문제가 있었고, 이 경로는 계속 확인 대상이다.

### 최종 피드백

- 운동 종료 후에는 레이턴시 부담이 작으므로 실시간보다 자세히 제공한다.
- 현재 구현은 프롬프트/LLM 기반 자동 생성이 아니라, 누적 feedback sample을 집계해 만드는 deterministic 분석이다.
- 반복적으로 나온 부위, 메시지, 점수, 피로 정보를 바탕으로 최종 자세 분석을 구성한다.
- 이후 LLM 기반 프롬프트 분석을 붙이려면 이 최종 피드백 단계에만 붙이는 것이 맞다.

## Expert Pose

전문가 포즈는 viewer와 app 양쪽에 표시된다.

- viewer는 `final/s05_frontend/viewer.js`에서 전문가 포즈를 로드하고 표시한다.
- app은 `src/hooks/useExpertPose2D.ts`, `src/components/SkeletonCanvas2D.tsx` 쪽에서 전문가 포즈를 재생한다.
- 서버가 내려주는 phase 기준으로 양쪽 재생 위치를 맞춘다.
- app과 viewer의 FPS, 시작 시간, 운동 변경 시 reset 타이밍이 어긋나면 전문가 영상 딜레이가 커진다.

## CSP와 모델 로딩

이전 문제:

- viewer에서 Kaggle TFHub redirect URL이 CSP에 막혔다.
- 그 결과 MoveNet 모델 fetch 실패로 카메라가 켜져도 keypoint가 들어오지 않았다.
- 화면에는 FPS가 높게 보여도 실제 pose 데이터 이동이 없을 수 있었다.

현재 방향:

- CSP의 `connect-src`는 실제 모델 fetch URL을 허용해야 한다.
- 가능한 경우 서버 또는 로컬 asset/cache를 활용해 외부 fetch 의존도를 낮춘다.
- `.npy` 전문가 포즈 캐시는 서버 시작 시 외부 모델 다운로드를 피하기 위해 포함했다.

## Latency 원인 정리

확인된 주요 원인은 다음과 같다.

- viewer에서 모델 fetch 실패로 pose frame이 생성되지 않음.
- CSP가 Kaggle/TFHub redirect URL을 막음.
- app과 viewer가 전문가 포즈를 각자 다른 시간 기준으로 재생함.
- DTW 또는 무거운 분석이 실시간 hot path에 들어오면 frame 처리 지연이 커짐.
- app UI에 별도 더미 카운터가 있으면 서버 기준 값과 어긋남.
- 운동 변경 시 이전 운동 expert frame/state가 잠시 남음.

## 현재 포함된 커밋 범위

`last-dance` 브랜치에는 다음이 포함되어 있다.

- 실시간 2D 운동 파이프라인 코드
- app/viewer/backend 연동 수정
- 운동 선택 동기화
- 전문가 포즈 phase sync
- 한국어 feedback 관련 수정
- rep detector 민감도 조정
- 전문가 포즈 JSON 및 `.npy` cache
- app 빌드 산출물 `dist`
- Unity/SMPLX 계획 문서
- 3D viewer 실험 코드

커밋에서 제외한 파일:

- `ngrok_*.txt`
- `pw_*.mjs`
- `screenshot_*.mjs`
- `final_check.mjs`
- `MotionBERT/` 본체

`MotionBERT/`는 내부에 별도 `.git`이 있어 그대로 커밋하면 정상 파일이 아니라 embedded repository gitlink로 들어가므로 제외했다.

## 다음 확인 순서

1. app의 reps/set UI가 서버 rep count만 쓰는지 확인한다.
2. 최종 운동 횟수가 더미 값이면 서버 값으로 통일한다.
3. 스쿼트 실시간 피드백이 "측정 중입니다."에 머무는 원인을 확인한다.
4. app에서 운동 변경 시 viewer 전문가 포즈가 즉시 바뀌는지 확인한다.
5. viewer와 app의 전문가 포즈 phase 차이를 실제 화면에서 다시 측정한다.
6. 최종 피드백을 LLM 기반으로 바꿀지, 현재 deterministic 집계 방식을 유지할지 결정한다.

