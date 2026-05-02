# 05 — RepDetector

## 책임

정규화된 관절 시퀀스에서 운동 1회 구간을 감지한다.
감지 방법은 `config.py`의 `rep_detector_type`으로 종목별로 지정한다.

---

## 스쿼트 감지 방법 (`"squat"`)

힙 y좌표가 n프레임 평균 감소(하강) 후 n프레임 평균 증가(상승)하는 구간을 1회로 판정한다.
n은 `config.py`에서 관리한다.

---

## 입출력 스펙

| 항목 | 내용 |
|------|------|
| 입력 | 정규화된 관절 시퀀스 shape `(M, 17, 3)` dtype `float32` |
| 입력 | `rep_detector_type`: 감지 방법 문자열 (config.py에서 읽어옴) |
| 출력 | 1회 구간 목록 `list[tuple[int, int]]` — `(start_frame, end_frame)` |

---

## 완료 기준

테스트 영상(`assets/test_videos/test_squat.mp4`) 1회 시퀀스를 입력했을 때 구간이 1개 감지되는지 확인.
