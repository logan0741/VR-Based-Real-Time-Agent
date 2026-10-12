# 04 — DTWComparator

## 책임

사용자의 실시간 정규화 시퀀스와 ExpertPoseCache의 전문가 시퀀스를 DTW로 정렬하고, 프레임별 관절 거리를 계산한다.
비교에 사용할 관절은 `config.py`의 `keypoints_used`에서 읽어온다.

---

## 입출력 스펙

| 항목 | 내용 |
|------|------|
| 입력 | 사용자 정규화 시퀀스 shape `(M, K, 3)` dtype `float32` |
| 입력 | 전문가 정규화 시퀀스 shape `(N, K, 3)` dtype `float32` |
| 입력 | `keypoints_used`: 비교할 관절 인덱스 목록 |
| 출력 | 프레임별 관절 거리 shape `(M, K)` dtype `float32` |

- M: 사용자 프레임 수, N: 전문가 프레임 수, K: 사용할 관절 수
- confidence 값은 비교에서 제외하고 `[y, x]`만 사용한다.

---

## 완료 기준

`assets/test_videos/test_squat.mp4`를 사용자 입력으로 사용하여 전문가 시퀀스와 비교했을 때 출력 거리가 0에 가까운지 확인.
(테스트 영상은 전문가 영상과 동일한 영상을 사용)
