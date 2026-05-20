# 기획·구현 과정 문제 해결 정리

---

## 문제 1. DTW 적용 시 프레임 밀도 불일치

### 문제
전문가 영상(25fps)과 사용자 카메라(실시간)의 프레임 수가 다르면,
같은 동작을 수행해도 DTW가 비교하는 프레임 밀도 자체가 달라져 거리 값이 왜곡된다.

### 해결 방향
양쪽 모두 동일한 `target_fps`로 처리하여 프레임 밀도를 통일한다.

### 코드 적용

**`backend/config.py`**
```python
"target_fps": 24,  # 전문가 영상 샘플링 및 사용자 처리 목표 fps
```

**`backend/expert_cache.py`** — 부동소수점 누적 방식으로 균일 샘플링
```python
sample_interval: float = original_fps / target_fps  # 예: 25 / 24 = 1.0416...
next_sample: float = 0.0

while True:
    ret, frame = cap.read()
    if frame_idx >= next_sample:
        keypoints = estimator.predict(frame)
        frames.append(normalizer.normalize(keypoints))
        next_sample += sample_interval
    frame_idx += 1
```
정수 간격으로 끊으면 프레임 오차가 누적되므로 부동소수점으로 누적하여 오차를 최소화한다.

**사용자 측**: CameraSession에서도 동일한 `target_fps` 기준으로 프레임을 처리한다.

DTW 자체는 M ≠ N 길이를 워핑 경로로 정렬하므로 완전히 같은 길이일 필요는 없지만,
밀도를 통일하면 워핑 경로의 왜곡이 줄어든다.

---

## 문제 2. 운동별 중요 관절이 DTW 계산에 반영되지 않음

### 문제
스쿼트는 하체 관절(무릎·힙·발목)이 중요하고, 상체 끝 관절(손목·팔꿈치)은 덜 중요하다.
모든 관절을 동등하게 DTW에 포함하면 중요하지 않은 관절이 점수를 희석한다.

### 해결 방향
config에서 종목별로 사용할 관절과 가중치를 명시적으로 지정한다.
DTWComparator는 지정된 관절만 비교하고, ScoreEngine은 관절별 가중치를 적용한다.

### 코드 적용

**`backend/config.py`**
```python
"keypoints_used": [
    LEFT_SHOULDER, RIGHT_SHOULDER,
    LEFT_HIP, RIGHT_HIP,
    LEFT_KNEE, RIGHT_KNEE,
    LEFT_ANKLE, RIGHT_ANKLE,
],
"weights": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
```

**`backend/dtw_comparator.py`**
```python
user_kp = user_seq[:, self._keypoints_used, :YX_DIM]    # (M, K, 2)
expert_kp = expert_seq[:, self._keypoints_used, :YX_DIM]  # (N, K, 2)
```
비교 전 `keypoints_used`로 슬라이싱하여 지정된 K개 관절만 DTW에 투입한다.

종목 추가 시 `config.py`의 `keypoints_used`와 `weights`만 수정하면 된다.

---

## 문제 3. DTW 계산 단위 — 관절별 계산 vs 통합 계산

### 문제
- **관절별**: 무릎끼리, 힙끼리 따로 DTW → 관절별 기여도를 분리할 수 있음
- **통합**: 모든 관절을 하나의 벡터로 묶어 한 번에 DTW → 전체 자세 유사도를 단일 경로로 계산

| 방식 | 장점 | 단점 |
|------|------|------|
| 관절별 | 관절별 점수·가중치 분리 가능, 종목 확장 유연 | DTW K번 실행 |
| 통합 | 자세 전체의 공간적 상관관계 반영 | 관절별 기여도 추출 불가, 가중치 적용 복잡 |

### 해결 방향
출력이 `(M, K)` 형태의 관절별 거리 행렬이어야 ScoreEngine에서 가중치를 독립적으로 적용할 수 있으므로
**관절별 개별 DTW**를 선택한다.

### 코드 적용

**`backend/dtw_comparator.py`**
```python
for k in range(K):
    path = dtw_ndim.warping_path(user_kp[:, k, :], expert_kp[:, k, :])
    # 관절 k에 대해 개별 워핑 경로 계산
    ...
result  # shape: (M, K), dtype: float32
```

---

## 문제 4. DTW 거리 집계 기준 — 최소값 vs 평균값

