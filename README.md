# Avatar3D — 3D 아바타(SMPL-X) 시도 브랜치 ★중단

**웹캠 관절점으로 SMPL-X 3D 아바타를 실시간으로 움직이려던 2026-04 ~ 2026-06-08 의 세 갈래 시도(Unity · Three.js 뷰어 · 3D 웹앱)와 그 실패 기록이다.**

> [!IMPORTANT]
> **이 라인은 중단됐다.** 학습 데이터(013 피트니스자세)에 SMPL-X `body_pose`(부모 기준 local 회전) 정답이 없어서, MLP 가 내는 66차원 회전값으로는 아바타가 25~50° 기울거나 뒤로 젖혀졌다.
> 3D 관절 좌표(MPJPE 10.87mm)로 뼈를 직접 돌리는 우회로도 local/world 회전 불일치로 무너졌고, Unity + SMPL-X 최적화 서버는 메모리 93~98% 까지 찼다.
> 같은 시점 2D 뷰어는 119 FPS 로 정상이었으므로, 최종 결과물은 [`App`](../../tree/App) 브랜치의 **2D 관절점** 방식이다. 자세한 결산은 [`docs/00_왜_중단했나.md`](docs/00_왜_중단했나.md).

이 브랜치는 "무엇을 해봤고 왜 안 됐는지"를 보존한다. 최종 앱은 [`App`](../../tree/App), 리프터 학습·SMPL-X 피팅은 [`Pose3D`](../../tree/Pose3D), 전체 서사는 [`main`](../../tree/main), 재편 이전 작업 공간 전체 스냅샷은 [`docs-archive`](../../tree/docs-archive) 에 있다.

---

## 세 갈래 시도

| 시도 | 기간 | 무엇을 했나 | 어디까지 됐나 | 왜 멈췄나 |
|---|---|---|---|---|
| 1. Unity SMPL-X 아바타 — [`unity_integration/`](unity_integration/), [`unity/FitnessPoseViewer/`](unity/FitnessPoseViewer/) | 2026-04-09 ~ 04-29 | 서버 WebSocket(`/ws/pose`)의 `fit.body_pose[63]`+`global_orient[3]`(axis-angle) → 쿼터니언 → Unity 뼈 회전. 오른손→왼손 축 반전, Slerp 보간, `rootRotationOffset`, 지면 스냅. 별도로 내보낸 JSON 시퀀스를 구·원기둥 골격으로 재생하는 스캐폴드 | 스크립트·연결 가이드 작성, 스쿼트 애니메이션(04-13). 04-29 에 UI 를 웹 2D 뷰어로 옮기고 Unity 는 병행으로 격하 | Unity 에디터 + SMPL-X optimization 서버 동시 실행 시 메모리 93~98% → lifter 백엔드로 경량화. 그러나 서버의 66차원 출력 자체가 올바른 SMPL-X 회전이 아니었다(6월에 판명). SMPLX-Unity 패키지는 라이선스상 저장소에 없다 |
| 2. Three.js 단독 뷰어 — [`viewer_3d_web/`](viewer_3d_web/) | 2026-06-08 | Vite + React 19 + R3F 로 `public/smplx.fbx` 를 띄우고 WebSocket 프레임의 SMPL-X 값으로 뼈 회전. `test_sender.py` 가 키포인트를 쏜다 | 빌드·실행 가능. 뼈 이름 매칭은 휴리스틱(실험 1 이전 방식) | 같은 입력 문제. 이후 작업은 3번 앱으로 옮겨감 |
| 3. PSVR 3D 웹앱 — [`app_3d_web/`](app_3d_web/) | 2026-06-08 | 강사(보라)·내 자세(초록) SMPL-X 메시 나란히 + "방식 비교" 화면에서 V1 SMPL-X MLP / V2 3D 기하 IK / V3 와이어프레임 3분할 | 실험 1~7 수행. V1 뼈 매핑·축 변환 확정, MLP v2·v3 재학습, V3 는 관절이 맞게 움직임 | V1 자세 틀림(입력 문제), V2 는 local/world 불일치로 T-pose 정지, V3 는 메시 없음. **근본 해결(AMASS·SMPLify-X·단순 IK) 미실행** 상태로 2D 로 전환 |

