# 01 Pipeline

현재 구조는 핸드폰 viewer, 서버, VR/app 웹이 나뉘어 움직인다.

## 전체 흐름

1. app에서 운동과 세트 수를 선택한다.
2. app이 WebSocket으로 `session_config` 또는 `session_start`를 서버에 보낸다.
3. 서버가 `session_control`을 갱신한다.
4. viewer가 `/api/session-control` polling 또는 WebSocket 메시지로 선택 운동을 따라간다.
5. viewer가 카메라에서 MoveNet 2D keypoint를 추출한다.
6. viewer가 `/ws/pose`로 17개 keypoint frame을 서버에 보낸다.
7. 서버가 pose를 즉시 app/viewer에 relay한다.
8. 서버가 preprocessing session에서 rep count와 feedback을 계산한다.
9. app이 사용자 skeleton, 전문가 skeleton, set/reps, score, feedback을 표시한다.
10. 운동 종료 시 app이 누적 feedback sample로 최종 결과를 만든다.

## 단계별 데이터

| 단계 | 입력 | 출력 | 담당 |
| --- | --- | --- | --- |
| 운동 선택 | exercise, sets | session_control | `src/App.tsx`, `src/hooks/useWebSocket.ts` |
| 카메라 추출 | video frame | COCO-17 `[y,x,score]` | `final/s05_frontend/viewer.js` |
| 실시간 전송 | keypoints | WebSocket message | `viewer.js` |
| pose relay | keypoints | `data_type: pose` | `final/s02_backend/server.py` |
| 전처리 | keypoints | normalized keypoints | `PoseNormalizer` |
| 횟수 계산 | normalized keypoints | `rep_count` | `RepDetector` |
| 실시간 피드백 | user/expert keypoints | message, score | `FeedbackEngine` |
| set/reps 표시 | rep_count | current set/progress | `ConnectionManager.exercise_progress` |
| 전문가 포즈 | exercise, phase | expert frame | `useExpertPose2D`, `SkeletonCanvas2D`, `viewer.js` |
| 최종 결과 | feedback samples | final report | `src/App.tsx`, `ResultPanel.tsx` |

## 실시간성 기준

실시간 화면에서는 다음을 우선한다.

- pose relay는 바로 보낸다.
- 무거운 DTW는 hot path에서 줄인다.
- rep count는 각도 기반 상태 머신으로 빠르게 처리한다.
- feedback은 짧은 메시지만 표시한다.
- 최종 분석은 운동 종료 후 처리한다.

