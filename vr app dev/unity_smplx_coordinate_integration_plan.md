# Unity SMPL-X 좌표 연동 계획서

작성일: 2026-06-04  
대상 브랜치: FOR-VR-APP  
대상 Unity 경로: `SMPLX-Unity/Assets/SMPLX/Scripts`

## 1. 목표

현재 웹 기반 실시간 운동 자세 분석 파이프라인에서 계산되는 좌표와 평가 결과를 Unity의 SMPL-X 모델 표시 방식에 맞춰 정리하고, Unity 화면에 사용자 아바타와 전문가 아바타를 함께 띄우는 것을 목표로 한다.

최종 목표 화면은 다음 구조다.

- 핸드폰 또는 웹 viewer에서 MoveNet 기반 2D keypoint를 추출한다.
- 서버는 COCO-17 keypoint를 받아 실시간 평가, 반복 횟수, 점수, 피드백을 계산한다.
- 서버는 동시에 Unity에서 바로 적용 가능한 SMPL-X pose payload를 만든다.
- Unity는 사용자 SMPL-X 모델을 실시간으로 움직인다.
- Unity는 전문가 SMPL-X 모델을 기준 동작으로 반복 재생한다.
- 사용자는 Unity 화면에서 자신의 모델과 전문가 모델을 동시에 비교한다.

## 2. 현재 코드 기준 구조

### 2.1 현재 입력 좌표

현재 viewer/app에서 사용되는 입력은 MoveNet 계열의 COCO-17 keypoint다.

형태:

```json
[
  [y, x, confidence],
  ...
]
```

현재 주요 사용 위치:

- `final/s05_frontend/viewer.js`
  - 핸드폰 viewer에서 keypoint를 추출한다.
  - `data_type: "keypoints"` 형태로 서버 WebSocket에 전송한다.
- `src/components/SkeletonCanvas.tsx`
  - app 화면에서 `keypoints_2d`를 2D skeleton으로 표시한다.
  - 현재 app 내 사용자 skeleton은 좌우 반전 보정을 위해 `mirror` 옵션을 사용한다.
- `final/s02_backend/server.py`
  - 서버가 keypoint payload를 받아 lifter 또는 optimization backend로 처리한다.

### 2.2 현재 서버 출력

현재 서버는 keypoint 입력을 처리한 뒤 Unity가 사용할 수 있는 pose 값을 포함해 응답한다.

핵심 응답 구조:

```json
{
  "status": "ok",
  "frame_id": "...",
  "keypoints_2d": [[y, x, confidence]],
  "fit": {
    "backend": "lifter",
    "global_orient": [float, float, float],
    "body_pose": [63 floats]
  },
  "feedback": {
    "score": 0,
    "message": "...",
    "body_part": "...",
    "severity": 0.0,
    "rep_count": 0,
    "rep_scores": []
  },
  "debug": {
    "inference_ms": 0.0,
    "smoothing_enabled": true,
    "smoothing_frame": 0
  }
}
```

Unity 연동에서 가장 중요한 값은 다음 두 개다.

- `fit.global_orient`
  - pelvis/root 방향
  - axis-angle 3개 값
- `fit.body_pose`
  - SMPL-X body joint 21개에 대한 axis-angle
  - 21 joints x 3 = 63개 값

### 2.3 현재 Unity SMPL-X 스크립트 구조

대상 경로:

`SMPLX-Unity/Assets/SMPLX/Scripts`

현재 주요 파일:

- `SMPLX.cs`
  - SMPL-X 모델의 본, shape, pose corrective를 제어하는 핵심 컴포넌트
  - `SetLocalJointRotation(jointName, quaternion)` 사용 가능
  - `QuatFromRodrigues(x, y, z)` 사용 가능
  - `UpdatePoseCorrectives()` 사용 가능
  - `SnapToGroundPlane()` 사용 가능
- `AvatarController.cs`
  - WebSocket으로 서버에 연결한다.
  - 서버 응답의 `global_orient`, `body_pose`를 받아 사용자 SMPL-X avatar에 적용한다.
  - `body_pose` 순서를 Unity SMPL-X body joint 이름 배열에 맞춰 적용한다.
- `ExpertAvatarController.cs`
  - 서버의 `/api/expert-smplx`에서 전문가 pose frame을 가져온다.
  - 전문가 SMPL-X avatar를 루프 재생한다.