### 문제
DTW 워핑 경로는 사용자 1개 프레임에 전문가 여러 프레임이 매핑될 수 있다.
이 경우 해당 사용자 프레임의 거리를 어떻게 집계할지 결정이 필요하다.

| 기준 | 의미 | 특성 |
|------|------|------|
| 최솟값 | 전문가 프레임 중 가장 유사한 것과 비교 | 점수가 후해짐, 이상치에 강함 |
| 평균값 | 매핑된 전문가 프레임들의 평균 거리 | 안정적, 전체 정렬 품질 반영 |

### 해결 방향
최솟값은 워핑이 유리한 구간만 선택하는 효과가 있어 점수를 과대평가한다.
**평균값**을 사용하면 워핑 경로 전체의 정렬 품질을 균형 있게 반영한다.

### 코드 적용

**`backend/dtw_comparator.py`**
```python
frame_dists: list[list[float]] = [[] for _ in range(M)]

for user_idx, expert_idx in path:
    dist = float(np.linalg.norm(user_kp[user_idx, k] - expert_kp[expert_idx, k]))
    frame_dists[user_idx].append(dist)

for m in range(M):
    result[m, k] = float(np.mean(frame_dists[m]))  # 평균값 적용
```

---

## 문제 5. 운동 1회 구간 검출

### 문제
실시간 점수 외에 운동 1회 단위 점수를 계산하려면 1회의 시작·끝 프레임을 감지해야 한다.
단순한 방법으로는 다음 두 가지 경계 문제가 발생한다.

**5-1. 감지 신호 선택**
정규화 후 힙(hip) y좌표는 항상 원점(≈0)이므로 움직임 신호가 없다.

→ **무릎(knee) y좌표** 사용: 스쿼트 하강 시 무릎이 힙 쪽으로 접혀 정규화 무릎 y가 감소,
상승 시 증가하여 명확한 오실레이션 신호가 된다.

**5-2. 경계 기준 모호성**

valley(바닥) 기준으로 rep을 정의하면 첫 rep와 나머지 rep의 구조가 달라진다.

```
서있음 | 하락 | 바닥 | 상승 | 서있음 | 하락 | 바닥 | 상승
Rep 1  | Rep 1| 경계 | Rep 2| Rep 2  | Rep 2| 경계 | Rep 3
```
→ Rep 1은 하락만 포함, Rep 2는 상승+하락 포함으로 비대칭.

**5-3. 마지막 rep 미감지**

peak(서있음) 기준으로 정의하면 마지막 rep 이후 다시 앉지 않아
마지막 서있음이 peak로 감지되지 않아 마지막 rep가 기록되지 않는다.

### 해결 방향: valley+peak 상태 머신

valley(하강→상승 전환)와 peak(상승→하강 전환)를 순차적으로 감지하고,
peak를 찾을 때 rep를 기록한다. 마지막 rep는 시퀀스 종료를 암묵적 경계로 처리한다.

```
상태: WAIT_VALLEY ──(valley 감지)──→ WAIT_PEAK
                                          │
                                   (peak 감지) → rep 기록 → WAIT_VALLEY
                                          │
                               (시퀀스 종료, valley 있음) → rep 기록
```

| 상황 | 결과 |
|------|------|
| valley → peak | rep 기록, 상태 초기화 |
| valley → 시퀀스 종료 | 마지막 rep 기록 |
| valley 없이 시퀀스 종료 | rep 없음 |

### 코드 적용

**`backend/rep_detector.py`**
```python
for i in range(1, len(slopes)):
    prev, curr = slopes[i - 1], slopes[i]

    if state == _RepState.WAIT_VALLEY and prev < 0 and curr > 0:
        state = _RepState.WAIT_PEAK                        # valley 감지

    elif state == _RepState.WAIT_PEAK and prev > 0 and curr < 0:
        reps.append((rep_start, i))                        # rep 기록
        rep_start = i
        state = _RepState.WAIT_VALLEY

if state == _RepState.WAIT_PEAK:
    reps.append((rep_start, len(slopes) - 1))             # 마지막 rep 처리
```

**노이즈 필터링**: `rep_slope_window=15`(기울기 평활화)와 `min_rep_frames=24`(최소 rep 길이)를
config에서 조정하여 짧은 노이즈 구간을 제거한다.

```
squat_full.mp4(4회) 테스트 결과: 4개 구간 정상 감지
squat.mp4(1회) 테스트 결과: 1개 구간 정상 감지 (마지막 rep 처리 검증)
```
