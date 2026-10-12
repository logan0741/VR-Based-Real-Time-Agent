# docs — 문서 지도

이 폴더는 Pose3D 브랜치의 문서를 순서대로 모은 곳이다. 번호가 작을수록 먼저 읽는다. 각 문서가 어떤 코드를 설명하는지 표로 정리했다.

| 문서 | 다루는 코드 / 데이터 | 언제 읽나 |
| --- | --- | --- |
| [00_전체흐름_단계별.md](00_전체흐름_단계별.md) | `run_steps.py`, `model_3d/` 전체 | 처음 |
| [00_환경_준비/00_처음_시작.md](00_환경_준비/00_처음_시작.md) | `environment.yml`, `requirements.txt`, `.env.example`, `experiments/data_prep/prepare_fitness_subset.py`, `scripts/check_fitness_training_env.ps1` | 설치할 때 |
| [10_데이터/01_데이터셋.md](10_데이터/01_데이터셋.md) | `model_3d/lifter_model.py`(FitnessLabelDataset), `model_3d/pose3d_dataset.py`, `experiments/pose_2d/` | 데이터를 놓을 때 |
| [10_데이터/02_2D_포즈추정기_비교.md](10_데이터/02_2D_포즈추정기_비교.md) | `experiments/pose_2d/compare_models.py`, `experiments/hpe_comparison/` | 2D 추정기 선택 근거 |
| [20_학습/01_리프터_학습.md](20_학습/01_리프터_학습.md) | `model_3d/train_lifter.py`, `train_fitness_lifter.py`, `train_smplx_v2.py`, `scripts/train_fitness_*.ps1`, `model_3d/artifacts/training/` | 학습할 때 |
| [20_학습/02_SMPLX_피팅과_좌표계.md](20_학습/02_SMPLX_피팅과_좌표계.md) | `model_3d/fitter.py`, `smplx_coordinate_fitter.py`, `server_app/server.py`(PoseLifterNet), `tools/run_motionbert.py` | 3D/SMPL-X 결과를 해석할 때 |
| [30_실시간_서버/01_서버와_2D뷰어.md](30_실시간_서버/01_서버와_2D뷰어.md) | `model_3d/server_app/`, `pose_retargeting.py`, `viewer_2d/`, `tools/play_squat.py` | 서버·뷰어를 띄울 때 |
| [40_분석_기록/](40_분석_기록/) | 2026-04 당시 작성된 분석 문서 원본 | 근거를 찾을 때 |
| [50_스크린샷/](50_스크린샷/) | 2D 뷰어 화면 캡처 | — |

## 40_분석_기록 안의 문서

당시 쓴 그대로 옮겼다(이름 유지). 경로·수치 일부는 지금 브랜치 구조와 다르다. 다른 점은 이 폴더의 새 문서들이 바로잡아 두었다.

| 파일 | 내용 | 주의 |
| --- | --- | --- |
| [PROJECT_ANALYSIS.md](40_분석_기록/PROJECT_ANALYSIS.md) | 2026-04-29 코드 분석, 파이프라인 A~D 다이어그램 | 루트 파일 경로는 재편 이전 기준 |
| [CHANGELOG.md](40_분석_기록/CHANGELOG.md) | 2026-03 ~ 04-29 변경 로그 | — |
| [analysis_results.md](40_분석_기록/analysis_results.md) | 전체 폴더 분석, 데이터셋 현황 | `python server.py` 는 이 스냅샷에 없는 예전 루트 서버 |
| [model_3d_deep_analysis.md](40_분석_기록/model_3d_deep_analysis.md) | model_3d 완성도, 지연 추정 | "MPJPE 10.2mm" 는 단위 오기(cm), lifter 166.7° 는 04:16 기록 |
| [smplx_paper_analysis.md](40_분석_기록/smplx_paper_analysis.md) | SMPL-X 논문 요약 | — |
| [future_directions_strategy.md](40_분석_기록/future_directions_strategy.md) | 논문 기반 발전 방향 | — |

## 이 브랜치에 없는 문서

`3d_avatar_experiment_log.md`(MLP v2/v3 재학습, 2026-06-08), `HANDOFF.md`(백엔드 지연 540 ms / 5 ms) 등은 이 브랜치에서 지웠다. 원본은 [docs-archive 브랜치](https://github.com/logan0741/VR-Based-Real-Time-Agent/tree/docs-archive)에 있다. 이 폴더의 새 문서는 필요한 내용을 출처와 함께 옮겨 적었다.
