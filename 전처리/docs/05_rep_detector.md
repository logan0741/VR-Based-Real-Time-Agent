# 05 — RepDetector

## 책임

정규화된 관절 프레임을 1개씩 입력받아 운동 1회 구간을 증분으로 감지한다.
감지 방법은 `config.py`의 `rep_detector_type`으로 종목별로 지정한다.

---

## 스쿼트 감지 방법 (`"squat"`)

무릎 y좌표의 기울기 부호 전환으로 valley·peak를 감지한다.

1. **diff 계산** — 새 프레임의 무릎 y값과 직전 저장값의 차이
2. **기울기 계산** — 최근 `slope_window`개 diff의 평균 (고정 크기 버퍼 유지)
3. **상태 전환 판정** — 직전 기울기와 현재 기울기의 부호 비교
   - `WAIT_VALLEY` 상태에서 기울기 음→양 전환: `WAIT_PEAK`으로 전환
   - `WAIT_PEAK` 상태에서 기울기 양→음 전환: rep 1회 기록, `WAIT_VALLEY`로 복귀

---

## 입출력 스펙

| 항목 | 내용 |
|------|------|
| 입력 (`__init__`) | `rep_detector_type`: 감지 방법 문자열 |
| 입력 (`__init__`) | `normalizer_type`: 무릎 관절 선택 기준 |
| 입력 (`__init__`) | `slope_window`: 기울기 계산에 사용할 diff 버퍼 크기 |
| 입력 (`__init__`) | `min_rep_frames`: 유효 rep 최소 프레임 수 |
| 입력 (`update`) | 정규화된 관절 프레임 shape `(17, 3)` dtype `float32` |
| 출력 (`update`) | 누적 rep 구간 목록 `list[tuple[int, int]]` — `(start_frame, end_frame)` |

---

## 내부 상태

| 상태 | 설명 |
|------|------|
| `_state` | 현재 상태 머신 상태 (`WAIT_VALLEY` / `WAIT_PEAK`) |
| `_rep_start` | 현재 진행 중인 rep의 시작 프레임 인덱스 |
| `_reps` | 완료된 rep 구간 목록 |
| `_frame_idx` | 지금까지 입력된 누적 프레임 수 |
| `_prev_signal` | 직전 프레임의 무릎 y값 (diff 계산용) |
| `_diff_buffer` | 최근 `slope_window`개 diff (고정 크기 deque) |
| `_prev_slope` | 직전 기울기 (부호 전환 감지용) |

---

## 완료 기준

테스트 영상(`assets/test_videos/test_squat.mp4`)을 프레임 단위로 1개씩 입력했을 때
4회 rep 구간이 감지되는지 확인.
