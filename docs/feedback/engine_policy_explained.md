# FeedbackEngine & FeedbackPolicy 동작 설명

## 두 모듈의 역할 분리

| 모듈 | 질문 | 역할 |
|------|------|------|
| `FeedbackEngine` | **"지금 뭐가 틀렸나?"** | DTW 계산 주기마다 분석 → 후보 dict 생성 |
| `FeedbackPolicy` | **"지금 보여줄 건가?"** | bad 후보 도착 시 `hold_frames`(2초) 동안 고정, hold 중 새 후보 무시 |

---

## 전체 데이터 흐름 (main.py 기준)

```
[VideoCapture / 웹캠]
      ↓  frame: np.ndarray (H, W, 3) BGR
PoseEstimator.predict(frame)
      ↓  kp: (17, 3) float32  [y, x, confidence]  ← user_raw_keypoints
PoseNormalizer.normalize(kp)
      ↓  norm_kp: (17, 3) float32  몸통 길이 기준 정규화  ← user_norm_keypoints
      |
      ├─ norm_seq.append(norm_kp)
      |
      └─ DTWComparator.compare(window_seq, expert_cache.sequence)
              ↓  window_dist_matrix: (n_frames, K) float32,  best_expert_idx: (n_frames,)
              |   마지막 행 window_dist_matrix[-1] = 현재 프레임 기준 관절별 DTW 거리
              ↓  joint_distances: (K,)  ← joint_distances
```

이 네 값(`kp`, `norm_kp`, `expert_kp`, `joint_distances`)이
DTW 계산 주기마다 `FeedbackEngine.analyze()`에 전달된다.

```python
# main.py 핵심 호출부 (n >= n_frames and n % dtw_interval == 0 블록 내)
window_dist_matrix, best_expert_idx = comparator.compare(window_seq, expert_cache.sequence)
expert_kp = expert_cache.sequence[int(best_expert_idx[-1])]  # DTW가 맞춘 전문가 프레임
feedback_candidate = feedback_engine.analyze(
    user_raw_keypoints=kp,
    user_norm_keypoints=norm_kp,
    expert_norm_keypoints=expert_kp,
    joint_distances=window_dist_matrix[-1],
)

# DTW 블록 밖 — 매 프레임 호출 (DTW 미계산 구간엔 candidate=None 전달)
feedback_message, feedback_bad_joints = feedback_policy.update(n, feedback_candidate)

result = {
    ...,
    "feedback":   feedback_message,     # UIRenderer 중앙 패널 텍스트
    "bad_joints": feedback_bad_joints,  # UIRenderer 유저 패널 빨간색 관절
}
canvas = renderer.render(frame, result)
```

> `expert_cache.sequence`는 앱 시작 시 전문가 영상을 한 번 처리해 만든 정규화 시퀀스.
> `expert_kp`는 DTW 비교 결과 `best_expert_idx[-1]`로 선택한 전문가 프레임으로,
> 단순 프레임 번호 클램프가 아닌 DTW가 시퀀스 전체에서 가장 잘 맞춘 전문가 자세를 비교 기준으로 쓴다.

---

## 아키텍처: Config-Driven 구조

`FeedbackEngine`은 운동·뷰 조합에 따라 분석 기준이 달라진다.
예를 들어 스쿼트 측면(`squat/side`)과 풀업 정면(`pullup/front`)은
확인해야 할 관절과 판단 기준이 완전히 다르다.

이를 하드코딩 대신 **`feedback_config.py`에 사전 정의**해두고, 엔진은 이를 읽어 동작한다.

```
feedback_config.py     ← 운동·뷰별 관절/임계값/분류규칙 사전 정의
        ↓
FeedbackEngine         ← config를 읽어 분석 (로직 범용, 종목 무관)
        ↓ candidate dict (message + bad_joints 포함)
FeedbackPolicy         ← 표시 시점 제어 (hold_frames 동안 고정)
        ↓ (message, bad_joints)
UIRenderer             ← 중앙 패널에 message, 유저 패널에 빨간색 관절 표시
```

### `feedback_config.py` 구조

```python
EXERCISE_CONFIGS: dict[tuple[str, str], ExerciseViewCfg]
# 키: (exercise, view), 예: ("squat", "side")
```

각 항목은 아래 TypedDict로 구성된다.

```
ExerciseViewCfg
├── confidence_joints: tuple[int, ...]     # 신뢰도 확인 관절 인덱스
└── body_parts: dict[str, BodyPartCfg]
        └── BodyPartCfg
              ├── joints: tuple[int, ...]   # 위치 오차 계산 관절 (bad_joints 강조에도 사용)
              ├── dtw_slice: (start, end)   # joint_distances 슬라이스
              ├── threshold: float          # 피드백 발생 심각도 기준
              └── classify: ClassifyRule    # 오류 상태 분류 규칙
```