스크린샷은 [`docs/30_스크린샷/`](docs/30_스크린샷/README.md), 렌더러별 설명은 [`docs/20_Three.js_SMPLX/02_렌더링_방식_3종.md`](docs/20_Three.js_SMPLX/02_렌더링_방식_3종.md).

## 이 README 하나로 돌아간다

여기서 "돌아간다"는 **빌드되고 화면이 뜬다**는 뜻이다. 아바타 자세가 맞게 나오는 경로는 없다(위 중단 사유).

### 0) 지금 내 상황

| 상황 | 갈 곳 | 필요한 것 |
|---|---|---|
| Unity 로 SMPL-X 아바타를 보려 한다 | A | Unity 2021.3/2022.3 LTS, SMPLX-Unity 패키지(라이선스), Pose3D 브랜치 서버 |
| Three.js 뷰어를 돌려본다 | B | Node 22 + npm, `smplx.fbx`, :8000 서버 |
| 3D 웹앱을 빌드해 V1/V2/V3 컴포넌트를 본다 | C | Node 22 + npm, `smplx.fbx`, App 브랜치 서버 |

이 브랜치에는 Python 서버·`.env.example`·`requirements.txt` 가 없다. **3D 서버 환경(리프터 체크포인트, `FITTER_BACKEND`, `LIFTER_CHECKPOINT` 등)은 [`Pose3D`](../../tree/Pose3D) 브랜치에 있다.** `/api/expert-smplx`·`/api/expert-pose3d` 를 포함한 FastAPI 서버(재편 전 경로 `final/s02_backend/server.py`)는 [`App`](../../tree/App)·`Pose3D` 브랜치에 있다.

### A. Unity 아바타

1. SMPLX-Unity 패키지를 받는다 — <https://smpl-x.is.tue.mpg.de/> 에서 회원가입·라이선스 동의 후 Unity 프로젝트 압축(옛 이름 `SMPLX_UnityProject_20241205.zip`)을 내려받아 저장소 바깥 또는 `SMPLX-Unity/`(gitignore 됨)에 푼다.
2. Unity Hub 로 연다(원 프로젝트는 2020.3.8f1, **2021.3 / 2022.3 LTS 로 업그레이드해서 연다**). `Assets/SMPLX/Prefabs/smplx-neutral.prefab` 배치.
3. 스크립트 둘 중 하나를 고른다.
   - [`unity/FitnessPoseViewer/Assets/Scripts/AvatarController.cs`](unity/FitnessPoseViewer/Assets/Scripts/AvatarController.cs) — 공식 `SMPLX.cs` 의 `QuatFromRodrigues`/`SetLocalJointRotation`/`SnapToGroundPlane` 을 호출. SMPLX 프리팹에 바로 붙인다. 절차: [`docs/10_Unity_아바타/01_아바타_컨트롤러_가이드.md`](docs/10_Unity_아바타/01_아바타_컨트롤러_가이드.md).
   - [`unity_integration/`](unity_integration/README.md) 의 `FitnessAvatarController.cs` + `WebSocketClient.cs` + `UIManager.cs` — 일반 휴머노이드 뼈 21개 + root 를 수동 할당. 절차: [`unity_integration/README.md`](unity_integration/README.md) (뼈 순서 주의는 F 표 참조).
