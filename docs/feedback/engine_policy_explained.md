# FeedbackEngine & FeedbackPolicy 동작 설명

## 두 모듈의 역할 분리

| 모듈 | 질문 | 역할 |
|------|------|------|
| `FeedbackEngine` | **"지금 뭐가 틀렸나?"** | DTW 계산 주기마다 분석 → 전체 부위 candidates 생성 |
| `FeedbackPolicy` | **"언제 보여줄까?"** | spike 즉시 표시 / ok 누적 후 최악 부위 표시 |

---

## 전체 데이터 흐름 (main.py 기준)

```python
# n >= n_frames and n % dtw_interval == 0 블록 내
window_dist_matrix, best_expert_idx = comparator.compare(window_seq, expert_cache.sequence)
expert_kp = expert_cache.sequence[int(best_expert_idx[-1])]
feedback_candidate = feedback_engine.analyze(
    user_raw_keypoints=kp,
    user_norm_keypoints=norm_kp,
    expert_norm_keypoints=expert_kp,
    joint_distances=window_dist_matrix[-1],
)

# 매 프레임 호출 (DTW 미계산 구간엔 candidate=None)
feedback_message, feedback_bad_joints = feedback_policy.update(n, feedback_candidate)

result = {
    "feedback":   feedback_message,     # UIRenderer 중앙 패널 텍스트
    "bad_joints": feedback_bad_joints,  # UIRenderer 유저 패널 빨간색 관절
}
```

---

## FeedbackEngine

### `analyze()` 판단 순서

```
1. joint_distances 없음  →  "측정 중입니다." (pending/warming_up)
2. 신뢰도 < 0.25        →  "자세를 다시 화면 중앙에 맞춰주세요." (pending/low_confidence)
3. 전체 부위 상태 분류  →  모든 body_part에 대해 DTW 거리 + 방향 분류
4. 최악 부위 선택       →  심각도(DTW 거리 최댓값) 기준
5. threshold 미달        →  "자세가 안정적입니다." (ok)
6. threshold 초과        →  해당 부위 템플릿 메시지 반환 (spike)
```

### 출력 형식

```python
{
    "body_part":  "knee",                              # 최악 부위 ("ok" / "pending" 포함)
    "state":      "too_forward",                       # 오류 상태
    "severity":   0.18,
    "message":    "무릎이 너무 앞으로 나갔어요.",
    "bad_joints": frozenset({LEFT_KNEE, RIGHT_KNEE}),
    "all_candidates": {          # 전체 부위 — Policy의 Case 2 누적에 사용
        "torso": {"body_part": "torso", "state": "...", "severity": 0.07, "message": "...", "bad_joints": ...},
        "hip":   { ... },
        "knee":  { ... },
        "ankle": { ... },
    },
}
```

`all_candidates`의 각 부위는 threshold 미달 여부와 무관하게 항상 분류된 상태·메시지를 가진다.  
`body_part`가 `"ok"` / `"pending"`일 때 `bad_joints`는 빈 `frozenset()`이다.

### 부위별 심각도: `_body_scores()`

```python
score = max(joint_distances[start:end])   # dtw_slice 범위의 최댓값
```

#### squat/side 부위 정의

| 부위 | DTW 슬라이스 | 관절 | threshold |
|------|-------------|------|-----------|
| `torso` | `[0:2]` | LEFT_SHOULDER, RIGHT_SHOULDER | 0.10 |
| `hip`   | `[2:4]` | LEFT_HIP, RIGHT_HIP           | 0.10 |
| `knee`  | `[4:6]` | LEFT_KNEE, RIGHT_KNEE         | 0.12 |
| `ankle` | `[6:8]` | LEFT_ANKLE, RIGHT_ANKLE       | 0.10 |

### 상태 분류: `_classify_state()`

| 타입 | 동작 |
|------|------|
| `axis_compare` | 관절 좌표 평균을 축으로 비교 → 차이 < `axis_tolerance`면 `generic`, 초과 시 `pos`/`neg` |
| `gap_compare` | 관절 간 간격 차이 > `gap_threshold`면 `gap_state`, 미달 시 `axis_compare`로 폴백 |

> 관절 좌표는 `[y, x, confidence]` 순서. `keypoints[:, 0]` = y, `keypoints[:, 1]` = x.

---

## FeedbackPolicy

### 두 가지 케이스

| | Case 1 (spike) | Case 2 (누적) |
|-|---------------|--------------|
| 조건 | `body_part` not in `{"ok", "pending"}` | `body_part == "ok"` |
| 동작 | 즉시 메시지·bad_joints 갱신, hold 시작 | `all_candidates` 부위별 severity 버퍼 누적 |
| 버퍼 | 클리어 | 축적 |
| 만료 시 | "측정 중입니다." 초기화 | 평균 최악 부위 표시 → 새 hold 시작 |

### `update()` 동작 흐름

```
타이머 만료 확인
    accumulation 타이머였으면 → 버퍼 평균 최악 부위 선택 → 표시 hold 시작 (Case 2)
    표시 hold였으면           → "측정 중입니다." 초기화

표시 hold 중 → 즉시 return (새 후보 무시)

candidate 처리
    spike (body_part not in ok/pending) → 즉시 표시, 버퍼 초기화, 표시 hold 시작
    ok                                  → all_candidates 누적, accumulation 타이머 미설정 시 시작
    pending                             → 아무것도 하지 않음
```

### 타임라인 예시 (hold_frames=30, dtw_interval=3)

```
[Case 1]
frame  0: spike  → "무릎이 너무 앞으로 나갔어요.", expire=30, 버퍼 클리어
frame  3: 후보   → 표시 hold 중 → 무시
frame 30: 만료   → "측정 중입니다."

[Case 2]
frame  0: ok     → 누적 시작, accumulation expire=30
frame  3: ok     → 누적 계속
frame 30: 만료   → 평균 최악 부위 → "어깨를 더 펴주세요.", expire=60 (표시 hold)
frame 33: 후보   → 표시 hold 중 → 무시
frame 60: 만료   → "측정 중입니다."
```

### `_is_accumulating` 플래그

`_expire_at`은 accumulation 타이머와 표시 hold 타이머 두 용도로 쓰인다.  
`_is_accumulating = True`이면 타이머 활성 중에도 ok 후보를 받아 누적한다.  
`_is_accumulating = False`이면 표시 hold — 모든 후보를 무시한다.

---

## UIRenderer — bad_joints 처리

| 대상 | 조건 | 색상 | 반지름 |
|------|------|------|--------|
| 관절 점 | `idx in bad_joints` | `(0, 0, 255)` 빨간색 | `BAD_JOINT_RADIUS = 9` |
| 관절 점 | 일반 | 좌/우/중앙 색상 | `JOINT_RADIUS = 4` |
| 엣지 선 | 한쪽 끝이라도 bad_joints | `(0, 0, 255)` | — |

전문가 패널에는 적용하지 않는다.

---

## 새 운동 추가 체크리스트

1. `backend/feedback/feedback_config.py` — `EXERCISE_CONFIGS`에 `(exercise, view)` 항목 추가
2. `backend/feedback/feedback_templates.py` — 해당 운동의 메시지 템플릿 추가
3. `backend/config.py` — `EXERCISES`에 운동 설정 추가 (`"view"` 키 포함)
4. `FeedbackEngine`, `FeedbackPolicy` 코드는 변경 불필요
