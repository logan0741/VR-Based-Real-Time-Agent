# Final Feedback TTS

이 브랜치는 운동 종료 후 생성되는 최종 자세 분석을 Python TTS로 음성 파일화하는 테스트 파이프라인입니다.

## 구성

- `final/s07_tts/tts_service.py`: 최종 피드백 JSON을 읽을 문장으로 변환하고 `pyttsx3`로 WAV 파일 생성
- `final/s02_backend/server.py`: `POST /api/tts/final-feedback` API 제공
- `final/assets/tts/`: 생성된 음성 파일 저장 위치
- `src/services/ttsApi.ts`: React 앱에서 TTS API 호출
- `src/components/ResultPanel.tsx`: 결과 화면에서 음성 생성 및 재생

## 실행 흐름

1. 운동 종료 시 React 앱이 `SessionResult`를 만든다.
2. 사용자가 결과 화면에서 `음성 생성`을 누른다.
3. 앱이 `/api/tts/final-feedback`로 최종 피드백 JSON을 보낸다.
4. 서버가 `pyttsx3`로 `final/assets/tts/final_feedback_<hash>.wav`를 생성한다.
5. 서버가 `/assets/tts/<file>.wav` URL을 반환한다.
6. 앱이 해당 WAV를 `<audio controls>`로 재생한다.

## 의도

TTS는 최종 결과 화면에서만 실행한다. 실시간 자세 처리, WebSocket 송수신, DTW 계산, 횟수 카운팅에는 TTS가 끼지 않으므로 운동 중 레이턴시를 늘리지 않는다.