즉, Unity 쪽에는 이미 “서버 pose payload를 SMPL-X 모델에 적용하는 기본 구조”가 있다. 앞으로의 핵심 작업은 서버 좌표 계산 결과가 이 Unity 적용 방식과 정확히 맞는지 검증하고 보정하는 것이다.

## 3. Unity 기준 관절 매핑

현재 `AvatarController.cs`와 `ExpertAvatarController.cs`의 `BodyJointNames` 순서는 같다.

`body_pose` 63개 값은 아래 순서로 해석된다.

| body_pose offset | SMPL-X joint |
|---:|---|
| 0:3 | left_hip |
| 3:6 | right_hip |
| 6:9 | spine1 |
| 9:12 | left_knee |
| 12:15 | right_knee |
| 15:18 | spine2 |
| 18:21 | left_ankle |
| 21:24 | right_ankle |
| 24:27 | spine3 |
| 27:30 | left_foot |
| 30:33 | right_foot |
| 33:36 | neck |
| 36:39 | left_collar |
| 39:42 | right_collar |
| 42:45 | head |
| 45:48 | left_shoulder |
| 48:51 | right_shoulder |
| 51:54 | left_elbow |
| 54:57 | right_elbow |
| 57:60 | left_wrist |
| 60:63 | right_wrist |

`global_orient`는 `pelvis`에 적용된다.

현재 Unity 적용 방식:

```text
global_orient -> SMPLX.QuatFromRodrigues() -> pelvis local rotation
body_pose[i*3:i*3+3] -> SMPLX.QuatFromRodrigues() -> BodyJointNames[i]
```

## 4. 현재 방식의 핵심 리스크

### 4.1 2D keypoint에서 SMPL-X pose로 바로 가는 정확도 문제

현재 서버의 lifter는 17개 2D keypoint를 받아 66개 SMPL-X pose 값을 예측한다. 이 방식은 빠르지만 다음 리스크가 있다.

- 2D 입력만으로 깊이와 회전 방향을 정확히 알기 어렵다.
- 카메라가 정면인지 측면인지에 따라 pelvis/root 방향이 흔들릴 수 있다.
- 좌우 반전 문제가 Unity 모델에서도 재발할 수 있다.
- squat처럼 하체 중심 운동은 무릎/골반/발목 각도가 조금만 틀어져도 모델 동작이 어색해질 수 있다.

따라서 Unity 연동의 첫 단계는 “모델을 띄우는 것”보다 “좌표계와 관절 순서가 맞는지 검증하는 것”이 우선이다.

### 4.2 웹 app의 mirror 보정과 Unity 좌표계 불일치 가능성

현재 React app skeleton은 사용자가 보기 편하도록 `mirror`를 적용했다. 하지만 Unity SMPL-X는 단순 화면 표시가 아니라 실제 관절 회전을 적용한다.

따라서 Unity에서는 다음을 별도로 검증해야 한다.

- 왼팔을 들었을 때 Unity의 왼팔이 움직이는가
- 오른팔을 들었을 때 Unity의 오른팔이 움직이는가
- squat에서 왼무릎/오른무릎이 반대로 해석되지 않는가
- 카메라 preview의 mirror와 서버 payload의 left/right 의미가 섞이지 않는가

Unity 모델이 반대로 움직이면 단순 화면 flip이 아니라 입력 keypoint left/right swap 또는 root rotation 보정이 필요하다.

### 4.3 Unity rootRotationOffset 보정

현재 `AvatarController.cs`에는 다음 기본값이 있다.

```text
rootRotationOffset = (0, 90, 0)
```

이 값은 side-view 영상 또는 모델 방향 보정용이다. 실제 카메라 배치에 따라 다음 후보를 테스트해야 한다.

- `(0, 0, 0)`
- `(0, 90, 0)`
- `(0, -90, 0)`
- `(0, 180, 0)`

최종값은 이론으로 고정하지 말고 실제 Meta Quest/Unity 화면에서 테스트 영상 기준으로 결정해야 한다.

### 4.4 서버 smoothing과 Unity smoothing 중복

현재 서버에는 `PoseRetargeter`가 있다.

- `body_pose` OneEuro smoothing
- `global_orient` OneEuro smoothing
- velocity clamp

Unity `AvatarController.cs`에도 smoothing이 있다.

