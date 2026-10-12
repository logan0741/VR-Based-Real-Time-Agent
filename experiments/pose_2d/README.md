# pose_2d 실험 스캐폴드

루트 경로의 `pose_2d` 데이터를 바로 읽어서 내부 실험 코드에 붙일 수 있게 만든 최소 코드 틀이다.

## 구성

```text
experiments/pose_2d/
├── config.py          # split별 경로 정의
├── dataset.py         # COCO 기반 pose_2d 레코드 로더
├── check_dataset.py   # 파일/annotation/detection 정합성 확인
├── compare_models.py  # 모델별 추론/오차/속도 비교
├── train_template.py  # 배치 루프 스텁
└── results/
    └── summaries/
```

## 바로 실행

저장소 루트에서 실행:

```bash
python experiments/pose_2d/check_dataset.py
python experiments/pose_2d/train_template.py --split train --batch-size 8 --max-batches 2
python experiments/pose_2d/compare_models.py --split valid_100 --bbox-source gt --dry-run
python experiments/pose_2d/compare_models.py --split valid_100 --bbox-source gt --models mediapipe movenet_lightning movenet_thunder
```

## 현재 형태

- `Pose2DDataset(split, bbox_source="gt" | "det")` 로 ground truth box 또는 detection box 기준 레코드를 읽는다.
- 레코드는 `image_path`, `bbox`, `keypoints`, `num_visible_keypoints` 같은 기본 필드를 가진다.
- `train_template.py` 의 배치 루프 안쪽에 모델 forward / loss / backward 를 붙이면 내부 학습 코드 골격으로 바로 쓸 수 있다.
- `compare_models.py` 는 bbox crop 기준으로 `MediaPipe`, `MoveNet`, `MMPose`를 같은 데이터셋 split에서 비교한다.
- 기본 split은 `valid_100` 이라서 빠른 검증용이고, 전체 비교는 `--split valid` 또는 `--split test` 로 바꾸면 된다.

## 출력

- `check_dataset.py` 는 `results/summaries/dataset_report.json` 을 만든다.
- `train_template.py` 는 기본값으로 `results/batch_preview.json` 을 만든다.
- `compare_models.py` 는 `results/comparisons/<timestamp>_<split>_<bbox_source>/` 아래에 모델별 샘플 CSV와 요약 CSV/JSON을 만든다.