`ClassifyRule`은 두 가지 타입을 지원한다.

| 타입 | 동작 |
|------|------|
| `axis_compare` | 관절 좌표 평균을 축(axis)으로 비교 → 차이가 `axis_tolerance` 미만이면 `generic`, 초과 시 `pos` / `neg` 상태 반환 |
| `gap_compare` | 관절 간 간격 차이 확인 후 `gap_threshold` 초과 시 `gap_state` 반환, 미달 시 axis_compare로 폴백 |

#### 뷰별 분석 부위 결정 원칙

- **측면(side)**: 좌우 이동(balance)은 카메라에 보이지 않으므로 포함하지 않음.
  무릎 좌우 간격(misaligned)도 측면 2D 영상에선 판단 불가 → 제외.
- **정면(front)**: balance·misaligned가 오히려 핵심 확인 항목이 됨.

새 운동/뷰 조합 추가 시 `EXERCISE_CONFIGS`에 항목을 추가하면 되고,
`FeedbackEngine` 코드는 변경하지 않아도 된다.

---

## FeedbackEngine

### 생성자

```python
FeedbackEngine(exercise: str, view: str)
# 예: FeedbackEngine("squat", "side")
```

`EXERCISE_CONFIGS[(exercise, view)]`를 로드한다.
지원하지 않는 조합이면 `ValueError`를 발생시킨다.

### 진입점: `analyze()`

```python
analyze(
    user_raw_keypoints,    # (17, 3) 원본 — confidence 확인용
    user_norm_keypoints,   # (17, 3) 정규화 — 위치 오차 계산용
    expert_norm_keypoints, # (17, 3) 전문가 — 비교 기준
    joint_distances,       # (K,) DTW 거리 벡터
)
```

내부에서 아래 순서로 동작한다.

```
1. joint_distances가 None/empty  →  "측정 중입니다."  (warming_up)
2. 핵심 관절 confidence < 0.25   →  "자세를 다시 화면 중앙에 맞춰주세요."  (low_confidence)
3. config 부위별 심각도 계산     →  _body_scores()
4. 심각도 최대 부위 선택         →  max(scores)
5. 해당 부위 threshold 미달      →  "자세가 안정적입니다."  (ok)
6. threshold 초과                →  _classify_state()로 상태 판단 → 템플릿 문구 반환
```

### 부위별 심각도: `_body_scores()`

config에 정의된 각 부위에 대해 DTW 거리 슬라이스의 최댓값을 심각도로 삼는다.

```python
score = max(joint_distances[start:end])   # dtw_slice 범위의 최댓값
```

#### squat/side 현재 정의된 부위

| 부위 | DTW 슬라이스 | 관절 | threshold |
|------|-------------|------|-----------|
| `torso` | `[0:2]` | LEFT_SHOULDER, RIGHT_SHOULDER | 0.10 |
| `hip`   | `[2:4]` | LEFT_HIP, RIGHT_HIP           | 0.10 |
| `knee`  | `[4:6]` | LEFT_KNEE, RIGHT_KNEE         | 0.12 |
| `ankle` | `[6:8]` | LEFT_ANKLE, RIGHT_ANKLE       | 0.10 |

### 상태 분류: `_classify_state()`

심각도 최대 부위가 결정되면, config의 `classify` 규칙으로 구체적 상태를 결정한다.

#### squat/side 현재 분류 결과

| 부위 | 판단 기준 | 상태 |
|------|----------|------|
| `torso` | 사용자 어깨 x 평균 > 전문가 | `too_forward` |
| `torso` | 사용자 어깨 x 평균 < 전문가 | `too_upright` |
| `hip`   | 사용자 골반 y 평균 > 전문가 | `too_low`     |
| `hip`   | 사용자 골반 y 평균 < 전문가 | `too_high`    |
| `knee`  | 사용자 무릎 x 평균 > 전문가 | `too_forward` |
| `knee`  | 사용자 무릎 x 평균 < 전문가 | `too_backward`|

> 관절 좌표는 `[y, x, confidence]` 순서임에 주의.
> `keypoints[:, 0]` = y(세로), `keypoints[:, 1]` = x(가로).

### 출력 형식

```python
{
    "exercise":  "squat",
    "body_part": "knee",
    "state":     "too_forward",
    "severity":  0.18,
    "message":   "무릎이 너무 앞으로 나갔어요.",
    "bad_joints": frozenset({LEFT_KNEE, RIGHT_KNEE}),  # 빨간색 강조 관절 인덱스
}
```

