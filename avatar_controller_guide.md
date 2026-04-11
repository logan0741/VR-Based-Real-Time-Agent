# SMPL-X Unity 셋업 가이드 (처음부터 끝까지)

## 현재 폴더 상태

```
C:\Project\VR-Based-Real-Time-Agent\SMPLX-Unity\
├── Assets/
│   ├── SMPLX/
│   │   ├── Models/          ← FBX 9종 (neutral/male/female × full/se/basic)
│   │   ├── Prefabs/         ← 바로 쓸 수 있는 프리팹 9종
│   │   ├── Scripts/
│   │   │   ├── SMPLX.cs            ← 공식 SMPL-X 제어 스크립트 (871줄)
│   │   │   ├── SMPLXBenchmark.cs   ← 벤치마크 (선택사항)
│   │   │   └── AvatarController.cs ← ★ 방금 넣은 실시간 WebSocket 스크립트
│   │   ├── Resources/       ← betas-to-joints JSON (체형 변경 시 사용)
│   │   ├── ThirdParty/      ← SimpleJSON, Matrix 라이브러리
│   │   ├── Materials/       ← 기본 Material
│   │   └── Textures/        ← 텍스처 (있으면 자동 적용)
│   ├── Scenes/
│   │   ├── SampleScene.unity     ← ★ 여기서 시작
│   │   ├── SetupScene.unity
│   │   ├── BenchmarkScene.unity
│   │   └── ValidationScene.unity
│   ├── Materials/
│   └── Standard Assets/
└── ProjectSettings/              ← Unity 2020.3.8+ 필요
```

---

## Step 1: Unity Hub에서 프로젝트 열기

1. **Unity Hub** 실행
2. **Open** (또는 "열기") 클릭
3. 경로 선택: `C:\Project\VR-Based-Real-Time-Agent\SMPLX-Unity`
4. Unity 버전 선택:
   - 프로젝트는 **2020.3.8f1**로 만들어졌지만, **2021.3 LTS** 이상이면 OK
   - 버전 업그레이드 팝업이 뜨면 → **"Continue"** 또는 **"Upgrade"** 클릭
5. 프로젝트가 열릴 때까지 대기 (첫 Import에 2-5분 소요)

> ⚠️ **Unity가 설치 안 되어 있다면**: Unity Hub → Installs → Install Editor → **2022.3 LTS** 추천

---

## Step 2: SampleScene 열어서 확인하기

1. Unity가 열리면: **Project** 패널 → `Assets/Scenes/SampleScene` 더블클릭
2. Scene 뷰에 **SMPL-X 바디 모델들이 줄 서있는 것**이 보일 것
3. **Play** 버튼 눌러서 동작 확인 → Inspector에서 Shape/Pose 조절 가능

> 이 단계에서 SMPL-X 모델이 정상적으로 보이면 에셋 셋업은 완료된 것입니다.

---

## Step 3: 실시간 아바타용 새 Scene 만들기

1. **File → New Scene** (비어있는 Scene)
2. **File → Save As** → `Assets/Scenes/RealtimeAvatarScene.unity`

---

## Step 4: SMPL-X Prefab 배치

1. **Project** 패널 → `Assets/SMPLX/Prefabs/` 이동
2. `smplx-neutral.prefab` 을 **Hierarchy** 패널로 **드래그 앤 드롭**
   - `neutral` = 성별 무관 (서버의 `smplx_locked_head/neutral` 과 일치)
   - 이미 **SMPLX** 컴포넌트가 붙어있고, 발이 바닥(y=0)에 맞춰져 있음

> 💡 **모델 선택 가이드**:
> | Prefab | Shape | Expression | Pose Correctives | 용도 |
> |---|---|---|---|---|
> | `smplx-neutral` | ✅ 10 | ✅ 10 | ✅ 486 | **최고 품질** (추천) |
> | `smplx-neutral-se` | ✅ 10 | ✅ 10 | ❌ | 중간 품질 |
> | `smplx-neutral-basic` | ❌ | ❌ | ❌ | **가장 빠름** (모바일/VR) |

---

## Step 5: AvatarController 스크립트 붙이기

1. **Hierarchy** 패널에서 방금 배치한 `smplx-neutral` 오브젝트 **클릭**
2. **Inspector** 패널에서 확인:
   - ✅ `SMPLX` 컴포넌트가 이미 붙어있음
   - ✅ `Skinned Mesh Renderer` 있음
3. **Inspector** 맨 아래 → **Add Component** 클릭
4. 검색창에 `AvatarController` 입력 → 선택

---

## Step 6: AvatarController Inspector 설정

| 항목 | 값 | 설명 |
|---|---|---|
| **Server Url** | `ws://127.0.0.1:8000/ws/pose` | Python 서버 주소 |
| **Auto Reconnect** | ✅ | 서버 재시작해도 자동 재연결 |
| **Smoothing Speed** | `15` | 관절 보간 속도 (높을수록 빠른 반응) |
| **Apply Root Position** | ✅ | 골반 위치 이동 반영 |
| **Snap To Ground** | ✅ | 발이 항상 바닥에 닿게 |
| **Hand Pose** | `Relaxed` | 손 모양 (Relaxed가 자연스러움) |
| **Log Frames** | ☐ | 디버깅 시에만 켜기 |