- `Quaternion.Slerp`
- `smoothingSpeed`
- `rootSmoothingSpeed`

두 곳에서 모두 smoothing을 강하게 걸면 모델은 부드럽지만 반응이 느려진다. 운동 중 실시간성이 중요하기 때문에 중복 smoothing을 조절해야 한다.

권장 방향:

- 서버 smoothing은 튐 방지용으로 약하게 유지한다.
- Unity smoothing은 화면 표시용으로 조절한다.
- 레이턴시 테스트 시 서버 smoothing ON/OFF, Unity smoothing speed별로 비교한다.

## 5. 단계별 작업 계획

## 5.1 1단계: Unity 연동 기준 정리

목표:

Unity가 받을 payload의 기준을 고정한다.

작업:

- 서버 WebSocket 응답에서 Unity용 필드를 명확히 분리한다.
- `fit.global_orient`, `fit.body_pose`를 Unity 표준 입력으로 확정한다.
- `keypoints_2d`는 평가/디버그/웹 skeleton용으로 유지한다.
- Unity에서는 `keypoints_2d`를 직접 모델 본에 적용하지 않는다.

완료 기준:

- Unity 사용자 모델은 `global_orient/body_pose`만으로 움직인다.
- 웹 app skeleton은 `keypoints_2d` 기반으로 계속 동작한다.
- 두 표시가 같은 frame_id 기준으로 연결되어 있다.

## 5.2 2단계: 좌우/축/스케일 검증용 테스트 시나리오 작성

목표:

Unity 모델의 관절 방향이 실제 사용자 움직임과 일치하는지 검증한다.

필수 테스트 동작:

- T-pose 또는 양팔 벌리기
- 왼팔만 들기
- 오른팔만 들기
- squat 1회
- 측면 squat 1회
- 정면 squat 1회

확인 항목:

- 좌우가 반전되지 않는가
- pelvis가 뒤집히지 않는가
- 무릎이 반대로 꺾이지 않는가
- 발이 바닥에서 심하게 뜨지 않는가
- root 방향이 카메라 방향과 맞는가
- smoothing 때문에 반응이 늦지 않는가

산출물:

- `rootRotationOffset` 후보별 결과표
- left/right swap 필요 여부
- Unity smoothing 권장값
- 서버 smoothing 권장값

## 5.3 3단계: 서버 좌표 변환 계층 정리

목표:

현재 서버의 좌표 계산 결과를 Unity 적용 기준에 맞춰 안정화한다.

작업:

- `server.py` 내부의 lifter 결과 생성 부분을 Unity payload 생성 함수로 분리한다.
- `global_orient`와 `body_pose`의 shape 검증을 추가한다.
- NaN, inf, 과도한 axis-angle 값을 방어한다.
- frame마다 `debug.unity_pose_valid` 같은 검증 값을 추가하는 방안을 검토한다.
- 카메라 mirror 정책을 서버에서 명확히 고정한다.

권장 구조:

```text
MoveNet keypoints
-> keypoint validation
-> optional left/right correction
-> lifter
-> server smoothing
-> Unity pose validation
-> WebSocket response
```

완료 기준:

- `global_orient`는 항상 길이 3이다.
- `body_pose`는 항상 길이 63이다.
- Unity에서 적용할 수 없는 값은 보내지 않거나 이전 정상 frame으로 대체한다.

## 5.4 4단계: Unity 사용자 모델 표시 안정화

목표:

`AvatarController.cs`가 실시간 사용자 모델 표시용으로 안정적으로 동작하게 한다.

작업:

- WebSocket 연결 상태 표시를 Unity Inspector 또는 debug UI로 확인한다.
- 수신 frame rate를 로그로 측정한다.
- 오래된 frame을 버리고 최신 frame만 적용하는 현재 queue 정책을 유지한다.
- `smoothingSpeed` 기본값을 실시간 운동용으로 재조정한다.
- `rootRotationOffset` 기본값을 실제 테스트 결과에 맞춰 확정한다.
- `snapToGround` ON/OFF를 비교한다.

주의:

`snapToGround`는 보기에는 안정적일 수 있지만, squat 중 하체 움직임이 과하게 보정되어 실제 자세와 다르게 보일 수 있다. 테스트 후 유지 여부를 결정해야 한다.

## 5.5 5단계: 전문가 모델 동시 표시

목표:

Unity 화면에 전문가 SMPL-X 모델을 함께 표시한다.

현재 구조:

- `ExpertAvatarController.cs`는 `/api/expert-smplx`에서 전문가 frame을 가져온다.
- 각 frame은 `global_orient`, `body_pose`로 구성된다.
- Unity에서 loop playback한다.

작업:

- 서버의 `/api/expert-smplx` 응답 frame 순서와 현재 운동 종류를 맞춘다.
- app에서 선택한 운동 종류가 Unity 전문가 모델에도 반영되도록 한다.
- 사용자 아바타와 전문가 아바타를 좌우 또는 앞뒤로 배치한다.
- 전문가 playback FPS를 실제 사용자 입력 FPS와 비교한다.
- set/rep 시작 시 전문가 animation index를 reset할지 결정한다.

권장 배치:

- 사용자 모델: 화면 왼쪽 또는 중앙
- 전문가 모델: 화면 오른쪽 또는 반투명 기준 모델
- 카메라: 두 모델의 하체가 보이는 고정 시점

## 5.6 6단계: app, viewer, Unity 세 화면의 상태 동기화

목표:

현재 app에서 선택하는 운동/세트/횟수가 viewer와 Unity에도 같은 기준으로 반영되게 한다.

현재 개선된 구조:

- app에서 `session_start`를 서버로 보낸다.
- viewer가 나중에 연결되어도 서버의 session control 상태를 sync한다.
- viewer/app의 rep count 불일치를 줄이기 위한 전역 session control이 있다.

추가 계획:

- Unity `AvatarController.cs`도 `session_start`를 독립적으로 보내지 않도록 조정할지 검토한다.
- app이 session owner가 되고, Unity는 display client로만 동작하는 구조를 검토한다.
- Unity가 별도 `session_start`를 보내면 app의 세트/횟수 설정과 충돌할 수 있다.

권장 정책:

```text
app = session control owner
viewer = keypoint producer
Unity = pose display client
server = session state authority
```

이 구조로 가면 Unity는 가능하면 `session_start`를 자동으로 보내지 않고, 서버에서 현재 session state를 받아 표시하는 역할이 된다.

## 5.7 7단계: 레이턴시 측정

목표:

Unity 모델 표시가 웹 app보다 실제로 더 나은지 수치로 판단한다.

측정 구간:

1. viewer MoveNet 추론 시간
2. viewer -> server WebSocket 전송 시간
3. server lifter + smoothing 처리 시간
4. server -> Unity WebSocket 전송 시간
5. Unity WebSocket 수신 queue 대기 시간
6. Unity model apply + rendering 시간

필수 timestamp:

- `client_timestamp_ms`
- `server_received_ms`
- `server_processed_ms`
- `unity_received_ms`
- `unity_applied_ms`

비교 대상:

- 기존 app skeleton 표시 지연
- Unity 사용자 SMPL-X 모델 표시 지연
- DTW-lite OFF
- DTW-lite ON
- 서버 smoothing ON/OFF
- Unity smoothing speed별 결과

완료 기준:

- 평균 end-to-end latency
- p95 latency
- Unity 표시 FPS
- 서버 처리 FPS
- 사용자 체감 기준: 운동 중 모델이 따라온다고 느껴지는지

## 6. 역할 분리

## 6.1 사람이 해야 할 작업

- Unity Editor에서 SMPL-X prefab 배치
- 사용자 avatar와 전문가 avatar를 scene에 배치
- Meta Quest 3 또는 PC Unity Play 환경에서 화면 확인
- 실제 카메라 위치별 테스트 영상 촬영
- 좌우 반전, root 방향, 모델 어색함 여부 판단
- 운동 전문가 관점에서 자세 평가 결과가 맞는지 검수
- 최종 화면 구성 선택

## 6.2 AI가 할 수 있는 작업

- 서버 payload 구조 정리
- Unity C# 스크립트 수정
- 좌표 validation 코드 추가
- left/right swap 옵션 추가
- rootRotationOffset 후보 테스트용 config 추가
- latency timestamp 추가
- Unity debug overlay 또는 log 출력 코드 작성
- `/api/expert-smplx` 운동별 분기 추가
- app session state와 Unity display state 동기화 구조 설계
- 테스트 체크리스트 문서화

## 7. 권장 구현 순서