4. 서버는 Pose3D 브랜치에서 lifter 백엔드로 띄운다(OOM 회피, [`02_진행_보고`](docs/10_Unity_아바타/02_진행_보고_2026-04-11.md) 5절):
   ```powershell
   $env:FITTER_BACKEND="lifter"; $env:DIAGNOSTICS_ENABLED="false"; $env:ENABLE_NGROK="false"
   $env:LIFTER_CHECKPOINT="<Pose3D 브랜치 안내에 따른 체크포인트 경로>"
   # 서버 실행 명령은 Pose3D 브랜치 README 를 따른다 (WebSocket ws://127.0.0.1:8000/ws/pose)
   ```
5. ▶ Play. 키포인트를 보내는 클라이언트(2D 뷰어 또는 `viewer_3d_web/test_sender.py`)가 있어야 움직인다.

FBX/패키지 없이 골격만 보고 싶다면 [`unity/FitnessPoseViewer/README.md`](unity/FitnessPoseViewer/README.md) 의 `FitnessPoseSequencePlayer.cs`(내보낸 JSON 시퀀스 재생. 내보내기 스크립트 `python -m model_3d.export_fitness_unity` 는 Pose3D 브랜치).

### B. Three.js 뷰어 (`viewer_3d_web`)

```bash
cd viewer_3d_web
npm ci
# smplx.fbx 를 public/ 에 둔다 (아래)
npm run dev          # http://localhost:3000  (strictPort)
npm run build        # tsc -b && vite build -> dist/
```

- **`public/smplx.fbx` 는 저장소에 없다**(`.gitignore` 의 `*.fbx`, SMPL-X 라이선스상 재배포 금지). 위 SMPLX-Unity 패키지의 `Assets/SMPLX/Models/` 에 든 neutral FBX 를 `viewer_3d_web/public/smplx.fbx` 로 복사한다. 실험 로그 기준 원래 파일은 1.54MB 이고 SMPL-X 22관절 이름의 뼈(`pelvis`, `left_hip` …)를 가진다. `public/Xbot.glb` 는 코드에서 쓰지 않는 예제 모델이다.
- 뷰어는 `ws://127.0.0.1:8000/ws/pose` 에서 `status=="ok"` 이고 `fit.global_orient`/`fit.body_pose` 가 든 메시지만 쓴다 → `FITTER_BACKEND=lifter` 서버가 필요하다.
- 프레임 송신: `python test_sender.py` (`pip install websockets`). 이 스크립트는 `C:\Project\VR-Based-Real-Time-Agent\squat_left_1_keypoints.json` 을 하드코딩해 읽는다 — 이 파일은 이 브랜치에서 지웠으니 [`docs-archive`](../../tree/docs-archive) 에서 가져와 경로를 맞춘다.

### C. 3D 웹앱 (`app_3d_web`)

```bash
cd app_3d_web
npm ci
npm run build        # tsc && vite build -> dist/  (base: /app/)
npm run dev          # http://localhost:5173/app/  — /api, /ws 는 localhost:8000 으로 프록시
```

- `smplx.fbx` 는 `app_3d_web/public/smplx.fbx` 에 둔다(B 와 같은 파일, 코드가 `${BASE_URL}smplx.fbx` 로 읽는다). 원래 루트 `public/` 에는 추적된 파일이 없었으므로(FBX 만 있었고 gitignore 됨) 이 폴더는 직접 만든다.
- `/api/expert-smplx`(V1)·`/api/expert-pose3d`(V2·V3)는 App 브랜치 서버가 제공한다. 재편 전 서버의 `expert-pose3d` 는 프로젝트 루트의 `squat_expert_keypoints_3d_mb.json`(MotionBERT-Lite 결과, `run_motionbert.py` 로 생성 — 둘 다 docs-archive)을 읽는다.
- 서버의 `/app/` 로 서빙하려면 `dist/` 를 서버가 보는 `app_dist/` 로 복사한다(재편 전 구조 `final/app_dist`).
- **주의**: 이 스냅샷의 `src/App.tsx` 는 2D 버전(`SkeletonCanvas2D` + `useExpertPose2D`)이다. 3D 컴포넌트 `Skeleton3DCanvas*`, `SkeletonWireframe3D`, `RenderSlot`, 훅 `useExpertPose`/`useExpertPose3d` 는 **타입 검사는 통과하지만 어느 화면에도 연결돼 있지 않다**. 스크린샷 속 "방식 비교" 페이지를 조립하던 `App.tsx` 는 어느 브랜치에도 커밋되지 않았다. 다시 보려면 세 컴포넌트를 `App.tsx` 에서 직접 렌더해야 한다.
- 캡처 스크립트: [`app_3d_web/tools/playwright/`](app_3d_web/tools/playwright/README.md).

