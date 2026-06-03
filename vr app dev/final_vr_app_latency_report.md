# VR App Test 1 최종 수정 보고서

작성일: 2026-06-04
브랜치 대상: `For_Tesst1`

## 1. 작업 배경

이번 작업의 목표는 기존 `final/` 서버와 웹 기반 구조를 유지하면서, Meta Quest 3의 `/app/` 화면에서 운동 중 사용자의 자세 이동이 더 실시간에 가깝게 보이도록 만드는 것이었다.

기존 사용 방식은 다음과 같았다.

```text
핸드폰: /viewer/ 접속
  - 카메라 실행
  - MoveNet으로 2D keypoints 추출
  - 서버 /ws/pose 로 keypoints 전송

Quest 3: /app/ 접속
  - 서버 broadcast 수신
  - 내 자세 skeleton, 점수, rep count, 피드백 표시
```

문제는 `/viewer/`에서는 움직임이 비교적 볼 만했지만, `/app/`에서는 사용자의 자세 skeleton이 늦게 따라오거나 끊겨 보였다는 점이다. VR 환경에서는 사용자가 운동 중 자기 자세를 보면서 교정해야 하므로, 점수보다 skeleton 이동의 즉시성이 더 중요했다.

## 2. 레이턴시 원인 분석

### 2.1 서버 DTW 계산 병목

기존 서버는 `final/s02_backend/server.py`의 `PreprocessingSession`에서 3프레임마다 DTW를 수행했다.

기존 설정:

```text
n_frames = 30
dtw_interval = 3
expert sequence = 256 frames
keypoints_used = 8 joints
```

측정 결과:

```text
최근 2프레임 vs 전문가 전체:  평균 약 78ms
최근 10프레임 vs 전문가 전체: 평균 약 306ms
최근 30프레임 vs 전문가 전체: 평균 약 870ms
```

따라서 기존 방식은 30fps 실시간 처리에 맞지 않았다. 3프레임마다 100ms 이하로 처리되어야 하는데, DTW 한 번이 수백 ms까지 튀면서 서버 큐가 밀렸다.

### 2.2 app은 서버 응답을 기다린 뒤 skeleton을 그림

`/viewer/`는 브라우저에서 MoveNet 결과를 직접 갖고 있다. 반면 `/app/`은 카메라가 없고 서버 broadcast를 받아야만 skeleton을 그릴 수 있다.

기존 흐름:

```text
핸드폰 카메라
-> MoveNet
-> 서버 전송
-> 서버 분석
-> 서버 broadcast
-> Quest app 렌더링
```

이 구조에서는 서버 분석이 늦어지면 `/app/` skeleton도 같이 늦어진다.

### 2.3 WebSocket 연결별 세션 상태 불일치

`/viewer/`와 `/app/`은 각각 다른 WebSocket 연결을 사용한다. 기존에는 `PreprocessingSession`과 rep detector가 연결별로 따로 생성되었다.

그 결과:

- `/viewer/`가 실제 keypoints를 보내면서 rep count를 계산
- `/app/`은 세트 수를 지정하고 운동 시작 버튼을 누름
- 하지만 `/app/`의 시작 버튼이 `/viewer/` 쪽 rep detector를 reset하지 못함
- viewer와 app의 rep count 기준이 달라짐

## 3. 적용한 주요 수정

## 3.1 좌표 즉시 relay

서버가 keypoints를 받으면 분석이 끝나기 전에 먼저 좌표만 즉시 broadcast하도록 수정했다.

새 흐름:

```text
핸드폰 keypoints 수신
-> 서버가 data_type="pose"로 즉시 broadcast
-> Quest app skeleton 갱신

동시에:
-> 서버가 비동기로 분석/DTW/피드백 처리
-> 늦게 feedback broadcast
```

효과:

- `/app/` skeleton이 분석 결과를 기다리지 않음
- 점수/피드백은 늦게 와도 skeleton 이동은 더 즉시적으로 보임

수정 파일:

- `final/s02_backend/server.py`
- `src/hooks/useWebSocket.ts`

## 3.2 최신 프레임 우선 처리

