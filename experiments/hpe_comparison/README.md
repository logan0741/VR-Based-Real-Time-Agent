# HPE 라이브러리 비교 실험

MoveNet / MediaPipe / MMPose 세 가지 HPE 라이브러리의 **처리량·정확도·떨림** 성능을 비교하는 실험 파이프라인입니다.

## 폴더 구조

```
experiments/hpe_comparison/
├── config.py               ← 전역 설정 (경로, 모델 파라미터, 키포인트 매핑)
├── utils.py                ← 공용 유틸 (영상 읽기, 좌표 변환, CSV I/O)
├── step1_check_env.py      ← 환경 점검 & 테스트 영상 녹화
├── step2_run_inference.py  ← 모델별 추론 실행 → CSV 저장
├── step3_analyze.py        ← FPS/Latency/Jitter 분석 → 요약 테이블
├── step4_visualize.py      ← 비교 차트 PNG 생성
├── run_pipeline.py         ← 전체 파이프라인 실행기
├── requirements.txt        ← 의존성 목록
├── input_videos/           ← 테스트 영상 넣는 폴더 (자동 생성)
└── results/                ← 결과 저장 (자동 생성)
    ├── raw/                ← 프레임별 키포인트 CSV
    ├── charts/             ← 시각화 차트 PNG
    └── report/             ← 요약 CSV + 상세 JSON
```

## 실행 방법

### 1. 의존성 설치
```bash
cd experiments/hpe_comparison
pip install -r requirements.txt
```

### 2. 테스트 영상 준비
`input_videos/` 폴더에 `.mp4` 영상 넣기 (1080p 권장)
- **정적 영상**: 자세를 고정한 채 5~10초 촬영
- **동적 영상**: 스쿼트/푸시업 등 반복 운동 촬영

> `config.py`의 `VIDEO_TAGS`에 정적/동적 태그를 설정하면 더 정확한 분석 가능

### 3. 전체 파이프라인 실행
```bash
python run_pipeline.py
```

### 4. 개별 단계 실행 (문제 발생 시)
```bash
python step1_check_env.py      # 환경 점검
python step2_run_inference.py  # 추론 실행
python step3_analyze.py        # 분석
python step4_visualize.py      # 시각화
```

또는
```bash
python run_pipeline.py --step 2   # Step 2만 실행
python run_pipeline.py --step 3   # Step 3만 실행
```

## 측정 지표

| 지표 | 설명 | 목표 (기획안) |
|------|------|-------------|
| Avg FPS | 평균 프레임 처리 속도 | ≥ 60 FPS |
| Avg Latency | 1프레임 평균 추론 지연 | ≤ 16.67ms |
| P99 Latency | 상위 1% 최악 지연 | 안정성 판별 |
| Static Jitter | 정지 자세에서 좌표 떨림 (px std) | 낮을수록 우수 |
| Dynamic Residual | 동적 궤적 잔차 RMSE (px) | ≤ 5cm 환산 |
| Accel Std | 가속도 변동 표준편차 (px) | 낮을수록 우수 |

## 생성 차트

1. `01_fps_comparison.png` — 모델별 평균 FPS 비교
2. `02_latency_boxplot.png` — 추론 지연시간 분포
3. `03_latency_timeline_*.png` — 프레임별 Latency 시계열
4. `04_jitter_comparison.png` — Jitter 지표 비교
5. `05_trajectory_*.png` — 관절 궤적 비교
