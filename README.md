# Pose3D — 2D→3D 리프팅 학습·SMPL-X 피팅 브랜치

**2D 키포인트(COCO-17)를 3D 관절로 올리는 `PoseLifterMLP` 학습, SMPL-X 최적화 피팅, QA 진단, Unity 시퀀스 내보내기, 첫 실시간 FastAPI 서버와 2D 웹 뷰어를 담은 연구·학습 기록 브랜치다 (2026-04 ~ 2026-06).**

이 브랜치 하나만 받으면 학습과 오프라인 분석이 끝까지 된다. 최종 앱은 [`App`](../../tree/App), 3D 아바타 시도(중단)는 [`Avatar3D`](../../tree/Avatar3D), 전체 서사는 [`main`](../../tree/main), 스냅샷은 [`docs-archive`](../../tree/docs-archive).

전체 그림은 네 갈래다. **A 실시간**(웹캠/영상 → WebSocket 서버 → 2D 뷰어), **B 학습**(AI-Hub 013 피트니스자세 → PoseLifterMLP 체크포인트), **C Unity 내보내기**(3D 라벨 → Unity JSON 시퀀스), **D 오프라인 분석**(키포인트/3D 라벨 → 피터 → 무릎각 피드백 + QA 이미지). 각 갈래의 다이어그램과 파일 흐름은 [docs/00_전체흐름_단계별.md](docs/00_전체흐름_단계별.md)에 있다.

---

## 이 README 하나로 돌아간다

모든 명령은 **저장소 루트**에서 PowerShell 기준이다. `python` 은 아래 A에서 만든 conda 환경의 파이썬을 뜻한다.

### 0) 지금 내 상황이 무엇인가

| 상황 | 할 일 | 필요한 것 |
| --- | --- | --- |
| 코드만 받았다, 아무것도 없다 | A → D의 `--dummy` 스모크 | 파이썬 + torch |
| 학습을 다시 돌리고 싶다 | A → B | AI-Hub 013 데이터셋, GPU 권장 |
| 이미 체크포인트가 있다 (`*.pt`) | `model_3d/artifacts/checkpoints/` 에 두고 C 또는 D | 체크포인트 파일 |
| 실시간 2D 뷰어만 보고 싶다 | A → C (`DB_ENABLED=false`) | 웹캠 또는 `data_samples/` 재생 |
| SMPL-X 피팅을 확인하고 싶다 | A의 SMPL-X 배치 → D의 `--smplx-fit-pose3d` | SMPL-X 모델(라이선스), `pose_3d_v3` |

### A. 처음 세우기 (한 번만)

```powershell
conda env create -f environment.yml        # 이름: vr-real-time-agent, Python 3.10 (+ requirements.txt)
conda activate vr-real-time-agent
pip install torch --index-url https://download.pytorch.org/whl/cu121   # 자기 CUDA 에 맞춰. CPU 면 그냥 pip install torch
copy .env.example .env                     # 서버용. DB_ENABLED=false 가 기본으로 들어 있다
python run_steps.py --check                # 의존성·파일 점검표
```

