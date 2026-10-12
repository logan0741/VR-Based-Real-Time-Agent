# SMPL-X 피팅과 좌표계

## 1. 3D 를 얻는 세 경로

| 경로 | 코드 | 입력 → 출력 | 속도 | 이 브랜치에서의 위치 |
| --- | --- | --- | --- | --- |
| SMPL-X 최적화 피터 (Phase 1) | `fitter.py OptimizationPoseFitter` | 2D 17×3 → SMPL-X global_orient(3) + body_pose(63) + 3D 관절 | 문서상 ≈540 ms/frame | 서버 `FITTER_BACKEND=optimization`, 오프라인 기본 피터 |
| SMPL-X 좌표 피터 | `smplx_coordinate_fitter.py SMPLXCoordinateFitter` | 3D 관절 17×3 → SMPL-X 파라미터 | 측정 기록 없음 | `--check-all` 의 smplx_coordinate_fit, `--smplx-fit-pose3d` |
| MLP 리프터 | `lifter_model.py PoseLifterMLP` | 2D 17×3 → 3D 관절 17×3 | 문서상 ≈5 ms/frame | 오프라인 `--lifter-checkpoint`, 학습 대상 |

540 ms 와 5 ms 는 당시 HANDOFF 문서(docs-archive 의 `HANDOFF.md`)에 적힌 값이다. 이 정리에서 다시 재지 않았다. [model_3d_deep_analysis.md](../40_분석_기록/model_3d_deep_analysis.md) §3 의 "MLP 0.05 ms GPU, 최적화 50–200 ms GPU" 는 측정이 아니라 추정표다.

### 최적화 피터 (2D 리프로젝션)

- SMPL-X 모델 파라미터는 고정하고, 프레임마다 `global_orient`(3)·`body_pose`(63)만 Adam 으로 최적화한다. 직전 프레임 값에서 출발한다(warm start). betas·손·얼굴은 0.
- 손실 = 신뢰도 가중 2D 리프로젝션 오차 + 포즈 prior (`SMPLX_POSE_PRIOR_WEIGHT=0.001`).
- 기본 15회 반복, lr 0.03, 가상 핀홀 카메라 640×480, f=500, 깊이 2.5 (`.env.example` 의 `SMPLX_*`, `CAMERA_*`).
- 15회 반복이라 프레임마다 수렴한다는 보장이 없다. 정확도는 QA 이미지(`reprojection_check.png`, `optimization_loss.png`)로만 확인했다.

### 좌표 피터 (3D → SMPL-X)

- 3D 관절을 타깃으로 global_orient, body_pose, scale, translation 을 맞춘다. 손실 = 3D 관절 오차(가중 1.0) + 리프로젝션(가중 0.01).
- 프로젝트의 핵심 질문 "SMPL-X 가 좌표를 받아 3D 몸을 맞출 수 있나" 의 실현 가능성 테스트였다. 2026-04-09 check-all 에서 pose_3d_v3 한 프레임으로 status ok, 무릎각 143.6° (`model_3d/artifacts/smplx_coordinate_fit_response.json`).

## 2. SMPL-X 회전 규약

- SMPL-X 는 **오른손 좌표계**, 관절 회전은 **axis-angle**(회전축 × 각도, 라디안)이다.
- `body_pose` 63 = 21 관절 × 3. 순서: left_hip, right_hip, spine1, left_knee, right_knee, spine2, left_ankle, right_ankle, spine3, left_foot, right_foot, neck, left_collar, right_collar, head, left_shoulder, right_shoulder, left_elbow, right_elbow, left_wrist, right_wrist.
- 각 회전은 **부모 뼈 기준 local rotation** 이다 (world rotation 아님). v2 1차 시도가 이것을 world rotation 으로 학습해 이중 회전이 났다.
- Unity(왼손 좌표계)나 FBX 를 거친 Three.js 에 적용할 때는 축 부호를 바꿔야 한다. 당시 결론은 Three.js 에서 `axis = (rx, -ry, -rz) / θ` 였다 (Unity 공식 `SMPLX.cs` 의 `QuatFromRodrigues` 와 수학적으로 같음). 이 변환을 쓰던 프런트 코드는 Avatar3D 쪽이며 이 브랜치에는 없다.

## 3. ★주의: 배포 체크포인트는 SMPL-X 파라미터가 아니라 3D 관절을 낸다

