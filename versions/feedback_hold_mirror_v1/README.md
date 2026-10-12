# Feedback Hold and Mirror v1

이 버전은 점수 기준을 완화하지 않고, 피드백 표시/누적 정책을 분리해서 경고가 과도하게 쌓이는 문제를 줄인다.

## 변경 이유

점수 기준을 느슨하게 만들면 실제 평가 기준 자체가 약해진다. 원래 의도는 평가 기준을 낮추는 것이 아니라 같은 구간에서 같은 경고가 프레임마다 계속 누적되는 것을 막는 것이다.

## 적용 내용

### 1. 점수 기준 원복

- `max_distance`: `1.35 -> 1.0`
- 피드백 threshold: `0.16/0.18 -> 0.10/0.12`
- `axis_tolerance`: `0.04 -> 0.02`
- `gap_threshold`: 원래 값으로 복구

`versions/scoring_normalization_lenient_v1`은 실험 기록으로 남긴다.

### 2. 피드백 hold 정책

위치:

- `final/s01_preprocessing/feedback/feedback_policy.py`
- `final/s02_backend/server.py`

동작:

1. 의미 있는 피드백 1개를 수락한다.
2. 기본 3초 동안 같은 피드백을 유지한다.
3. 유지 시간 동안 다른 피드백은 화면 메시지/최종 누적 이벤트로 새로 쌓지 않는다.
4. 유지 시간이 끝나면 다음 피드백을 받을 수 있다.

조정:

```powershell
$env:FEEDBACK_HOLD_FRAMES="90"
```

기본값은 `target_fps * 3`이다.

### 3. feedback_event

서버가 `feedback.feedback_event`를 내려준다.

- `true`: 새로 수락된 피드백 이벤트
- `false`: hold 중인 표시용 피드백

App은 `feedback_event=true`일 때만 운동 중 주요 피드백 로그와 최종 분석 샘플에 넣는다.

### 4. App 좌우 반전 버튼

App의 내 자세 패널에 `좌우 반전` 버튼을 추가했다.

- 버튼 ON/OFF 상태가 `SkeletonCanvas2D mirror` prop에 직접 연결된다.
- 내 자세 skeleton만 반전한다.

## 테스트 기준

1. 같은 자세 오류가 한 구간에서 반복돼도 운동 중 피드백 로그가 프레임마다 늘지 않아야 한다.
2. 최종 피드백의 동일 메시지 count가 수백/수천 회로 튀지 않아야 한다.
3. 좌우 반전 버튼을 누르면 내 자세 skeleton이 좌우로 즉시 뒤집혀야 한다.
