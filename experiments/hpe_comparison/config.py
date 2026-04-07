"""
config.py — 실험 전역 설정
─────────────────────────────
경로·해상도·모델 파라미터 등을 한 곳에서 관리합니다.
실험 조건을 바꾸고 싶으면 이 파일만 수정하세요.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Dict, Optional

# ─────────────────────────────────────────────
# 1) 경로 설정
# ─────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent          # experiments/hpe_comparison/
PROJECT_DIR = ROOT_DIR.parent.parent                # VR-Based-Real-Time-Agent/

# 입력 영상 폴더 (여기에 테스트 영상 넣으세요)
INPUT_VIDEO_DIR = ROOT_DIR / "input_videos"
INPUT_VIDEO_DIR.mkdir(exist_ok=True)

# 결과 저장 폴더
OUTPUT_DIR = ROOT_DIR / "results"
OUTPUT_DIR.mkdir(exist_ok=True)

RAW_DIR = OUTPUT_DIR / "raw"        # 프레임별 keypoint CSV
RAW_DIR.mkdir(exist_ok=True)

CHART_DIR = OUTPUT_DIR / "charts"   # 시각화 이미지
CHART_DIR.mkdir(exist_ok=True)

REPORT_DIR = OUTPUT_DIR / "report"  # 최종 리포트
REPORT_DIR.mkdir(exist_ok=True)

# ─────────────────────────────────────────────
# 2) 영상 설정
# ─────────────────────────────────────────────
# 분석할 영상 리스트 (자동 스캔 or 수동 지정)
# 비워두면 INPUT_VIDEO_DIR 내 모든 .mp4/.avi 를 자동 수집
VIDEO_FILES: List[str] = []

# 영상 태그: 정적(static) / 동적(dynamic) 구분
# 형식 → {"파일이름.mp4": "static", "squat.mp4": "dynamic"}
# 태그가 없는 영상은 "dynamic" 으로 간주
VIDEO_TAGS: Dict[str, str] = {}

# 처리 해상도 (모델 입력 전처리)
FRAME_WIDTH = 640       # 넓이 (원본 유지하려면 None)
FRAME_HEIGHT = 480      # 높이 (원본 유지하려면 None)

# 웜업 프레임 수 (처음 N프레임은 측정에서 제외)
WARMUP_FRAMES = 30

# ─────────────────────────────────────────────
# 3) 모델 설정
# ─────────────────────────────────────────────
MODELS_TO_RUN = [
    "mediapipe",
    "movenet_lightning",
    "movenet_thunder",
    # "mmpose",            # 설치했을 때만 주석 해제
]

# MediaPipe 설정
MEDIAPIPE_COMPLEXITY = 1    # 0=Lite, 1=Full, 2=Heavy
MEDIAPIPE_MIN_DETECTION = 0.5
MEDIAPIPE_MIN_TRACKING = 0.5

# MoveNet TFHub URL
MOVENET_LIGHTNING_URL = (
    "https://tfhub.dev/google/movenet/singlepose/lightning/4"
)
MOVENET_THUNDER_URL = (
    "https://tfhub.dev/google/movenet/singlepose/thunder/4"
)

# MoveNet 입력 크기 (모델 고정)
MOVENET_LIGHTNING_SIZE = 192
MOVENET_THUNDER_SIZE = 256

# MMPose 설정 (선택)
MMPOSE_MODEL = "rtmpose-m"  # rtmpose-s / rtmpose-m / rtmpose-l

# ─────────────────────────────────────────────
# 4) 공통 키포인트 매핑 (17-COCO 기준)
# ─────────────────────────────────────────────
COCO_KEYPOINT_NAMES = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
]

# MediaPipe 33 → COCO 17 인덱스 매핑
MEDIAPIPE_TO_COCO = {
    0: 0,   # nose
    2: 1,   # left_eye_inner → left_eye
    5: 2,   # right_eye_inner → right_eye
    7: 3,   # left_ear
    8: 4,   # right_ear
    11: 5,  # left_shoulder
    12: 6,  # right_shoulder
    13: 7,  # left_elbow
    14: 8,  # right_elbow
    15: 9,  # left_wrist
    16: 10, # right_wrist
    23: 11, # left_hip
    24: 12, # right_hip
    25: 13, # left_knee
    26: 14, # right_knee
    27: 15, # left_ankle
    28: 16, # right_ankle
}

# ─────────────────────────────────────────────
# 5) Jitter 분석 설정
# ─────────────────────────────────────────────
# 정적 Jitter: 분석에 사용할 주요 관절 인덱스 (COCO 기준)
JITTER_JOINTS = [5, 6, 11, 12, 13, 14, 15, 16]
# → 어깨(5,6), 골반(11,12), 무릎(13,14), 발목(15,16)

# 동적 Jitter: 스무딩 윈도우 (Savitzky-Golay 필터)
SMOOTH_WINDOW = 15   # 홀수
SMOOTH_POLYORDER = 3

# ─────────────────────────────────────────────
# 6) 유틸리티 함수
# ─────────────────────────────────────────────
def get_video_list() -> List[Path]:
    """분석 대상 영상 목록 반환"""
    if VIDEO_FILES:
        return [INPUT_VIDEO_DIR / f for f in VIDEO_FILES]
    exts = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
    vids = sorted(
        p for p in INPUT_VIDEO_DIR.iterdir()
        if p.suffix.lower() in exts
    )
    return vids

def get_video_tag(video_path: Path) -> str:
    """영상의 태그(static/dynamic) 반환"""
    return VIDEO_TAGS.get(video_path.name, "dynamic")
