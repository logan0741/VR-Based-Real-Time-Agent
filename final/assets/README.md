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

## 전문가 키포인트

`squat_left_1_keypoints.json` — 스쿼트 레퍼런스 포즈 267프레임  
서버 `/api/expert` 엔드포인트에서 서빙됨.

## SMPLX-Unity 패키지

`SMPLX-Unity/` — Meta/MPI 공식 Unity SMPL-X 패키지  
`.gitignore` 처리됨 (용량 큼). 별도 다운로드 필요.