#### 현재 빌드 상태 (2026-10-12, Node v22.20.0 / npm 10.9.3, Windows)

| 폴더 | 명령 | 결과 |
|---|---|---|
| `viewer_3d_web/` | `npm ci` → `npm run build` (`tsc -b && vite build`, Vite 8.0.16) | **통과** — 572 modules, `index-*.js` 1,137.56 kB (gzip 315.03 kB). 500 kB 초과 청크 경고만 |
| `app_3d_web/` | `npm ci` → `npm run build` (`tsc && vite build`, Vite 5.4.21) | **통과** — 44 modules, `index-*.js` 162.47 kB (gzip 53.88 kB). `three-mesh-bvh@0.7.8` deprecated 경고만. 3D 컴포넌트는 import 되지 않아 번들에 없다(타입 검사는 `src` 전체 대상이라 통과 확인됨) |

빌드는 FBX 가 없어도 성공한다. FBX 가 없으면 실행 중 `useFBX` 가 404 로 실패해 3D 캔버스가 비어 보인다.

### F. 막혔을 때

| 증상 | 원인 / 조치 |
|---|---|
| 아바타가 앞으로 쓰러지거나 25~50° 기운다 | 입력 문제다(실험 3·5). 렌더러를 고쳐서는 안 고쳐진다. 임시로 `global_orient` 를 `[0,0,0]` 으로 두면 수직은 선다 |
| 팔다리 대신 손가락이 돈다 | 뼈 이름 매핑 실패 → fallback 인덱스 매핑. `viewer_3d_web/src/Scene.tsx` 는 아직 휴리스틱 매칭(`'lefthip'` vs `'left_hip'`)이다. `app_3d_web` 의 `Skeleton3DCanvas.tsx` 처럼 exact match 로 바꾼다(실험 1) |
| 축이 뒤집힌 듯 돈다 | SMPL-X 회전은 Three.js 에서 `(rx, −ry, −rz)` 가 맞다(실험 4). 3D 관절 좌표는 아래 좌표계 규약 참조 — 축을 그대로 쓰면 뼈가 ~72° 돌아간다 |
| V2 가 T-pose 로 멈춰 있다 | 알려진 실패(실험 7). 부모 world 행렬 미갱신 + local/world 혼동 |
| 캔버스가 비었다 | `public/smplx.fbx` 없음, 또는 `/api/expert-*` 가 404(서버 없음·`squat_expert_keypoints_3d_mb.json` 없음) |
| Unity + 서버에서 메모리 부족 | `FITTER_BACKEND=lifter` 로 서버를 띄운다. optimization 백엔드는 수 GB 상주 |
| `unity_integration/README.md` 의 `run_steps.py --server`, `play_squat.py` 가 없다 | 이 브랜치에서 지웠다. docs-archive 에 있다. 서버는 Pose3D/App 브랜치 안내를 따른다 |
| `unity_integration` 뼈를 22개 넣으라는데 배열은 21칸이다 | README 는 Element 0 = Pelvis 로 안내하지만 `FitnessAvatarController.smplBones[i]` 는 `body_pose[i*3..]`(0 = left_hip)를 받는다. 코드 기준으로는 Pelvis 를 `rootBone` 에 넣고 `smplBones` 를 left_hip … right_wrist 21개로 채운다 |