---

## Step 7: 카메라 위치 조정

기본 Camera가 모델을 안 보고 있을 수 있음:

1. **Hierarchy** → `Main Camera` 선택
2. **Transform** 값 설정:
   - Position: `(0, 1, 3)` → 정면에서 1m 높이로 3m 떨어진 위치
   - Rotation: `(0, 180, 0)` → 모델을 바라보는 방향

또는 Scene 뷰에서 원하는 각도를 잡고 → **GameObject → Align With View** (Ctrl+Shift+F)

---

## Step 8: Python 서버 실행

PowerShell에서:

```powershell
cd C:\Project\VR-Based-Real-Time-Agent

# MLP Lifter 체크포인트 지정 (서버에서 body_pose 계산)
$env:LIFTER_CHECKPOINT = "model_3d\artifacts\checkpoints\fitness_pose_lifter_latest_best.pt"

# 진단 이미지 끄기 (성능)
$env:DIAGNOSTICS_ENABLED = "false"

# ngrok 끄기 (로컬 테스트)
$env:ENABLE_NGROK = "false"

# 서버 실행
python server.py
```

**서버 콘솔에 `Uvicorn running on http://0.0.0.0:8000` 확인**

---

## Step 9: Unity Play!

1. Unity Editor에서 **▶ Play** 버튼 클릭
2. **Console** 창 (Window → General → Console) 확인:
   ```
   [AvatarController] Connecting to ws://127.0.0.1:8000/ws/pose...
   [AvatarController] Connected!
   ```
3. 이 상태에서 **서버로 키포인트를 보내는 클라이언트**가 있으면 아바타가 실시간으로 움직임

---

## Step 10: 테스트 (서버에 키포인트 보내기)

아직 VR/카메라 클라이언트가 없다면, Python으로 테스트:

```python
# test_send_keypoints.py
import asyncio, json, websockets

SAMPLE = json.load(open("sample_keypoints.json"))

async def main():
    async with websockets.connect("ws://127.0.0.1:8000/ws/pose") as ws:
        for i in range(100):
            await ws.send(json.dumps({
                "data_type": "keypoints",
                "frame_id": f"test-{i}",
                "payload": SAMPLE["payload"]
            }))
            response = await ws.recv()
            data = json.loads(response)
            print(f"Frame {i}: {data.get('feedback', {}).get('label', '?')}")
            await asyncio.sleep(0.1)  # 10 FPS

asyncio.run(main())
```

```powershell
pip install websockets
python test_send_keypoints.py
```

**이 스크립트 실행하면 Unity의 SMPL-X 아바타가 움직이는 것을 볼 수 있음!**

---

## 전체 흐름 요약

```
test_send_keypoints.py          server.py                    Unity
(또는 VR 클라이언트)            (FastAPI)                    (SMPLX-Unity)
       │                           │                            │
       │── 2D keypoints ──────────▶│                            │
       │   (17×3 MoveNet)          │                            │
       │                           │── MLP Lifter ──▶ 3D joints │
       │                           │── SMPL-X fit ──▶ body_pose │
       │                           │                            │
       │◀── JSON response ────────│                            │
       │                           │── WebSocket ──────────────▶│
       │                           │   body_pose (63 floats)    │
       │                           │   global_orient (3 floats) │
       │                           │                            │
       │                           │                    QuatFromRodrigues()
       │                           │                    SetLocalJointRotation()
       │                           │                    Quaternion.Slerp()
       │                           │                            │
       │                           │                    ★ 아바타가 움직임!
```

---

## 트러블슈팅

| 문제 | 해결 |
|---|---|
| Unity 버전 경고 | 2021.3 이상이면 안전하게 업그레이드 가능. "Continue" 클릭 |
| 모델이 분홍/보라색 | Material 누락. `Assets/SMPLX/Materials/` 에서 재할당 (URP/HDRP 전환 시 발생) |
| `SMPLX component not found` 에러 | Prefab을 쓰지 않고 FBX를 직접 넣은 경우. Prefab 사용 권장 |
| `Connected!` 후에도 안 움직임 | 서버로 키포인트를 보내는 클라이언트가 없음. Step 10 테스트 스크립트 실행 |
| 관절이 이상하게 꺾임 | `Smoothing Speed` 를 5-10으로 낮추거나, Prefab의 `Pose Corrective Quality`를 Medium/Low로 변경 |
| 아바타가 너무 작거나 큼 | SMPL-X는 실제 인체 크기(~1.7m). 카메라 위치를 조절하거나 parent 오브젝트 스케일 조절 |
| 프레임 드랍 | `smplx-neutral-basic` Prefab 사용 (Pose Correctives 없음, 가장 빠름) |
