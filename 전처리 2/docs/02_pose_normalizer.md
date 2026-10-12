# 02 — PoseNormalizer

## 책임

관절 좌표에서 체형(키, 체격) 차이를 제거한다.
정규화 타입은 `config.py`에서 지정하며, 세션 내내 고정된 기준 관절을 사용한다.

---

## 입출력 스펙

| 항목 | 내용 |
|------|------|
| 입력 | 관절 좌표 shape `(17, 3)` dtype `float32` |
| 입력 | `normalizer_type`: `"front"` / `"side_left"` / `"side_right"` |
| 출력 | 정규화된 관절 좌표 shape `(17, 3)` dtype `float32` |

- confidence 값은 변경 없이 그대로 유지한다.
- 타입별 기준 관절: `"front"` → 양쪽 힙/어깨 중심, `"side_left"` → `LEFT_HIP`·`LEFT_SHOULDER`, `"side_right"` → `RIGHT_HIP`·`RIGHT_SHOULDER`

---

## 완료 기준

전문가 영상 첫 프레임에 `config.py`의 `normalizer_type`을 적용했을 때, 기준 힙 관절이 원점에 위치하고 몸통 길이가 1.0인지 확인.