---

## 좌표계 규약 모음

| 대상 | 규약 | 출처 |
|---|---|---|
| SMPL-X 파라미터 | 오른손 좌표계 axis-angle(Rodrigues). `global_orient[3]` = pelvis, `body_pose[63]` = 21관절 × 3, **각각 부모 뼈 기준 local 회전** | 실험 로그 §3 |
| Unity 공식 `SMPLX.cs` | `QuatFromRodrigues`: axis = `(−rx, ry, rz)`, angle = `−θ` (왼손 좌표계로 X 반전) | 실험 로그 §2, `unity/.../AvatarController.cs` |
| `unity_integration/FitnessAvatarController.cs` | 자체 변환: axis 의 **X·Z 반전**, angle `+θ`, `initialRotation × q`, 루트에 `Quaternion.Euler(rootRotationOffset)`(코드 기본값 `(0,0,0)`, 문서상 측면 영상엔 `(0,90,0)`), `Quaternion.Slerp` 보간. 공식 `SMPLX.cs` 와 다른 규약이다 | 코드 |
| Three.js (`FBXLoader`) | `quatFromRodrigues`: axis = `(rx, −ry, −rz)/θ`, angle `+θ` — `SMPLX.cs` 와 수학적으로 동치. 뼈 목표 = `rest × q` | `app_3d_web/src/utils/smplMath.ts` |
| **PoseLifterMLP 출력 3D 관절** (`/api/expert-pose3d`) | `pt[0]` = 좌우, `pt[1]` = 깊이, `pt[2]` = 높이(Z-up), cm. Three.js: **`new THREE.Vector3(pt[0], pt[2], -pt[1])`**. 실제 출력으로 해부학 검증됨(코 z≈92 > 어깨 77 > 엉덩이 37 > 무릎 1 > 발목 −35 cm). `(pt[0], pt[1], pt[2])` 를 그대로 쓰면 뼈가 ~72° 돌아가 자세가 깨진다 | 이후 검증 |
| ↳ 실험 로그의 옛 서술 | 로그 §5 의 "x=깊이, y=좌우, z=높이 → `[y→X, z→Y, x→Z]`" 는 입력 키포인트 공간을 보고 내린 **잘못된 진단이며 이후 정정·되돌려졌다**. 로그는 역사 기록이라 원문 그대로 둔다 | — |
| MotionBERT-Lite 3D 관절 (이 스냅샷의 V2·V3 코드) | x = right, y = down, z = depth. Three.js: `(x, −y, z)`, 골반 중심 원점. 6월 8일 마지막 시점 서버가 `/api/expert-pose3d` 로 MotionBERT-Lite 결과를 냈기 때문이다. PoseLifterMLP 출력을 넣을 땐 위 규약으로 바꿔야 한다 | `Skeleton3DCanvasV2.tsx`, `SkeletonWireframe3D.tsx` |
| 2D 입력 | MoveNet COCO-17 `[y/H, x/W, conf]` (0~1) | 실험 로그 "다음 작업 시 고려사항" |

`body_pose` 인덱스 (각 3칸, 부모 기준):

| 슬라이스 | 관절 | 슬라이스 | 관절 | 슬라이스 | 관절 |
|---|---|---|---|---|---|
| 0:3 | left_hip | 21:24 | right_ankle | 42:45 | head |
| 3:6 | right_hip | 24:27 | spine3 | 45:48 | left_shoulder |
| 6:9 | spine1 | 27:30 | left_foot | 48:51 | right_shoulder |
| 9:12 | left_knee | 30:33 | right_foot | 51:54 | left_elbow |
| 12:15 | right_knee | 33:36 | neck | 54:57 | right_elbow |
| 15:18 | spine2 | 36:39 | left_collar | 57:60 | left_wrist |
| 18:21 | left_ankle | 39:42 | right_collar | 60:63 | right_wrist |

