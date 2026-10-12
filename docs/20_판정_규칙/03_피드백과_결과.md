# 04 Feedback And Result

피드백은 rep count와 분리한다.

## 실시간 피드백

목적:

- 운동 중 바로 볼 수 있는 짧은 교정 문장 제공
- 실시간성을 유지
- 변수명이나 enum key가 화면에 직접 나오지 않게 처리

주요 파일:

- `final/s01_preprocessing/feedback/feedback_engine.py`
- `final/s01_preprocessing/feedback/feedback_templates.py`
- `final/s01_preprocessing/feedback/feedback_config.py`
- `final/s01_preprocessing/feedback/feedback_policy.py`
- `src/App.tsx`
- `final/s05_frontend/viewer.js`

수정 포인트:

- 한국어 문장: `feedback_templates.py`
- 운동별 부위 기준: `feedback_config.py`
- 반복 피드백 유지 시간: `feedback_policy.py`
- app 표시: `FeedbackChip`

## 피로도/각도 분석

파일:

- `final/s02_backend/posture_analyzer.py`

현재 역할:

- 각도 기반으로 피로도 상태를 계산한다.
- squat의 무릎 각도, 허리/코어 상태를 분석한다.
- rep count에는 직접 쓰지 않는다.

주의:

- 이름은 analyzer지만 counter가 아니다.
- rep count는 `RepDetector`가 담당한다.

## 최종 피드백

파일:

- `src/App.tsx`
- `src/components/ResultPanel.tsx`

현재 방식:

- LLM 기반이 아니다.
- 운동 중 누적된 feedback sample을 집계한다.
- 평균 점수, 반복 문제 부위, 반복 메시지, 피로 부위를 요약한다.

개선 방향:

- 실시간 feedback은 짧게 유지한다.
- 최종 feedback은 자세히 만든다.
- LLM을 붙일 경우 최종 feedback 단계에만 붙인다.
- 서버 또는 app 중 한 곳을 최종 기준으로 정해야 한다.

## 피드백과 rep count를 섞지 않는 이유

피드백은 품질 평가다.

rep count는 이벤트 감지다.

둘을 섞으면 다음 문제가 생긴다.

- 자세가 나쁘면 실제 1회를 해도 카운트가 안 될 수 있다.
- 피드백 문장이 바뀌는 순간을 rep으로 잘못 셀 수 있다.
- feedback threshold를 바꾸면 rep count도 흔들린다.
- 실시간성 때문에 feedback을 가볍게 만들면 count 정확도도 같이 낮아진다.

따라서 구조는 다음처럼 유지한다.

```text
RepDetector: 몇 회 했는가
FeedbackEngine: 자세가 어떤가
FinalFeedback: 운동 전체가 어땠는가
```