2026-06-08 에 찾은 근본 원인이다 ([3d_avatar_experiment_log.md (docs-archive)](https://github.com/logan0741/VR-Based-Real-Time-Agent/blob/docs-archive/3d_avatar_experiment_log.md) §1, 실험 3).

| 모델 | 정의 위치 | 출력 |
| --- | --- | --- |
| `PoseLifterMLP` | `model_3d/lifter_model.py` | 17×3 = 51, **3D 관절 좌표** |
| `PoseLifterNet` | `model_3d/server_app/server.py` (v2 는 `train_smplx_v2.py`) | 3 + 63 = 66, **SMPL-X global_orient + body_pose** |

`fitness_pose_lifter_latest_best.pt` 는 `PoseLifterMLP` 로 학습된 것이다. 서버는 이것을 `PoseLifterNet` 에 `strict=False` 로 싣고, 출력 앞 3개를 global_orient, 다음 63개를 body_pose 로 읽는다. 당시 증상은 "global_orient 가 항상 X 축 −40° → 전신이 앞으로 쓰러짐" 이었다.

**2026-10-12 재확인 — 실제로는 가중치가 하나도 실리지 않는다.** 체크포인트는 `{model_state, optimizer_state, epoch, config, metrics}` 딕셔너리로 저장된다. 서버는 이 딕셔너리 전체를 state_dict 로 넘기므로 `strict=False` 가 최상위 키 5개를 "unexpected" 로, 모델 파라미터 18개를 "missing" 으로 조용히 넘기고 `[Lifter] Weights loaded successfully.` 를 찍는다. 원래 작업 폴더의 체크포인트로 직접 확인한 결과:

```text
top-level keys: ['model_state', 'optimizer_state', 'epoch', 'config', 'metrics']
missing: 18 unexpected: ['model_state', 'optimizer_state', 'epoch', 'config', 'metrics']
params changed after load: 0 / 18
final layer shape in ckpt: network.16.weight (51, 512)   ← 서버 모델은 (66, 512)
```

즉 이 브랜치 서버의 `body_pose`·`global_orient` 는 **초기화된 무작위 가중치의 출력**이다. `model_state` 를 꺼내 넘겨도 마지막 층 크기(51 vs 66)가 달라 실패한다. 2D 뷰어는 입력 2D 키포인트(`keypoints_2d`)만 그리므로 이 문제와 상관없이 돌았다.

## 4. PoseLifterMLP 출력 3D 관절의 좌표계

### 검증된 규약 (2026-10-12, 체크포인트 출력 48개로 측정) — **Y-up · cm**

| 성분 | 의미 | Three.js (Y-up) |
| --- | --- | --- |
| `pt[0]` | 좌우 (lateral) | X |
| `pt[1]` | **높이 (height, Y-up)** | Y |
| `pt[2]` | 깊이 (depth) | Z (카메라 방향에 따라 −Z) |

단위는 **cm** 다. Three.js 도 Y-up 이므로 축 교환은 필요 없고, **cm→m 스케일과 골반 원점 이동**만 하면 된다. 근거는 바로 아래 측정값과 학습 타깃이다. `/api/expert-pose3d` 는 v3 재학습 무렵 `final/s02_backend/server.py` 에 추가된 엔드포인트이고, 이 브랜치의 서버(`model_3d/server_app/server.py`)에는 없다.

### 출처 미확인 과거 메모 (커밋된 경로에서 재현 안 됨)

재편 전 세션 메모와 실험 로그에는 아래 두 서술이 있었다. **둘 다 위 측정과 맞지 않으므로 쓰지 않는다.**

| 서술 | 내용 | 왜 못 믿나 |
| --- | --- | --- |
| 세션 메모 | `pt[1]`=깊이→−Z, `pt[2]`=높이(Z-up)→Y, `new THREE.Vector3(pt[0], pt[2], -pt[1])`, "코 z≈92 > 어깨 77 > 골반 37 > 무릎 1 > 발목 −35 cm" | 값 범위(−35~92)가 라벨의 절대 높이(0~160)와 다르고, 커밋된 어떤 `/api/expert-pose3d` 도 MLP 를 돌리지 않는다(아래). 골반 정렬이나 다른 입력 공간에서 나온 값으로 추정 |
| 실험 로그 `3d_avatar_experiment_log.md` §5 | "x=깊이(앞뒤), y=좌우, z=높이 → `[y→X, z→Y, x→Z]`" | **입력 2D+깊이 키포인트**(다른 좌표 공간)를 보고 내린 서술. 출력 측정과 맞지 않는다 |

### 측정 — 이 브랜치 코드로 학습 분포 입력을 넣었을 때 (2026-10-12)

이 브랜치의 `FitnessLabelDataset` 입력(013 검증 파일 3개, 48 샘플 평균)을 `v3_pose3d/pose3d_best.pt` 에 그대로 넣으면 **`pt[1]` 이 높이**로 나온다:

```text
nose       pt0=   -4.0 pt1=  159.5 pt2=   26.9
L shoulder pt0=   10.7 pt1=  144.5 pt2=   15.0
L hip      pt0=    7.7 pt1=   93.8 pt2=   11.0
L knee     pt0=   12.8 pt1=   61.7 pt2=   16.4
L ankle    pt0=   11.9 pt1=   24.5 pt2=    9.3
```

이유는 학습 타깃에 있다. `fitness_points_to_3d_array` 는 013 3D 라벨의 x, y, z 를 변환 없이 쓰고, 그 라벨은 y 가 높이(cm, 코 평균 약 160)다. `export_fitness_unity.py` 도 같은 라벨을 `unity_y_up_z_forward` 로 내보낸다. 배포 체크포인트(`fitness_pose_lifter_latest_best.pt`)도 같은 결과였다 (코 pt1 159.3).

과거 메모가 다른 값을 낸 경로는 확인하지 못했다. 알아낸 것과 가능성:

- 저장소에 커밋된 모든 버전(61eaf995b, f11e24b60, 4faebc599, docs-archive 17188859b)의 `/api/expert-pose3d` 는 MLP 를 돌리지 않고 MotionBERT 결과 파일 `squat_expert_keypoints_3d_mb.json` 을 그대로 돌려준다. 그 파일은 y 가 아래쪽(코 y≈−0.97, 발목 y≈+1.0, 대략 m)이라 과거 메모와도, 위 측정과도 다르다. 따라서 과거 메모의 값은 커밋되지 않은 다른 버전의 엔드포인트나 다른 입력에서 나왔을 것이다.

1. 그 경로에서 MLP 출력에 축 변환이나 골반 기준 정렬이 들어갔을 수 있다 (값 범위 −35~92 가 절대 높이 0~160 과 다르다).
2. 입력이 학습 입력과 달랐을 수 있다. 학습 입력은 `[x/W, y/H, conf]` 인데 서버 입력은 MoveNet `[y, x, score]` 이다 (`KEYPOINT_FORMAT=movenet_yx`). x·y 가 뒤바뀐 분포 밖 입력이면 출력 축의 의미가 학습 때와 달라질 수 있다.

**쓰는 쪽에서 해야 할 일**: 3D 관절을 소비하는 코드는 자기가 받는 데이터에서 코·골반·발목 값을 직접 찍어 높이 축을 확인한다. 이 브랜치의 학습·평가·Unity 내보내기 경로는 Y-up(`pt[1]`=높이, cm)이다. Avatar3D 브랜치의 README "좌표계 규약 모음" 도 같은 결론이다.

## 5. MotionBERT 시도 (`tools/run_motionbert.py`)

- 시간 문맥이 있는 리프터(MotionBERT-Lite, 243 프레임 창)로 전문가 스쿼트 131프레임을 3D 로 올려 본 기록이다.
- COCO-17 → H36M-17 로 바꿔 넣고 결과를 다시 COCO 순서로 돌려 `data_samples/squat_expert_keypoints_3d_mb.json` 에 저장했다 (`coord_note: x=right, y=down(negate for ThreeJS Y-up), z=depth`, 단위 대략 m).
- 필요한 것: 루트 `MotionBERT/` (저장소 + `checkpoint/pose3d/FT_MB_lite_MB_ft_h36m_global_lite/best_epoch.bin`), CUDA (`map_location='cuda'`), 입력 `data_samples/squat_expert_keypoints.json` (docs-archive 에서 꺼낸다 — [01_데이터셋.md](../10_데이터/01_데이터셋.md) §5).
- 이 결과를 아바타에 붙이는 작업은 Avatar3D 쪽에서 이어졌다.
