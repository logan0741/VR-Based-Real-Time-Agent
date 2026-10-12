
# 3D 아바타 포즈 연동 실험 로그

작성일: 2026-06-08  
브랜치: FOR-VR-APP

---

## 목표

웹캠 → 2D 포즈 → MLP → SMPL-X 파라미터 → Three.js FBX 아바타 실시간 애니메이션

---

## 최종 확인된 사실들

### 1. 서버 (FastAPI, final/s02_backend/server.py)

- **PoseLifterNet** (server.py 내부 정의): 17×3 → 66차원 (global_orient[3] + body_pose[63])
- **PoseLifterMLP** (model_3d/lifter_model.py): 17×3 → 17×3 3D 관절 좌표 (다른 모델!)
- 기존 체크포인트 (`fitness_pose_lifter_latest_best.pt`)는 **PoseLifterMLP** 학습 → 3D 좌표 출력
- 서버가 이것을 `strict=False`로 PoseLifterNet에 로드 → **출력이 SMPL-X 파라미터가 아님**
- 이것이 포즈가 이상한 근본 원인

### 2. SMPL-X 좌표 변환 (smplMath.ts)

Unity 공식 SMPLX.cs의 `QuatFromRodrigues`:
```csharp
Vector3 axis = new Vector3(-rodX, rodY, rodZ);  // X만 부정
float angle_deg = -axis.magnitude * Rad2Deg;    // 각도도 부정
// 수학적으로 axis=(rx, -ry, -rz), angle=+theta 와 동일
```

**Three.js에서 올바른 변환** (smplx_integration_status.md에서 확인):
```typescript
const axis = new THREE.Vector3(rx / theta, -ry / theta, -rz / theta);
```
- FBX가 Unity 왼손 좌표계 기준 → FBXLoader가 오른손으로 변환 → Y, Z flip 필요

### 3. SMPL-X body_pose 구조 (AvatarController.cs에서 확인)

```
body_pose[0:3]   → left_hip     (pelvis 기준 local rotation)
body_pose[3:6]   → right_hip
body_pose[6:9]   → spine1
body_pose[9:12]  → left_knee    (left_hip 기준 local rotation)
body_pose[12:15] → right_knee
body_pose[15:18] → spine2
body_pose[18:21] → left_ankle
body_pose[21:24] → right_ankle
body_pose[24:27] → spine3
body_pose[27:30] → left_foot
body_pose[30:33] → right_foot
body_pose[33:36] → neck
body_pose[36:39] → left_collar
body_pose[39:42] → right_collar
body_pose[42:45] → head
body_pose[45:48] → left_shoulder
body_pose[48:51] → right_shoulder
body_pose[51:54] → left_elbow
body_pose[54:57] → right_elbow
body_pose[57:60] → left_wrist
body_pose[60:63] → right_wrist
```

**중요**: 각 관절의 rotation은 **parent bone 기준 local rotation** (world rotation이 아님)

### 4. FBX bone 이름 (smplx.fbx)

파일에 SMPL-X 22개 관절 이름이 모두 포함됨:
```
root, pelvis, left_hip, right_hip, spine1, left_knee, right_knee,
spine2, left_ankle, right_ankle, spine3, left_foot, right_foot,
neck, left_collar, right_collar, head, left_shoulder, right_shoulder,
left_elbow, right_elbow, left_wrist, right_wrist
```

### 5. 3D 관절 좌표계 (PoseLifterMLP v3 출력)

- **좌표계**: x=깊이(앞뒤), y=좌우, z=높이 (**Z-up**)
- Three.js로 변환: `[3d_y → Tx, 3d_z → Ty, 3d_x → Tz]`
- 단위: cm

---

## 실험 기록

### 실험 1: Bone 매핑 문제 (해결됨)

**문제**: `SMPL_JOINT_NAMES[i].replace('_', '')` = `'lefthip'`인데 FBX bone은 `'left_hip'` → 이름 불일치로 fallback 인덱스 매핑 사용 → 오른손 손가락 bone에 hip rotation 적용

**해결**: `boneName === SMPL_JOINT_NAMES[i]` exact match로 변경 → 22/22 정확히 매핑