서버가 처리 중일 때 새 keypoints가 계속 들어오면, 오래된 프레임을 쌓아서 처리하지 않고 최신 프레임만 남기도록 수정했다.

목적:

- "늦게라도 모든 프레임 처리"가 아니라 "현재에 가까운 프레임 처리"
- VR/app에서 과거 움직임이 뒤늦게 재생되는 현상 방지

구현:

```text
latest_keypoints_msg 슬롯에 최신 메시지만 저장
processor_task가 끝나면 가장 최신 메시지만 처리
```

수정 파일:

- `final/s02_backend/server.py`

## 3.3 DTW-lite 적용

관절 수는 줄이지 않았다. 사용자가 지적한 대로 관절 수를 줄이면 부위별 피드백 품질이 떨어진다.

유지한 관절:

```text
LEFT_SHOULDER, RIGHT_SHOULDER
LEFT_HIP, RIGHT_HIP
LEFT_KNEE, RIGHT_KNEE
LEFT_ANKLE, RIGHT_ANKLE
```

대신 시간축과 계산 빈도를 줄였다.

최종 DTW-lite 설정:

```text
PREPROCESSING_REALTIME_DTW=true
DTW_EXPERT_STRIDE=16
DTW_N_FRAMES_OVERRIDE=8
DTW_INTERVAL_OVERRIDE=20
FEEDBACK_INTERVAL_FRAMES=3
```

의미:

- 전문가 시퀀스 256프레임을 약 16프레임으로 downsample
- 사용자 최근 8프레임만 비교
- 20프레임마다 1번만 DTW 계산
- 피드백은 3프레임마다 갱신
- 좌표 skeleton은 DTW와 무관하게 즉시 relay

벤치마크:

```text
lite stride12 n8 every20
평균 5.66ms
p95 25.64ms
최대 140.99ms
33ms 초과 2번

lite stride16 n6 every20
평균 4.16ms
p95 16.59ms
최대 107.91ms
33ms 초과 1번

lite stride16 n8 every20
평균 4.19ms
p95 16.27ms
최대 114.67ms
33ms 초과 1번
```

최종 선택:

```text
DTW_EXPERT_STRIDE=16
DTW_N_FRAMES_OVERRIDE=8
DTW_INTERVAL_OVERRIDE=20
```

이 설정은 관절 수를 유지하면서 app 끊김 위험을 가장 작게 만든 후보였다.

## 3.4 rep-only DTW 후보도 테스트

rep 완료 시점에만 DTW를 계산하는 방식도 테스트했다.

결과:

```text
rep-only DTW stride8
평균 3.39ms
p95 3.49ms
최대 161.28ms
33ms 초과 1번
```

판단:

- 평소 skeleton 이동에는 가장 안전
- 하지만 실시간 중 부위별 DTW 피드백이 약함
- 최종 rep 점수용으로는 유용

현재는 실시간 DTW-lite를 켜되, 좌표 relay를 완전히 분리해서 skeleton이 DTW에 막히지 않도록 했다.

## 3.5 app과 viewer의 rep/session 기준 동기화

서버에 전역 session control을 추가했다.

`/app/`에서 운동 시작을 누르면:

```text
app -> session_start 전송
server -> 전역 session_control_version 증가
viewer keypoints 처리 전 -> 해당 control version 감지
viewer 쪽 PreprocessingSession reset
rep detector reset
```

이제 app에서 지정한 운동 시작 시점이 viewer에서 실제 rep를 세는 기준이 된다.

권장 사용 순서:

```text
1. Quest에서 /app/ 열기
2. 세트 수 지정
3. 핸드폰에서 /viewer/ 열기
4. 카메라 시작
5. Quest /app/에서 운동 시작 누르기
6. 그 시점부터 viewer/app rep count 기준이 reset됨
```

viewer를 먼저 켜도 된다. 중요한 기준점은 app의 운동 시작 버튼이다.

수정 파일:

- `final/s02_backend/server.py`
- `src/hooks/useWebSocket.ts`
- `src/App.tsx`

## 3.6 app 내 자세 좌우 반전

`/viewer/`는 기본 mirror 모드라 사용자가 거울처럼 본다. `/app/`은 서버 좌표를 그대로 그려 좌우가 반대로 보였다.