1. Unity에서 현재 `AvatarController.cs`만 붙여 사용자 모델이 움직이는지 확인한다.
2. 왼팔/오른팔 테스트로 좌우 반전 여부를 확인한다.
3. `rootRotationOffset` 후보를 테스트해 모델 방향을 맞춘다.
4. 서버 payload validation을 추가한다.
5. Unity 자동 `session_start` 정책을 정리한다.
6. `ExpertAvatarController.cs`로 전문가 모델을 같이 띄운다.
7. app의 운동 선택 값이 전문가 모델에도 반영되도록 연결한다.
8. end-to-end latency timestamp를 추가한다.
9. DTW-lite ON/OFF 상태에서 Unity 표시 지연을 비교한다.
10. Meta Quest 3 화면에서 최종 체감 테스트를 한다.

## 8. 우선 결정해야 할 사항

### 8.1 Unity를 최종 화면으로 쓸 것인가, 보조 화면으로 쓸 것인가

가능한 구조는 두 가지다.

1. Unity가 최종 운동 화면
   - 장점: SMPL-X 모델을 제대로 보여줄 수 있다.
   - 단점: app UI와 session control을 Unity에도 맞춰야 한다.

2. Unity는 모델 표시 전용 보조 화면
   - 장점: 현재 app 구조를 덜 건드린다.
   - 단점: 사용자는 app과 Unity 화면을 함께 봐야 할 수 있다.

현재 단계에서는 2번이 더 안전하다. Unity 표시가 충분히 안정화된 뒤 1번으로 확장하는 것이 낫다.

### 8.2 Unity가 keypoint를 직접 받을 것인가, SMPL-X pose만 받을 것인가

권장: Unity는 SMPL-X pose만 받는다.

이유:

- 현재 Unity 스크립트가 이미 `global_orient/body_pose` 적용 구조다.
- Unity에서 COCO-17을 직접 SMPL-X로 바꾸면 변환 로직이 중복된다.
- 서버에서 평가와 pose 변환을 함께 관리하는 쪽이 디버깅이 쉽다.

### 8.3 app과 Unity 중 session owner는 누구인가

권장: app이 session owner다.

이유:

- 현재 app에서 운동, 세트, 횟수를 지정한다.
- viewer와 app 횟수 불일치를 이미 session control sync로 줄였다.
- Unity까지 session_start를 독립적으로 보내면 상태 충돌 가능성이 커진다.

## 9. 성공 기준

1. Unity 사용자 SMPL-X 모델이 실시간으로 움직인다.
2. 왼쪽/오른쪽 관절이 실제 사용자와 일치한다.
3. squat 중 무릎, 골반, 발목 움직임이 크게 어긋나지 않는다.
4. 전문가 SMPL-X 모델이 같은 운동 기준으로 반복 재생된다.
5. app에서 설정한 세트/횟수와 viewer/server/Unity 상태가 충돌하지 않는다.
6. DTW-lite ON 상태에서도 Unity 표시가 실시간 운동 확인에 쓸 수 있는 수준이다.
7. end-to-end latency가 수치로 기록된다.

## 10. 냉정한 가능 여부 판단

Unity 화면에 SMPL-X 사용자 모델과 전문가 모델을 함께 띄우는 것은 가능하다. 현재 코드에도 이미 그 기반이 있다.

다만 “정확한 3D 자세 재현”은 별도 문제다. 현재 입력이 단일 카메라 2D keypoint라서 깊이, 회전, 좌우, 발 위치가 완벽하게 맞는다는 보장은 없다. 따라서 첫 목표는 고정밀 모션캡처가 아니라 실시간 운동 피드백용 시각화로 잡아야 한다.

현실적인 1차 목표:

- Unity에서 사용자 모델이 실시간으로 따라 움직인다.
- 전문가 모델과 대략적인 동작 비교가 가능하다.
- 좌우/방향/세트 상태가 맞는다.
- 레이턴시가 app skeleton보다 나쁘지 않은지 측정한다.

현실적인 2차 목표:

- 운동별 보정값을 분리한다.
- squat 전용 root/hip/knee 안정화 규칙을 추가한다.
- Meta Quest 3 환경에서 보기 편한 Unity scene UI를 구성한다.

현실적인 3차 목표:

- 단일 카메라 2D 한계를 줄이기 위해 멀티뷰, depth, IMU, 또는 더 강한 3D pose 모델을 검토한다.