---

### 실험 2: expert-smplx API 개선

**문제**: `squat_left_1_keypoints.json` 삭제 → API 에러

**해결**: `ExpertPoseCache.raw_sequence` (서버 시작 시 로드된 256프레임)를 MLP에 통과시켜 SMPL-X params 생성

---

### 실험 3: global_orient 문제

**현상**: MLP 출력 global_orient가 항상 X축 -40도 기울어짐 → 전신이 앞으로 쓰러짐

**원인**: 기존 PoseLifterMLP가 SMPL-X params를 예측하는 게 아니라 3D 좌표를 예측하도록 학습됨. 서버가 이 출력을 global_orient + body_pose로 잘못 해석

**임시 해결**: global_orient를 [0,0,0]으로 강제 → 전신 수직 유지

---

### 실험 4: smplMath.ts 좌표 변환 실험

| 시도 | 변환 | 결과 |
|------|------|------|
| 1차 | `(rx, -ry, -rz)` | smplx_integration_status에서 올바른 것으로 확인됨 |
| 2차 | `(rx, ry, rz)` | "3D Y-up에서 학습됐으니 flip 불필요"로 변경 → 틀림 |
| 3차 | `(rx, -ry, -rz)` | SMPLX.cs 분석 후 복원 |

**결론**: `(rx, -ry, -rz)` 이 올바름 (Unity FBX → FBXLoader Three.js 변환 특성)

---

### 실험 5: MLP v2 재학습 (방향 B - SMPL-X params)

**목표**: 3D 관절 좌표 → SMPL-X body_pose 변환 후 MLP 재학습

**1차 시도**:
- `prepare_smplx_dataset.py`: 각 bone의 T-pose → actual 방향 **world rotation** 계산
- 문제: SMPL-X body_pose는 **local rotation**인데 world rotation으로 학습 → 이중 회전 적용으로 이상한 자세

**2차 시도 (계층적 local rotation)**:
- parent bone world rotation의 inverse × world rotation = local rotation
- 계층 순서대로 처리: pelvis → hip → knee → ...
- 학습 완료: val_loss 0.08, best_epoch 209

**문제**: 추론 시 global_orient가 여전히 25-50도 기울어짐
- 원인: 학습 데이터(5개 고정 카메라)와 추론 데이터(raw_sequence, 다른 카메라)의 도메인 불일치

**현재 상태**: 이론적으로 올바른 구조이나 실제 포즈 품질 미흡

---

### 실험 6: MLP v3 재학습 (방향 A - 3D 관절 좌표)

**목표**: PoseLifterMLP (17×3 → 17×3 3D 좌표)를 올바르게 재학습

**결과**: Best epoch 88, **MPJPE 10.87mm** (우수한 3D 좌표 예측 정확도)

**새 엔드포인트**: `/api/expert-pose3d` 추가 (server.py)

---

### 실험 7: Skeleton3DCanvasV2 - 3D 좌표 직접 구동 (방향 A)

**목표**: 3D 관절 좌표로 FBX bone을 직접 구동

**구현 순서**:
1. T-pose 방향 → actual 방향 world rotation 계산
2. `parent.getWorldQuaternion()` × inv = local rotation
3. bone.quaternion에 적용 후 `bone.updateMatrixWorld(true)`

**문제들**:
- 초기 좌표 변환 오류: `[x,y,z]` 그대로 사용 → "배에서 꺾이고 손이 아닌 팔이 꺾임"
- 수정: 3D(Z-up) → Three.js(Y-up) 변환 `[y→x, z→y, x→z]`
- `parent.getWorldQuaternion()`이 이전 프레임 값 반환 (행렬 미업데이트)
- `rest.multiply(worldRot)` 방식이 틀림

**부분 성공**: 하체(무릎/고관절 굽힘)는 어느 정도 표현됨  
**실패 원인**: SMPL-X body_pose는 **parent 기준 local rotation**인데, world rotation을 그대로 적용

**결론**: 방향 A (3D 좌표로 bone 직접 구동)는 SMPL-X 구조와 근본적으로 맞지 않음. bone.parent.getWorldQuaternion() 기반 접근도 Three.js SkinnedMesh에서 프레임마다 올바르게 작동하지 않음