## 코드 구성

| 경로 | 내용 |
|---|---|
| [`unity_integration/`](unity_integration/) | `FitnessAvatarController.cs`(145줄, 21뼈 + root, X·Z 반전, Slerp), `WebSocketClient.cs`(211줄, `System.Net.WebSockets`, `ws://127.0.0.1:8000/ws/pose`), `UIManager.cs`(43줄, 점수·피드백 표시), 초보자 가이드 README |
| [`unity/FitnessPoseViewer/`](unity/FitnessPoseViewer/) | Unity 임포트 스캐폴드: `AvatarController.cs`(502줄, 공식 SMPLX.cs 연동, 스무딩·지면 스냅·손 포즈), `FitnessPoseSequencePlayer.cs`(398줄, 내보낸 JSON 시퀀스를 구·원기둥 골격으로 재생) |
| [`viewer_3d_web/`](viewer_3d_web/) | Vite 8 + React 19 + R3F 9. `src/Scene.tsx`(FBX 뼈 회전), `src/hooks/useWebSocketPose.ts`(자동 재연결), `src/utils/smplMath.ts`, `test_sender.py`(30 FPS 키포인트 송신). 폴더 README 는 Vite 템플릿 그대로다 |
| [`app_3d_web/`](app_3d_web/) | Vite 5 + React 18 + R3F 8 "PSVR" 앱. `src/components/Skeleton3DCanvas.tsx`(V1), `Skeleton3DCanvasV2.tsx`(V2), `SkeletonWireframe3D.tsx`(V3), `RenderSlot.tsx`, `src/hooks/useExpertPose.ts`·`useExpertPose3d.ts`, `src/utils/smplMath.ts`. 나머지는 2D 앱과 같은 HUD·결과 화면 |
| [`app_3d_web/tools/playwright/`](app_3d_web/tools/playwright/) | 2026-06-08 캡처 스크립트 12개(`pw_*.mjs`, `screenshot_*.mjs`, `final_check.mjs`) |

## 문서

| 문서 | 내용 |
|---|---|
| [`docs/README.md`](docs/README.md) | 문서 지도 |
| [`docs/00_왜_중단했나.md`](docs/00_왜_중단했나.md) | **결산** — 타임라인, 실험 7개, 원인, 되살리는 법, 2D 대안 |
| [`docs/10_Unity_아바타/`](docs/10_Unity_아바타/) | 컨트롤러 가이드, 04-11 진행 보고(OOM), 진행 요약, 노션·발표 정리(당시 낙관적 서술) |
| [`docs/20_Three.js_SMPLX/01_실험_로그_2026-06-08.md`](docs/20_Three.js_SMPLX/01_실험_로그_2026-06-08.md) | 결정적 원본 기록(§5 좌표 서술은 이후 정정됨 — 위 표) |
| [`docs/20_Three.js_SMPLX/02_렌더링_방식_3종.md`](docs/20_Three.js_SMPLX/02_렌더링_방식_3종.md) | V1/V2/V3 설명 |
| [`docs/30_스크린샷/README.md`](docs/30_스크린샷/README.md) | 스크린샷 15장 |

## 다른 브랜치

| 브랜치 | 내용 |
|---|---|
| [`main`](../../tree/main) | 프로젝트 전체 서사와 브랜치 안내 |
| [`App`](../../tree/App) | **최종 결과물** — 2D 관절점 기반 실시간 자세 교정 앱과 서버 |
| [`Pose3D`](../../tree/Pose3D) | 2D→3D 리프터 학습, SMPL-X 피팅, 3D 서버 환경 |
| `Avatar3D` (여기) | 3D 아바타 시도 ★중단 |
| [`docs-archive`](../../tree/docs-archive) | 재편 이전 작업 공간 전체 스냅샷 (지운 파일 원본은 모두 여기) |