수정:

- `SkeletonCanvas`에 `mirror` 옵션 추가
- app의 "내 자세" skeleton에만 mirror 적용
- 강사 모델은 mirror 적용하지 않음

수정 파일:

- `src/components/SkeletonCanvas.tsx`
- `src/App.tsx`

## 3.7 viewer rep count 겹침 수정

viewer 중앙 패널에서 rep count가 score label을 가리는 문제가 있었다.

수정:

- score ring 아래 margin 확장
- rep count를 독립 박스 형태로 분리
- CSS pseudo label로 "총 횟수" 표시

수정 파일:

- `final/s05_frontend/style.css`

## 4. 현재 실행 설정

현재 테스트 서버 권장 실행 설정:

```powershell
$env:PREPROCESSING_ENABLED="true"
$env:PREPROCESSING_REALTIME_DTW="true"
$env:DTW_EXPERT_STRIDE="16"
$env:DTW_N_FRAMES_OVERRIDE="8"
$env:DTW_INTERVAL_OVERRIDE="20"
$env:FEEDBACK_INTERVAL_FRAMES="3"
$env:DB_ENABLED="false"
$env:FITTER_BACKEND="lifter"
python -m uvicorn final.s02_backend.server:app --host 0.0.0.0 --port 8000
```

접속 주소:

```text
핸드폰 viewer: http://192.168.0.18:8000/viewer/
Quest app:     http://192.168.0.18:8000/app/
```

## 5. requirements.txt 업데이트

누락되어 있던 의존성을 추가했다.

추가 항목:

```text
tensorflow>=2.13.0
tensorflow-hub>=0.16.0
websocket-client>=1.6.0
typing_extensions>=4.8.0
```

이유:

- `final/s01_preprocessing/pose_estimator.py`에서 TensorFlow와 TensorFlow Hub 사용
- `final/tools/test_2reps.py`에서 `websocket` 패키지 사용
- Python 3.8 환경에서 `NotRequired` fallback에 `typing_extensions` 필요

## 6. .gitignore 업데이트

기존 `.gitignore`는 `/src`, `/package.json`, `/dist` 등을 무시하고 있었다. 이번 VR app 테스트에서는 React app 수정이 핵심이므로, 다음 항목을 Git에 포함하도록 예외를 추가했다.

```text
!/src/
!/src/**
!/package.json
!/package-lock.json
!/tsconfig.json
!/tsconfig.node.json
!/vite.config.ts
!/dist/
!/dist/**
```

또한 Cloudflare quick tunnel 테스트 중 생기는 임시 로그를 무시하도록 추가했다.

```text
cloudflared_*.txt
```

## 7. 남은 리스크와 다음 과제

### 7.1 app 렌더링 병목

현재 app은 React state update를 통해 skeleton을 갱신한다. 더 부드럽게 만들려면 다음 단계가 필요하다.

```text
WebSocket 수신 -> ref에 최신 keypoints 저장
requestAnimationFrame -> canvas 직접 draw
React state는 score/feedback만 갱신
```

이렇게 하면 skeleton 이동이 React render cycle에 덜 묶인다.

### 7.2 DTW 정확도 손실

DTW-lite는 정확도보다 실시간성을 우선한다.

손실 요인:

- 전문가 시간축 downsample
- 사용자 window 축소
- 계산 빈도 감소

하지만 관절 수는 유지했기 때문에 부위별 피드백 구조는 유지된다.

### 7.3 Cloudflare quick tunnel 불안정

임시 trycloudflare tunnel은 한 번 URL 생성 후 404가 나왔고, 재시도 시 API timeout도 발생했다.

운영용으로는 quick tunnel보다 named tunnel과 실제 도메인 CNAME 설정이 필요하다.

## 8. 최종 판단

이번 변경의 핵심은 다음이다.

```text
skeleton 이동 = 즉시 relay
피드백/점수 = 비동기 분석
DTW = 관절 수 유지, 시간축/빈도만 축소
session 기준 = app의 운동 시작 버튼으로 통일
```

이 구조가 현재 웹 기반 Quest 테스트 환경에서 가장 현실적인 균형점이다.
