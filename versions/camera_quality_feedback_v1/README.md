# Camera Quality Feedback Gate v1

이 버전은 운동 중 카메라에 몸이 충분히 잡히지 않는 프레임을 운동 평가에서 제외하기 위한 테스트 버전이다.

## 목표

- 사용자가 화면 밖으로 벗어나거나 주요 관절이 안 보이면 점수에 포함하지 않는다.
- 같은 상황에서는 운동 횟수도 증가시키지 않는다.
- 대신 실시간 피드백에는 카메라 위치 조정 메시지를 띄운다.
- 실시간 피드백 평가 빈도를 낮춰 운동 중 피드백이 과하게 많이 바뀌지 않게 한다.

## 적용 내용

### 1. 카메라 가시성 게이트

위치:

- `final/s02_backend/server.py`
- `PreprocessingSession._camera_visibility_message`

판정 기준:

- 운동별 필수 관절의 confidence가 `0.25` 미만이면 제외
- 필수 관절이 normalized 화면 좌표 `0.02 ~ 0.98` 밖에 있으면 제외

제외 프레임 반환값:

```json
{
  "score": 0,
  "rep_count": "현재까지 카운트된 횟수 유지",
  "message": "전신이 카메라에 모두 나오도록 ...",
  "body_part": "camera",
  "state": "out_of_frame",
  "bad_joints": [],
  "countable": false
}
```

### 2. 점수/횟수 제외

서버:

- `countable: false`인 frame은 `session_tracker.record_frame()`에 넣지 않는다.
- rep detector 업데이트 전에 카메라 게이트를 통과해야 하므로, 화면 밖 프레임은 rep count를 증가시키지 않는다.

앱:

- `src/App.tsx`
- `countable: false`인 frame은 `scoresRef`, `feedbackSamplesRef`, reps/progress 갱신에서 제외한다.
- 메시지는 계속 보여준다.

### 3. 피드백 빈도 감소

위치:

- `final/s02_backend/server.py`
- `FEEDBACK_INTERVAL_FRAMES`

기본값:

```text
8 frames
```

환경변수로 조정 가능:

```powershell
$env:FEEDBACK_INTERVAL_FRAMES="12"
```

## 테스트 기준

1. 몸 일부가 카메라 밖으로 나가면 app에 카메라 위치 조정 메시지가 떠야 한다.
2. 그 동안 score 평균과 reps는 증가하지 않아야 한다.
3. 다시 전신이 잡히면 기존 흐름대로 score/reps가 재개되어야 한다.
4. 피드백 메시지가 매 프레임 단위로 과하게 바뀌지 않아야 한다.
