# Scoring Normalization Lenient v1

이 버전은 기존 좌표 정규화는 유지하면서 점수와 실시간 피드백 판정을 덜 빡빡하게 조정한 테스트 버전이다.

## 현재 정규화 방식

이미 `PoseNormalizer`가 적용되어 있다.

- 위치 정규화: 골반 또는 한쪽 hip을 원점으로 이동
- 크기 정규화: shoulder-hip 거리로 나눔
- smoothing: 최근 `norm_buffer_size` 프레임의 origin/scale 평균 사용

즉 사람 키, 카메라 거리, 화면 내 위치 차이는 어느 정도 보정된다.

## 한계

현재 정규화는 회전 정규화가 아니다.

- 사용자가 전문가 영상보다 몸을 더 틀면 점수가 크게 떨어질 수 있다.
- 카메라가 좌우/상하로 기울면 점수가 빡빡해질 수 있다.
- side 운동에서 실제 촬영 방향이 `side_left`와 반대면 오차가 커질 수 있다.

## 완화한 값

### ScoreEngine

`final/s01_preprocessing/config.py`

```text
max_distance: 1.0 -> 1.35
```

효과:

- 같은 DTW 거리여도 점수 하락폭이 줄어든다.
- 운동 초반/카메라 각도 차이에서 0점 근처로 급락하는 상황을 줄인다.

### Feedback threshold

`final/s01_preprocessing/feedback/feedback_config.py`

```text
body threshold: 0.10 -> 0.16
body threshold: 0.12 -> 0.18
axis_tolerance: 0.02 -> 0.04
gap_threshold: +0.03 수준 완화
```

효과:

- 미세한 차이는 즉시 경고하지 않는다.
- 빨간 관절 표시와 경고 메시지가 덜 자주 뜬다.

## 다음 후보

이 버전으로도 빡빡하면 다음은 단순 threshold가 아니라 정규화 자체를 개선해야 한다.

- shoulder-hip 벡터 회전 보정
- 좌/우 side 자동 판정
- 운동별 핵심 관절만 score에 더 크게 반영
- 초반 1~2초 calibration 구간 추가