---

## 현재 파일 상태

### 체크포인트
| 파일 | 모델 | 설명 |
|------|------|------|
| `model_3d/artifacts/checkpoints/fitness_pose_lifter_latest_best.pt` | PoseLifterMLP | 17×3→17×3 3D 좌표 (기존) |
| `model_3d/artifacts/checkpoints/v2/smplx_lifter_best.pt` | PoseLifterNet | 17×3→66 SMPL-X (계층적 local rotation, v2) |
| `model_3d/artifacts/checkpoints/v3_pose3d/pose3d_best.pt` | PoseLifterMLP | 17×3→17×3 3D 좌표 (재학습, MPJPE 10.87mm) |

### 주요 수정 파일
- `src/utils/smplMath.ts`: `(rx, -ry, -rz)` 변환 (Unity SMPLX.cs와 동일)
- `src/components/Skeleton3DCanvas.tsx`: exact bone name match, SLERP smoothing, framesRef 방식
- `src/components/Skeleton3DCanvasV2.tsx`: 3D 좌표 기반 (방향 A, 현재 미사용)
- `src/hooks/useExpertPose.ts`: state → ref 방식 (React re-render 방지)
- `src/hooks/useExpertPose3d.ts`: `/api/expert-pose3d` 훅
- `final/s02_backend/server.py`: `/api/expert-smplx`, `/api/expert-pose3d` 엔드포인트
- `model_3d/prepare_smplx_dataset.py`: 계층적 local rotation 계산
- `model_3d/train_smplx_v2.py`: PoseLifterNet 재학습 스크립트
- `.env`: `LIFTER_CHECKPOINT=model_3d/artifacts/checkpoints/v2/smplx_lifter_best.pt`

---

## 미해결 문제

### 핵심 문제: 올바른 SMPL-X ground truth 없음

MLP가 올바른 SMPL-X body_pose를 출력하려면:
- **입력**: 2D keypoints (17×3, MoveNet [y,x,conf] 형식)
- **출력**: SMPL-X body_pose (63차원 local axis-angle)

현재 학습 데이터 (`013.피트니스자세`)의 ground truth는:
- 3D 관절 좌표 (24개 관절 x,y,z)
- SMPL-X body_pose 값이 없음

계층적 변환으로 3D 좌표 → local axis-angle을 근사하였으나:
1. 도메인 불일치 (학습 카메라 vs 추론 카메라)
2. 근사치라 정확도 한계

### 근본 해결 방법 (미실행)

**옵션 A**: AMASS 데이터셋 (SMPL-X 파라미터 ground truth 포함) 사용 → MLP 재학습  
**옵션 B**: SMPLify-X로 기존 3D 좌표 데이터에서 정확한 body_pose 추출  
**옵션 C**: 3D 관절 좌표 기반으로 단순 기하학적 IK (무릎 각도만 계산)

---

## 2D 시스템 상태 (정상 작동)

- **2D 뷰어** (`http://localhost:8000/viewer/`): 119 FPS, 0.0ms latency ✅
- WebSocket 연결, 실시간 스쿼트 포즈 인식 ✅
- MediaPipe 클라이언트 정상 작동 ✅
- 전문가 포즈 2D 비교 정상 작동 ✅

---

## 다음 작업 시 고려사항

1. **smplMath.ts는 `(rx, -ry, -rz)` 유지** — SMPLX.cs 분석으로 검증됨
2. **방향 A는 SMPL-X 구조와 맞지 않음** — 3D 좌표로 local rotation 계산이 근본적으로 어려움
3. **MLP 학습 데이터**: 2D 입력은 `[y/H, x/W, conf]` 형식 (MoveNet yx, 정규화 0-1)
4. **전문가 포즈 데이터**: `ExpertPoseCache.raw_sequence` 사용 (squat_full.npy에서 로드)
5. **서버 체크포인트**: v2 (계층적 local rotation)가 현재 .env에 설정됨
6. **FBX 크기**: public/smplx.fbx = 1.54MB (스켈레톤 포함, 메시 있음)
