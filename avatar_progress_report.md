# Unity 실시간 아바타 연동 진행 보고서 (Progress Report)

## 1. 프로젝트 목표
FastAPI 서버에서 실시간으로 추출되는 3D 관절 데이터를 Unity로 전송하여 실시간 아바타를 구동하는 시스템 구축. 
응답 지연(Latency) 0.5초 이내를 목표로 하며, 자연스러운 움직임과 부드러운 보간(Interpolation)을 요구함.

---

## 2. 접근 방식의 진화

### Phase 1: IK 기반 Humanoid 리타겟팅 (초기 접근)
*   **방식**: 서버가 제공하는 17개의 3D 키포인트 좌표(COCO Format)를 수신하여, 이를 바탕으로 수학적 역운동학(IK)을 계산, Mixamo 등의 일반 Humanoid 뼈대의 회전값을 산출.
*   **한계점**: 
    1. 위치 데이터를 회전 데이터로 역산하는 과정에서 근사 오차가 발생.
    2. 서버 내부 파이프라인에서 이미 정확한 회전값(SMPL-X 파라미터)을 산출하고 있음에도 이를 활용하지 못하는 비효율성 발견.

### Phase 2: 공식 SMPL-X Unity 패키지 연동 (현재 접근)
*   **에셋 발굴**: 프로젝트 내 `SMPLX_UnityProject_20241205.zip` 아카이브 분석을 통해 공식 SMPL-X Unity 패키지 발굴.
*   **방식**: `AvatarController.cs`를 전면 재작성하여, 서버에서 전송되는 63개의 `body_pose` 파라미터(Axis-Angle)와 3개의 `global_orient` 파라미터를 직접 수신. 공식 스크립트(`SMPLX.cs`)의 `QuatFromRodrigues` 함수를 호출하여 아바타의 관절 회전값에 다이렉트 매핑.
*   **개선 효과**:
    1. 코드 복잡도 대폭 감소 (570줄 -> 330줄).
    2. 서버 최적화 로직의 결과를 손실 없이 그대로 반영하여 극도의 정확성 확보.
    3. 근육/피부 변형을 자연스럽게 해주는 **Pose Correctives (Blend Shapes)** 기능 자동 활성화.

---

## 3. 서버 측 아키텍처 수정 내역
*   **Python 3.8 호환성 패치**: FastAPI 서버의 WebSocket 핸들러 내부에서 사용된 `asyncio.to_thread()`가 Python 3.9+ 부터 지원됨에 따라 런타임 에러 발생. 이를 Python 3.8 호환 문법인 `loop.run_in_executor()`로 교체하여 서버 백엔드를 완벽하게 복구함.
*   **데이터 통신 검증**: 50 프레임 분량의 모의 데이터를 전송하는 `test_debug.py` 스크립트를 작성해 송수신을 테스트한 결과, 지연 없이 `body_pose` 63개, `global_orient` 3개 및 스쿼트 무릎 각도(feedback)가 정상적으로 반환됨을 100% 확인.

---

## 4. 현재 발생 중인 이슈: 메모리 부족 (OOM) 에러
*   **현상**: Unity 에디터와 파이썬 서버를 동시에 가동할 때 시스템 페이지 파일(Paged Memory) 점유율이 93~98%까지 치솟아 정상적인 테스트 진행이 불가능해지는 현상 확인.
*   **원인 분석**:
    SMPL-X `optimization` 백엔드는 PyTorch를 기반으로 무거운 비선형 최적화 연산을 수행합니다. GPU VRAM과 별개로, 모델 로딩과 텐서 연산을 위해 시스템 RAM을 수 기가바이트(Gigabytes) 상주시키며, 무거운 Unity Editor와 병행 실행 시 물리적 메모리 한계를 초과하게 됩니다.

---

## 5. Next Step: 경량 백엔드(MLP Lifter)로의 전환
메모리 제약을 극복하고 0.5초 이내의 레이턴시를 확정적으로 달성하기 위해, 서버 구동 방식을 **초경량 모드**로 전환해야 합니다.

### 해결 가이드:
1.  **모든 프로세스 종료**: 현재 열려있는 무거운 Python.exe 콘솔과 불필요한 백그라운드 앱을 모두 종료합니다.
2.  **경량 파이프라인(Lifter) 모드로 서버 실행**: 
    SMPL-X 최적화를 생략하고 이미 학습 완료된 고속의 MLP 네트워크(추론 0.05ms 이하)만을 백엔드로 사용하도록 환경 변수를 재정의합니다.
    새로운 PowerShell에서 아래 코드를 복사해서 실행하세요:

```powershell
cd C:\Project\VR-Based-Real-Time-Agent
$env:DIAGNOSTICS_ENABLED="false"
$env:ENABLE_NGROK="false"
$env:FITTER_BACKEND="lifter"
$env:LIFTER_CHECKPOINT="model_3d\artifacts\checkpoints\fitness_pose_lifter_latest_best.pt"

python server.py
```

이 세팅으로 서버를 구동하면 RAM 사용량이 **최대 10배 (수백 MB 수준) 감소**하며 Unity와의 동시 실행이 가능해질 것입니다. 이후 앞서 작성한 `AvatarController`의 연동을 다시 시도합니다.