- **SMPL-X 모델**(SMPL-X 피팅을 쓸 때만): [smpl-x.is.tue.mpg.de](https://smpl-x.is.tue.mpg.de) 에서 가입 후 `models_smplx_v1_1.zip` 을 받아 `smplx_locked_head/neutral/model.npz` 로 둔다. 라이선스상 이 저장소에 넣지 않는다(`.gitignore` 처리).
- **데이터셋**(학습할 때만): AI-Hub "013.피트니스자세" 를 루트의 `013.피트니스자세/` 에 두고 `python experiments/data_prep/prepare_fitness_subset.py` 로 `prepared_train_eval_body01_compact/` 를 만든다.
- 자세한 순서와 폴더 모양은 [docs/00_환경_준비/00_처음_시작.md](docs/00_환경_준비/00_처음_시작.md).

### B. 학습을 돌린다

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check_fitness_training_env.ps1   # torch/CUDA/데이터 샘플 수 확인
python -m model_3d.train_fitness_lifter --epochs 800 --device cuda                  # 또는 .\scripts\train_fitness_full.ps1 -Epochs 800 -Device cuda
```

- 데이터 경로는 루트의 `013.*/prepared_train_eval_body01_compact` 를 자동으로 찾는다.
- 조기 종료: 검증 loss 가 40 epoch 동안 1.0 이상 줄지 않으면 멈춘다 (`--early-stop-patience 40 --early-stop-min-delta 1.0`).
- 나오는 것:
  - `model_3d/artifacts/checkpoints/fitness_pose_lifter_latest.pt` (마지막), `..._latest_best.pt` (검증 loss 최소 — **서버가 쓰는 것**)
  - `model_3d/artifacts/training/fitness_full/pose_lifter_metrics.json`, `pose_lifter_training_curve.png`
- 체크포인트는 gitignore 대상이다. 지표 json 과 곡선 png 만 커밋되어 있다.
- 학습→QA→Unity 내보내기를 한 번에: `.\scripts\run_fitness_to_unity.ps1 -Epochs 800`.
- 세부 내용·지표 해석: [docs/20_학습/01_리프터_학습.md](docs/20_학습/01_리프터_학습.md).

### C. 실시간 서버 + 2D 뷰어

```powershell
python run_steps.py --server                       # = uvicorn model_3d.server_app.server:app --host 0.0.0.0 --port 8000
# 브라우저: http://localhost:8000/viewer/          (Quest 3 는 같은 Wi-Fi 에서 http://<PC_IP>:8000/viewer/)
python tools/play_squat.py --loops 2               # 별도 터미널: data_samples 의 스쿼트 267프레임을 약 30fps 로 흘려 보낸다
python -m model_3d.server_app.clients.webcam_client   # 또는 PC 웹캠(MediaPipe) → 서버
```

- 뷰어는 3패널(전문가 / 실시간 피드백 / 사용자)이다. 전문가 패널은 `/api/expert` 가 `data_samples/squat_left_1_keypoints.json` 을 내려 준다.
- 뷰어 자체의 "웹캠 시작" 버튼은 브라우저 안에서 MoveNet Lightning(tfjs)으로 포즈를 뽑아 서버로 보낸다.
- 자세한 메시지 형식과 한계: [docs/30_실시간_서버/01_서버와_2D뷰어.md](docs/30_실시간_서버/01_서버와_2D뷰어.md).

### D. 오프라인 분석·QA

```powershell
python -m model_3d --dummy --frame-id smoke-test                     # SMPL-X·데이터 없이 배선+진단 이미지만
python -m model_3d --check-all --lifter-checkpoint model_3d\artifacts\checkpoints\fitness_pose_lifter_latest_best.pt
python model_3d\run_pipeline.py --smplx-fit-pose3d --pose3d-path pose_3d_v3 --pose3d-split train --max-frames 1
python -m model_3d.export_fitness_unity --split train val --limit 0 --view view1   # Unity 시퀀스 JSON
```

- 인자 없이 `python -m model_3d` 를 치면 `--check-all` 로 돌고 결과를 `model_3d/artifacts/model_3d_check_all.json` 에 **덮어쓴다**. 기록을 보존하려면 `--output` 을 준다.
- `--check-all` 은 dummy / pose3d_direct / smplx_coordinate_fit / lifter_checkpoint 네 검사를 돌린다. 데이터나 모델이 없는 검사는 `skipped`·`unavailable` 로 적히고 실패하지 않는다. 체크포인트가 하나도 없으면 `pose_3d_v3` 로 작은 스모크 체크포인트를 먼저 학습한다.
- QA 산출물: `model_3d/artifacts/pose_debug/<YYYYMMDD_HHMMSS>/` 아래
  - `frames/*_preprocessed_keypoints.png`: 픽셀로 바꾼 2D 입력
  - `frames/*_reprojection_check.png`: 입력 2D vs 3D 관절을 다시 투영한 점
  - `frames/*_joints_3d_check.png`: COCO-17 3D 골격
  - `frames/*_smplx_mesh_preview.png`, `*_optimization_loss.png`: SMPL-X 경로일 때만
  - `graphs/performance_graph.png`, `metrics.jsonl`: 프레임별 지연·loss·무릎각
- 실시간 측정 때는 `DIAGNOSTICS_ENABLED=false` 로 PNG 저장을 끈다.

### E. 무엇이 나오면 정상인가

`--check-all` 기록 (`model_3d/artifacts/*.json`, 2026-04-09):

| 검사 | 백엔드 | 무릎각 / 피드백 (04-09 04:08, `model_3d_check_all.json`) | 04-09 04:16 (`fitness_pipeline_check.json`) | 2026-10-12 재실행 |
| --- | --- | --- | --- | --- |
| dummy | 배선 테스트 | 116.2° / Good | 116.2° / Good | 116.2° / Good |
| pose3d_direct | pose_3d_v3 3D 라벨 직접 | 79.0° / Good | 79.0° / Good | skipped (worktree 에 데이터 없음) |
| smplx_coordinate_fit | SMPL-X 좌표 피팅 | 143.6° / Good | 143.6° / Good | unavailable (SMPL-X 모델 없음) |
| lifter_checkpoint | PoseLifterMLP | 36.1° / "Raise your hips slightly" | 166.7° / "Lower your hips" | 166.7° / "Lower your hips" |

- 정상 기준은 **status 가 ok** 이고 dummy 가 116.2° 로 재현되는 것이다. 무릎각은 합성 입력 1프레임(`_sample_movenet_payload`)에 대한 값이라 정확도 지표가 아니다.
- lifter 값이 04:08 과 04:16 에 다르다. 같은 경로의 체크포인트가 그 사이 학습으로 갱신된 것으로 보인다(추정). 지금 남아 있는 best 체크포인트(epoch 245)로 재실행하면 166.7° 가 나온다.
- 학습 지표 정상 범위 (fitness_full): 검증 MPJPE 약 10 (데이터셋 단위 cm), 학습 MPJPE 약 7.5, GPU 약 17–27k samples/s.

### F. 막혔을 때 어디를 보나

| 증상 | 볼 곳 |
| --- | --- |
| `No module named 'smplx'` / `SMPL-X model file not found` | `pip install smplx`, `SMPLX_MODEL_PATH` — [00_처음_시작.md](docs/00_환경_준비/00_처음_시작.md) |
| `Could not find prepared_train_eval_body01_compact` | 루트에 `013.피트니스자세/` 가 있는지, data_prep 을 돌렸는지 |
| 서버 시작 때 `[DB] Disabled: ...` | 정상. MySQL 없이 돈다. 끄려면 `.env` 에 `DB_ENABLED=false` |
| 뷰어가 연결은 되는데 점수가 이상하게 오르내린다 | 서버 점수는 자리표시자다 — [01_서버와_2D뷰어.md](docs/30_실시간_서버/01_서버와_2D뷰어.md) |
| 서버 아바타 파라미터(`body_pose`)가 의미 없다 | 서버가 학습 가중치를 실제로 못 싣는다 — [02_SMPLX_피팅과_좌표계.md](docs/20_학습/02_SMPLX_피팅과_좌표계.md) |
| `KEYPOINT_FORMAT` 오류, 골격이 뒤집힘 | 입력 순서 `[y,x,score]` vs `[x,y,score]` — `.env.example` |
| 포트 8000 사용 중 | `python run_steps.py --server --port 8020` |

---

## 무엇을 하는 브랜치인가

VR 자세 교정 에이전트의 첫 설계는 "2D 키포인트 → 3D 관절 → SMPL-X 아바타 → VR 에서 전문가와 3D 비교"였다. 이 브랜치는 그 3D 쪽 연구를 담는다.

1. **2D 포즈 추정기 고르기** — MediaPipe / MoveNet Lightning / Thunder 비교 (pose_2d valid_100: MediaPipe 평균 오차 11.1 px, Lightning 92.6 px · 35.9 ms). [docs/10_데이터/02_2D_포즈추정기_비교.md](docs/10_데이터/02_2D_포즈추정기_비교.md)
2. **2D→3D 리프터 학습** — `PoseLifterMLP` 를 AI-Hub 013 으로 학습, 검증 MPJPE 10.08 (cm).
3. **SMPL-X 피팅** — 2D 리프로젝션 최적화와 3D 좌표 피팅 두 경로. 문서상 SMPL-X 최적화 ≈540 ms/frame, MLP ≈5 ms (문서상 수치, 재측정 안 함).
4. **실시간 서버 + 2D 뷰어** — FastAPI WebSocket, OneEuro 스무딩, 근육 피로도 판정, Quest 브라우저용 3패널 뷰어.
5. **Unity 내보내기** — 3D 라벨 240 시퀀스를 Unity JSON 으로.

**왜 제품은 2D 로 갔나.** 3D 경로는 숫자상으로는 돌았지만 아바타로 이어지지 않았다.

- 배포 체크포인트는 SMPL-X 파라미터가 아니라 **3D 관절 좌표**를 낸다. 서버는 이것을 SMPL-X 파라미터 모델(`PoseLifterNet`, 66차원)로 읽으려 했고, 실제로는 학습 가중치가 하나도 실리지 않는다(2026-10-12 재확인, 아래 문서).
- SMPL-X 파라미터를 직접 내도록 재학습한 v2 는 val_loss 0.08(best epoch 209)까지 내려갔지만 추론 때 global_orient 가 25–50° 기울었다 — 학습 카메라 5대와 추론 카메라의 도메인 불일치.
- SMPL-X 최적화는 문서상 ≈540 ms/frame 로 실시간에 못 미친다.
- 반면 2D 경로는 같은 시기(2026-06-08) 뷰어 카운터 기준 119 FPS 로 안정적으로 돌았다 (App 쪽 서버·뷰어 화면, 카운터는 응답 간격 평균이라 처리량 측정은 아니다 — [01_서버와_2D뷰어.md](docs/30_실시간_서버/01_서버와_2D뷰어.md) §4).

그래서 제품은 2D 비교로 옮겨 갔고([`App`](../../tree/App)), 3D 아바타 시도는 [`Avatar3D`](../../tree/Avatar3D)에서 멈췄다. 이 브랜치는 그 판단의 근거 기록이다.

## 코드 구성

| 파일 | 역할 | 갈래 |
| --- | --- | --- |
| `model_3d/server_app/server.py` | FastAPI WebSocket `/ws/pose`, `/viewer/` 정적 서빙, `/api/expert` | A |
| `model_3d/server_app/posture_analyzer.py` | 관절 각도 → 근육 피로도(low/mid/high) | A |
| `model_3d/server_app/database.py` | 완료된 운동 세션을 MySQL 에 저장 (선택) | A |
| `model_3d/server_app/clients/*.py` | webcam(MediaPipe) / video / dataset(pose_3d_v3) / 테스트 전송 클라이언트 | A |
| `model_3d/pose_retargeting.py` | OneEuro 필터 + 속도 제한 스무딩 (`PoseRetargeter`) | A |
| `model_3d/lifter_model.py` | `PoseLifterMLP`(17×3 → 17×3), 데이터셋 어댑터, 체크포인트 저장/로드 | A·B |
| `model_3d/train_lifter.py` | 학습/평가 루프 (AdamW, MSE, MPJPE, 조기 종료) | B |
| `model_3d/train_fitness_lifter.py` | 013 데이터셋 전용 학습 진입점 | B |
| `model_3d/prepare_smplx_dataset.py`, `train_smplx_v2.py` | v2: 3D 관절 → 계층적 local rotation → `PoseLifterNet`(66차원) 재학습 | B |
| `model_3d/pose3d_dataset.py` | pose_3d_v3 (`frame_81/*.pkl`) 읽기 | B·D |
| `model_3d/pipeline.py` | 프레임 처리 엔진 (피터 → 분석 → 진단) | D |
| `model_3d/pipeline_cli.py`, `run_pipeline.py`, `__main__.py` | CLI, `--check-all`, 체크포인트 선택 | D |
| `model_3d/fitter.py` | SMPL-X 2D 리프로젝션 최적화 피터 (Phase 1), Phase 2 자리 | D |
| `model_3d/smplx_coordinate_fitter.py` | 3D 좌표 → SMPL-X 피팅 (실현 가능성 테스트) | D |
| `model_3d/analyzer.py` | 스쿼트 무릎각 피드백 | A·D |
| `model_3d/diagnostics.py` | 프레임별 QA PNG + 성능 그래프 | D |
| `model_3d/preprocessing.py`, `camera.py`, `joint_mapper.py`, `schemas.py`, `config.py` | 입력 검증, 핀홀 카메라, SMPL-X→COCO 매핑, 데이터 구조, 경로/환경 | 공통 |
| `model_3d/export_fitness_unity.py`, `workflow_fitness_to_unity.py` | Unity JSON 내보내기, 학습→QA→내보내기 일괄 | C |
| `viewer_2d/` | 3패널 2D 웹 뷰어 (Canvas, WebSocket, tfjs MoveNet) | A |
| `2d_assets/` | 근육 맵 SVG (앞/뒤) | A |
| `run_steps.py` | 단계별 실행기 (`--check`, `--server`, `--train`, `--export-unity`, `--step N`) | 전체 |
| `tools/` | `play_squat.py`(샘플 재생), `test_debug.py`(응답 확인), `run_motionbert.py`(MotionBERT 리프팅 시도) | 보조 |
| `experiments/` | `hpe_comparison/`, `pose_2d/`(2D 추정기 비교), `data_prep/`(013 부분집합 만들기) | 연구 |
| `scripts/*.ps1` | 학습 환경 점검, 전체 학습, 야간 학습, 학습→Unity | B·C |
| `data_samples/` | 샘플 키포인트 (1프레임, 스쿼트 267프레임, MotionBERT 3D 131프레임) | A·D |

`run_steps.py` 는 루트에 남겼다. 파일 위치(`Path(__file__).parent`)를 저장소 루트로 쓰고 `python -m model_3d...` 를 그 디렉터리에서 실행하기 때문에, `tools/` 로 옮기면 경로 계산을 바꿔야 한다.

## 학습 결과 요약

데이터셋 `013.피트니스자세/prepared_train_eval_body01_compact`, 학습 17,105 / 검증 9,010 샘플, GPU. 수치는 `model_3d/artifacts/training/*/pose_lifter_metrics.json` 에서 읽었다. MPJPE 단위는 데이터셋 3D 라벨 단위(cm)다.

| 실행 | 모델 | epoch | best 검증 MPJPE | 최종 검증 MPJPE / loss | 최종 학습 MPJPE | 비고 |
| --- | --- | --- | --- | --- | --- | --- |
| `fitness_full` (배포: `fitness_pose_lifter_latest_best.pt`) | PoseLifterMLP 17×3→17×3 | 285 (조기 종료) | **10.08** @245 | 10.21 / 53.3 | 7.57 | best 체크포인트 = epoch 245 |
| `v3_pose3d` (2026-06-08 재학습) | PoseLifterMLP 17×3→17×3 | 128 | 10.82 @123 | 11.10 / 61.0 | 9.02 | 저장된 best 는 loss 기준 epoch 88 (MPJPE 10.88) |
| v2 `train_smplx_v2.py` | PoseLifterNet 17×3→66 SMPL-X | — | val_loss 0.08 @209 | — | — | 추론 global_orient 25–50° 기울어짐 (문서상, 지표 json 없음) |

![fitness_full 학습 곡선](model_3d/artifacts/training/fitness_full/pose_lifter_training_curve.png)

학습 MPJPE(7.6)와 검증 MPJPE(10.2)의 차이가 남는다. 검증은 다른 촬영 그룹(4번)이라 일반화 간격으로 읽어야 하고, 검증 피사체가 한 그룹뿐이라 이 숫자를 실사용 정확도로 보면 안 된다. 상세: [docs/20_학습/01_리프터_학습.md](docs/20_학습/01_리프터_학습.md).

## 문서

| 문서 | 내용 |
| --- | --- |
| [docs/README.md](docs/README.md) | 문서 지도 (문서 ↔ 코드) |
| [docs/00_전체흐름_단계별.md](docs/00_전체흐름_단계별.md) | 파이프라인 A/B/C/D 다이어그램 |
| [docs/00_환경_준비/00_처음_시작.md](docs/00_환경_준비/00_처음_시작.md) | conda, torch, SMPL-X 모델, 데이터셋 배치, 스모크 테스트 |
| [docs/10_데이터/01_데이터셋.md](docs/10_데이터/01_데이터셋.md) | 013 피트니스자세, pose_3d_v3, pose_2d, AthletePose3D |
| [docs/10_데이터/02_2D_포즈추정기_비교.md](docs/10_데이터/02_2D_포즈추정기_비교.md) | MediaPipe vs MoveNet 측정표 (2026-04-03) |
| [docs/20_학습/01_리프터_학습.md](docs/20_학습/01_리프터_학습.md) | 리프터 모델·명령·지표 |
| [docs/20_학습/02_SMPLX_피팅과_좌표계.md](docs/20_학습/02_SMPLX_피팅과_좌표계.md) | 최적화 피터 vs 좌표 피터, 좌표계, ★서버 가중치 문제 |
| [docs/30_실시간_서버/01_서버와_2D뷰어.md](docs/30_실시간_서버/01_서버와_2D뷰어.md) | 서버·스무딩·피로도·뷰어·클라이언트 |
| [docs/40_분석_기록/](docs/40_분석_기록/) | 당시 분석 문서 원본 (PROJECT_ANALYSIS, CHANGELOG 등) |
| [docs/50_스크린샷/](docs/50_스크린샷/) | 2D 뷰어 화면 |
| [model_3d/README.md](model_3d/README.md) | 패키지 원문 문서 (영문) |

## 다른 브랜치

| 브랜치 | 내용 |
| --- | --- |
| [`main`](../../tree/main) | 프로젝트 전체 서사와 브랜치 안내 |
| [`App`](../../tree/App) | 최종 2D 자세 교정 앱 |
| [`Avatar3D`](../../tree/Avatar3D) | SMPL-X/FBX 3D 아바타 연동 시도 (중단) |
| [`docs-archive`](../../tree/docs-archive) | 재편 이전 작업 공간 전체 스냅샷 (삭제된 문서 원본 포함) |
