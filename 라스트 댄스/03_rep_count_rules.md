# 03 Rep Count Rules

현재 rep count는 피드백 기반이 아니라 각도 기반 상태 머신이다.

파일:

- `final/s01_preprocessing/rep_rules.py`
- `final/s01_preprocessing/joint_angles.py`
- `final/s01_preprocessing/rep_signals.py`
- `final/s01_preprocessing/rep_detector.py`

## 기본 원칙

1. 시작 자세에 들어온다.
2. 목표 각도를 확실히 통과한다.
3. 최소 가동범위를 만족한다.
4. 다시 시작 자세 쪽으로 돌아온다.
5. 최소 프레임 길이를 만족하면 1회로 센다.

작은 흔들림은 세지 않는다.

## 상태 머신

```text
WAIT_READY
  -> 시작 자세 확인
WAIT_TARGET
  -> 목표 각도 통과
WAIT_RETURN
  -> 시작 자세 쪽으로 복귀하면 rep count +1
```

## 현재 운동별 기준

| 운동 | 기준 관절 | 시작 | 목표 | 복귀 | 최소 가동범위 |
| --- | --- | ---: | ---: | ---: | ---: |
| squat | hip-knee-ankle 무릎 각도 | 155 이상 | 125 이하 | 150 이상 | 25 |
| hammer_curl | shoulder-elbow-wrist 팔꿈치 각도 | 145 이상 | 75 이하 | 135 이상 | 55 |
| pullup | shoulder-elbow-wrist 팔꿈치 각도 | 140 이상 | 95 이하 | 130 이상 | 35 |
| lateral_raise | hip-shoulder-wrist 어깨 각도 | 30 이하 | 70 이상 | 40 이하 | 35 |

## 수정 방법

threshold를 바꾸려면:

1. `final/s01_preprocessing/rep_rules.py`를 연다.
2. `ANGLE_REP_RULES` 값을 수정한다.
3. `python -m py_compile final\s01_preprocessing\rep_detector.py`를 실행한다.
4. 함수 단위 테스트와 WebSocket 테스트를 각각 2회 이상 확인한다.

## 너무 안 세질 때

- `target`을 완화한다.
- `min_range`를 낮춘다.
- `return`을 완화한다.

예:

```py
"squat": {
    "target": 130.0,
    "min_range": 20.0,
}
```

## 너무 쉽게 세질 때

- `target`을 더 강하게 한다.
- `min_range`를 높인다.
- `ready`와 `return` 차이를 더 명확히 둔다.

예:

```py
"squat": {
    "target": 115.0,
    "min_range": 35.0,
}
```

## 주의

- 전문가 영상 phase와 rep count는 같은 기준이 아니다.
- rep count는 사용자의 실제 관절 움직임 기준이다.
- feedback message 변경으로 rep을 세면 안 된다.
- confidence가 낮은 frame을 어떻게 처리할지는 다음 개선 대상이다.
