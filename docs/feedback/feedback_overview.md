# 피드백 시스템 개요

## 구조

```
feedback_config.py   ← 운동별 분석 기준 정의 (관절, 임계값, 분류 규칙)
       ↓
FeedbackEngine       ← "지금 뭐가 틀렸나?" 분석
       ↓
FeedbackPolicy       ← "언제 보여줄까?" 표시 타이밍 제어
       ↓
UIRenderer           ← 텍스트 메시지 + 빨간색 관절 시각화
```

---

## FeedbackEngine — 분석 로직

매 DTW 계산 주기(`dtw_interval` 프레임)마다 `analyze()`가 호출된다.

### 판단 순서

```
1. DTW 거리 없음       →  "측정 중입니다."
2. 관절 신뢰도 < 0.25  →  "자세를 다시 화면 중앙에 맞춰주세요."
3. 전체 부위 상태 분류 →  부위별 DTW 거리 슬라이스 최댓값 + 방향 분류
4. 가장 나쁜 부위 선택 →  심각도 최대 부위
5. threshold 미달       →  "자세가 안정적입니다." (ok)
6. threshold 초과       →  해당 부위 피드백 메시지 반환 (spike)
```

### 출력 (candidate dict)

```python
{
    "body_part":  "knee",                              # 가장 나쁜 부위 ("ok" / "pending" 포함)
    "state":      "too_forward",                       # 오류 상태
    "severity":   0.18,                                # 심각도 (DTW 거리)
    "message":    "무릎이 너무 앞으로 나갔어요.",       # 화면 출력 문구
    "bad_joints": frozenset({LEFT_KNEE, RIGHT_KNEE}),  # 빨간색 강조 관절
    "all_candidates": {                                # 전체 부위 candidates (Policy 누적용)
        "torso": { ... },
        "hip":   { ... },
        "knee":  { ... },
        "ankle": { ... },
    },
}
```

`body_part`가 `"ok"` / `"pending"`이면 `bad_joints`는 빈 `frozenset()`이다.  
`all_candidates`의 각 부위는 threshold 여부와 무관하게 항상 분류된 상태·메시지를 담는다.

### Config 기반 설계

운동·뷰 조합별로 `feedback_config.py`에 분석 기준을 정의한다.  
새 운동 추가 시 `FeedbackEngine` 코드는 수정하지 않아도 된다.

| 설정 항목 | 역할 |
|----------|------|
| `joints` | 해당 부위 관절 인덱스 (bad_joints 강조에도 사용) |
| `dtw_slice` | joint_distances에서 해당 부위 범위 |
| `threshold` | spike 판정 심각도 기준 |
| `classify` | 오류 방향 판단 규칙 (`axis_compare` / `gap_compare`) |

---

## FeedbackPolicy — 표시 타이밍

### 두 가지 케이스

| | Case 1 (spike) | Case 2 (누적) |
|-|---------------|--------------|
| 조건 | 부위 심각도 > threshold | 모든 부위 < threshold (ok 상태) |
| 동작 | 즉시 표시 + hold 시작 | hold_frames 동안 누적 → 만료 시 평균 최악 부위 표시 |
| 버퍼 | 클리어 | 부위별 severity 누적 |

### 동작 흐름

```
[Case 1: spike]
bad 후보 도착 → 즉시 메시지 표시, 버퍼 초기화, hold 시작
hold 중       → 모든 새 후보 무시
hold 만료     → "측정 중입니다." 초기화

[Case 2: 누적]
ok 후보 도착  → all_candidates의 부위별 severity 버퍼에 누적
              → 첫 ok 후보 시 accumulation 타이머 시작 (hold_frames)
타이머 만료   → 버퍼 내 평균 최악 부위 선택 → 해당 부위 메시지 표시, hold 시작
hold 만료     → "측정 중입니다." 초기화
```

### 타임라인 예시 (hold_frames=30, dtw_interval=3)

```
[Case 1]
frame  0: spike 후보 → "무릎이 너무 앞으로 나갔어요." 표시, expire=30
frame  3: 어떤 후보  → hold 중 → 무시
frame 30: hold 만료  → "측정 중입니다."

[Case 2]
frame  0: ok 후보 → 누적 시작, accumulation expire=30
frame  3: ok 후보 → 누적 계속
frame  6: ok 후보 → 누적 계속
frame 30: 타이머 만료 → 평균 최악 부위 "어깨를 더 펴주세요." 표시, expire=60
frame 33: 어떤 후보  → hold 중 → 무시
frame 60: hold 만료  → "측정 중입니다."
```

### 왜 이 구조인가

- DTW는 3프레임마다 실행되므로 hold 없이 매번 갱신하면 0.1초마다 메시지가 바뀐다.
- spike는 즉각 교정이 필요하므로 바로 표시한다.
- ok 상태에서도 상대적으로 나쁜 부위를 hold_frames 평균으로 걸러 보여줌으로써 노이즈를 줄인다.

---

## UIRenderer — 시각화

bad_joints에 포함된 관절은 유저 패널에서 빨간색·큰 원으로 표시된다.

| | 일반 관절 | bad 관절 |
|-|---------|---------|
| 색상 | 좌(초록) / 우(파랑) / 중앙(흰색) | 빨간색 `(0, 0, 255)` |
| 반지름 | 4px | 9px |
| 연결선 | 일반 색상 | 빨간색 |

전문가 패널에는 적용하지 않는다.

---

## 새 운동 추가 시 수정 파일

1. `backend/feedback/feedback_config.py` — 운동·뷰 분석 기준 추가
2. `backend/feedback/feedback_templates.py` — 피드백 메시지 템플릿 추가
3. `backend/config.py` — 운동 설정 추가 (`"view"` 키 포함)