`bad_joints`는 `body_part`가 `"pending"` / `"ok"`인 경우 빈 `frozenset()`이다.

---

## FeedbackPolicy

### 생성자

```python
FeedbackPolicy(hold_frames: int)
# 예: FeedbackPolicy(hold_frames=cfg["target_fps"] * 2)
# squat(24fps) → 48프레임, hammer_curl·pullup(30fps) → 60프레임
```

### 진입점: `update()`

```python
update(frame_idx: int, candidate: dict[str, object] | None) -> tuple[str, frozenset[int]]
```

반환값: `(피드백 메시지, 빨간색으로 강조할 관절 인덱스 집합)`

#### 동작 흐름

```
hold 활성 (frame_idx < _expire_at)
    → 새 candidate 무시
    → 현재 (message, bad_joints) 그대로 반환

hold 만료 (frame_idx >= _expire_at)
    → message = "측정 중입니다.", bad_joints = frozenset() 으로 초기화
    → _expire_at = -1

candidate가 있고 body_part가 bad 상태 (pending·ok 제외)
    → message, bad_joints 갱신
    → _expire_at = frame_idx + hold_frames  (새 hold 시작)

candidate가 없거나 ok/pending
    → 현재 상태 유지
```

#### 타임라인 예시 (hold_frames=60, dtw_interval=3)

```
frame  0: bad 후보 도착  → message="무릎이 너무 앞으로 나갔어요.", expire=60
frame  3: bad 후보 도착  → hold 중 → 무시
frame  6: ok  후보 도착  → hold 중 → 무시
frame 60: hold 만료      → "측정 중입니다.", bad_joints={}
frame 63: bad 후보 도착  → message 갱신, expire=123
```

### 왜 hold 중에 새 후보를 무시하는가

- DTW 계산은 `dtw_interval`마다 (기본 3프레임) 실행된다.
- hold 없이 매번 갱신하면 메시지가 3프레임마다 바뀌어 읽을 수 없다.
- ok 후보가 즉시 bad를 덮으면 오류 표시가 순식간에 사라진다.
- hold 기간 동안 고정함으로써 사용자가 2초간 충분히 인지하고 교정할 수 있다.

### 초기 상태

인스턴스 생성 직후 `_active_message = "측정 중입니다."`, `_active_bad_joints = frozenset()`으로
초기화되어 있어서 DTW가 계산되기 전 구간에도 화면에 빈 칸 없이 표시된다.

---

## UIRenderer의 bad_joints 처리

`render()`는 `result["bad_joints"]`를 읽어 `_build_user_panel()`에 전달한다.

`_draw_skeleton()`에서 bad_joints 처리:

| 대상 | 조건 | 색상 | 반지름 |
|------|------|------|--------|
| 관절 점 | `idx in bad_joints` | `COLOR_BAD = (0, 0, 255)` (빨간색) | `BAD_JOINT_RADIUS = 9` |
| 관절 점 | 일반 | 좌/우/중앙 색상 | `JOINT_RADIUS = 4` |
| 엣지 선 | 양 끝 중 하나라도 bad_joints | `COLOR_BAD` | — |
| 엣지 선 | 일반 | 좌/우/중앙 색상 | — |

전문가 패널에는 bad_joints를 적용하지 않는다 (유저 패널 전용).

---

## 두 모듈의 연결 흐름

```
[DTW 계산 주기 (n >= n_frames and n % dtw_interval == 0)]
    FeedbackEngine.analyze()
        → candidate dict 반환 (body_part, state, severity, message, bad_joints)
    그 외 프레임 → candidate = None

[매 프레임: FeedbackPolicy.update(frame_idx, candidate)]
    hold 중이면 → 새 후보 무시, 현재 상태 반환
    hold 만료   → 초기화
    bad 후보    → 갱신 + hold 시작
    → (message, bad_joints) 반환

[UIRenderer]
    → 중앙 패널에 message 텍스트 표시
    → 유저 패널에서 bad_joints 관절·엣지를 빨간색·큰 원으로 표시
```

계산(Engine)과 표시 시점(Policy)을 분리했기 때문에, 향후 정책만 바꿔도
— 쿨다운, 투표, 심각도 우선순위 등 — Engine은 손대지 않아도 된다.

---

## 새 운동 추가 체크리스트

1. `backend/feedback/feedback_config.py` — `EXERCISE_CONFIGS`에 `(exercise, view)` 항목 추가
2. `backend/feedback/feedback_templates.py` — 해당 운동의 메시지 템플릿 추가
3. `backend/config.py` — `EXERCISES`에 운동 설정 추가 (`"view"` 키 포함)
4. `FeedbackEngine`, `FeedbackPolicy` 코드는 변경 불필요
