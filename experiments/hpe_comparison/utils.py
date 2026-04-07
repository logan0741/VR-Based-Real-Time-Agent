"""
utils.py — 공통 유틸리티
─────────────────────────
영상 읽기, 키포인트 변환, 저장 등 공용 함수 모음.
"""
from __future__ import annotations

import time
import csv
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import pandas as pd

from config import (
    FRAME_WIDTH, FRAME_HEIGHT,
    COCO_KEYPOINT_NAMES,
    MEDIAPIPE_TO_COCO,
)


# ──────────────────────────────────────────────────
# 영상 I/O
# ──────────────────────────────────────────────────
class VideoReader:
    """프레임 단위 영상 읽기 + 리사이즈"""

    def __init__(self, path: str | Path):
        self.path = str(path)
        self.cap = cv2.VideoCapture(self.path)
        if not self.cap.isOpened():
            raise FileNotFoundError(f"영상 열기 실패: {self.path}")

        self.orig_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.orig_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))

        self.target_w = FRAME_WIDTH or self.orig_w
        self.target_h = FRAME_HEIGHT or self.orig_h

    def __iter__(self):
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        return self

    def __next__(self) -> np.ndarray:
        ret, frame = self.cap.read()
        if not ret:
            raise StopIteration
        if (frame.shape[1], frame.shape[0]) != (self.target_w, self.target_h):
            frame = cv2.resize(frame, (self.target_w, self.target_h))
        return frame

    def __len__(self):
        return self.total_frames

    def __del__(self):
        if self.cap.isOpened():
            self.cap.release()

    @property
    def info(self) -> dict:
        return {
            "path": self.path,
            "original_size": f"{self.orig_w}x{self.orig_h}",
            "target_size": f"{self.target_w}x{self.target_h}",
            "fps": self.fps,
            "total_frames": self.total_frames,
        }


# ──────────────────────────────────────────────────
# 키포인트 변환·정규화
# ──────────────────────────────────────────────────
def mediapipe_to_coco(landmarks, img_w: int, img_h: int) -> np.ndarray:
    """
    MediaPipe 33 랜드마크 → COCO 17 키포인트 (px 좌표)
    반환: shape (17, 3) → [x_px, y_px, confidence]
    """
    kps = np.zeros((17, 3), dtype=np.float32)
    for mp_idx, coco_idx in MEDIAPIPE_TO_COCO.items():
        lm = landmarks[mp_idx]
        kps[coco_idx] = [lm.x * img_w, lm.y * img_h, lm.visibility]
    return kps


def movenet_to_coco(keypoints: np.ndarray, img_w: int, img_h: int) -> np.ndarray:
    """
    MoveNet 출력 → COCO 17 키포인트 (px 좌표)
    입력: shape (1,1,17,3) → [y_norm, x_norm, score]
    반환: shape (17, 3) → [x_px, y_px, confidence]
    """
    kps_raw = keypoints[0, 0]  # (17, 3)
    kps = np.zeros((17, 3), dtype=np.float32)
    for i in range(17):
        y_n, x_n, score = kps_raw[i]
        kps[i] = [x_n * img_w, y_n * img_h, score]
    return kps


# ──────────────────────────────────────────────────
# 결과 저장·로드
# ──────────────────────────────────────────────────
def build_csv_header() -> list[str]:
    """CSV 컬럼 헤더 생성"""
    cols = ["frame_idx", "inference_ms"]
    for name in COCO_KEYPOINT_NAMES:
        cols.extend([f"{name}_x", f"{name}_y", f"{name}_conf"])
    return cols


def keypoints_to_row(frame_idx: int, inference_ms: float,
                     kps: np.ndarray) -> list:
    """키포인트 → CSV 한 줄"""
    row = [frame_idx, round(inference_ms, 4)]
    for i in range(17):
        row.extend([
            round(float(kps[i, 0]), 2),
            round(float(kps[i, 1]), 2),
            round(float(kps[i, 2]), 4),
        ])
    return row


def save_csv(rows: list, header: list[str], path: Path):
    """CSV 저장"""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"  💾 저장 완료: {path}  ({len(rows)} rows)")


def load_result_csv(path: Path) -> pd.DataFrame:
    """저장된 결과 CSV 로드"""
    return pd.read_csv(path)


# ──────────────────────────────────────────────────
# 타이머
# ──────────────────────────────────────────────────
class Timer:
    """간단한 고해상도 타이머 (ms 단위)"""

    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.elapsed_ms = (time.perf_counter() - self.start) * 1000
