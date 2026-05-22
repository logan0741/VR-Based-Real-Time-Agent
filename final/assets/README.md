# Assets

## SMPL-X 모델

| 파일 | 경로 | 용도 |
|------|------|------|
| neutral model | `smplx_locked_head/neutral/model.npz` | 서버 피팅용 |
| male model | `smplx_locked_head/male/model.npz` | 예비 |
| female model | `smplx_locked_head/female/model.npz` | 예비 |

모델 파일은 `.gitignore` 처리됨. 라이선스: MPI-IS SMPL-X.

## PoseLifterMLP 체크포인트

| 파일 | 경로 | 설명 |
|------|------|------|
| best | `model_3d/artifacts/checkpoints/fitness_pose_lifter_latest_best.pt` | 최적 체크포인트 |
| latest | `model_3d/artifacts/checkpoints/fitness_pose_lifter_latest.pt` | 최근 체크포인트 |

체크포인트는 `.gitignore` 처리됨. 재학습: `python run_steps.py --train`

## 전문가 영상 (Expert Videos)

`final/assets/expert_videos/` — DTW 비교 및 강사 스켈레톤 표시에 사용되는 영상/사전처리 데이터.

| 파일 | 용도 |
|------|------|
| `squat_full.mp4` | 스쿼트 4회 전문가 영상 |
| `squat_full.npy` | 사전 처리된 전문가 keypoints 캐시 (있으면 mp4 재처리 생략) |
| `hammer_curl.mp4` | 해머컬 전문가 영상 |
| `lateral_raise.mp4` | 레터럴 레이즈 전문가 영상 |
| `pull_up.mp4` | 풀업 전문가 영상 |

> **바이너리 파일은 `.gitignore` 처리됨.** 별도 전달 필요.  
> `.npy` 캐시가 없으면 서버 시작 시 `squat_full.mp4`에서 자동 생성됨.

## 전문가 키포인트

`squat_left_1_keypoints.json` — 스쿼트 레퍼런스 포즈 267프레임  
서버 `/api/expert` 엔드포인트에서 서빙됨.

## SMPLX-Unity 패키지

`SMPLX-Unity/` — Meta/MPI 공식 Unity SMPL-X 패키지  
`.gitignore` 처리됨 (용량 큼). 별도 다운로드 필요.
