# TTS Pipeline

## Input

React `SessionResult`:

- `exercise`
- `sets`
- `score`
- `grade`
- `totalReps`
- `durationMinutes`
- `accuracy`
- `finalFeedback[]`

## Backend

Endpoint:

```http
POST /api/tts/final-feedback
Content-Type: application/json
```

Steps:

1. `build_final_feedback_script()`가 최종 분석 문장을 조합한다.
2. payload hash로 파일명을 만든다.
3. 같은 payload의 WAV가 이미 있으면 캐시 파일을 반환한다.
4. 없으면 `pyttsx3`로 WAV를 생성한다.
5. `/assets/tts/<filename>.wav`를 반환한다.

## Frontend

`ResultPanel`:

1. `음성 생성` 버튼 클릭
2. `requestFinalFeedbackTts(result)` 호출
3. 성공 시 audio player 표시
4. 실패 시 오류 메시지 표시

## Latency Rule

TTS는 운동 종료 후 1회 요청으로만 동작한다. 실시간 경로에는 추가하지 않는다.
