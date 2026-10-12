"""
step4_visualize.py — 시각화 차트 생성
──────────────────────────────────────
Step 3 결과를 기반으로:
  1) FPS 비교 Bar Chart
  2) Latency 분포 Box Plot
  3) Jitter 비교 Bar Chart
  4) 프레임별 Latency 시계열 Line Chart
  5) 관절별 궤적 비교 Line Chart
를 생성합니다.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")      # GUI 없이 파일 저장
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

from config import (
    RAW_DIR, CHART_DIR, REPORT_DIR, MODELS_TO_RUN,
    COCO_KEYPOINT_NAMES, JITTER_JOINTS,
    get_video_list, get_video_tag,
)


# ──────────────────────────────────────────────────
# 한글 폰트 설정 (Windows)
# ──────────────────────────────────────────────────
def setup_korean_font():
    """Malgun Gothic 등 한국어 폰트 설정"""
    candidates = ["Malgun Gothic", "NanumGothic", "AppleGothic"]
    available = {f.name for f in fm.fontManager.ttflist}
    for font in candidates:
        if font in available:
            plt.rcParams["font.family"] = font
            break
    plt.rcParams["axes.unicode_minus"] = False


# ──────────────────────────────────────────────────
# 색상 팔레트
# ──────────────────────────────────────────────────
MODEL_COLORS = {
    "mediapipe":        "#4285F4",   # Google Blue
    "movenet_lightning": "#FBBC04",  # Google Yellow
    "movenet_thunder":   "#EA4335", # Google Red
    "mmpose":           "#34A853",   # Google Green
}


def get_color(model: str) -> str:
    return MODEL_COLORS.get(model, "#888888")


# ══════════════════════════════════════════════════════
#  차트 1: FPS 비교 Bar Chart
# ══════════════════════════════════════════════════════
def chart_fps_comparison(summary_df: pd.DataFrame):
    """모델별 평균 FPS 비교"""
    fig, ax = plt.subplots(figsize=(10, 6))

    models = summary_df["Model"].unique()
    videos = summary_df["Video"].unique()
    x = np.arange(len(videos))
    width = 0.8 / len(models)

    for i, model in enumerate(models):
        subset = summary_df[summary_df["Model"] == model]
        fps_vals = []
        for v in videos:
            row = subset[subset["Video"] == v]
            fps_vals.append(row["Avg FPS"].values[0] if len(row) > 0 else 0)
        bars = ax.bar(x + i * width, fps_vals, width,
                      label=model, color=get_color(model), edgecolor="white")
        # 값 라벨
        for bar, val in zip(bars, fps_vals):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                    f"{val:.0f}", ha="center", va="bottom", fontsize=9)

    ax.axhline(y=60, color="red", linestyle="--", alpha=0.7, label="60 FPS 목표")
    ax.set_xlabel("Video")
    ax.set_ylabel("Average FPS")
    ax.set_title("모델별 평균 FPS 비교")
    ax.set_xticks(x + width * (len(models) - 1) / 2)
    ax.set_xticklabels(videos, rotation=20, ha="right")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()

    path = CHART_DIR / "01_fps_comparison.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  📊  {path.name}")
    return path


# ══════════════════════════════════════════════════════
#  차트 2: Latency 분포 Box Plot
# ══════════════════════════════════════════════════════
def chart_latency_boxplot(csv_map: dict):
    """모델별 프레임 Latency 분포"""
    fig, ax = plt.subplots(figsize=(10, 6))

    data_list = []
    labels = []

    for model in MODELS_TO_RUN:
        if model not in csv_map:
            continue
        # 모델의 모든 영상 latency를 합산
        all_ms = []
        for vstem, csv_path in csv_map[model].items():
            df = pd.read_csv(csv_path)
            all_ms.extend(df["inference_ms"].tolist())
        if all_ms:
            data_list.append(all_ms)
            labels.append(model)

    bp = ax.boxplot(data_list, labels=labels, patch_artist=True,
                    showfliers=True, flierprops={"markersize": 2})
    for patch, label in zip(bp["boxes"], labels):
        patch.set_facecolor(get_color(label))
        patch.set_alpha(0.7)

    ax.axhline(y=16.67, color="red", linestyle="--", alpha=0.7,
               label="16.67ms (60FPS)")
    ax.set_ylabel("Inference Latency (ms)")
    ax.set_title("모델별 추론 지연시간 분포")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()

    path = CHART_DIR / "02_latency_boxplot.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  📊  {path.name}")
    return path


# ══════════════════════════════════════════════════════
#  차트 3: 프레임별 Latency 시계열
# ══════════════════════════════════════════════════════
def chart_latency_timeline(csv_map: dict, video_stem: str):
    """특정 영상에 대해 모델별 프레임 Latency 시계열"""
    fig, ax = plt.subplots(figsize=(12, 5))

    for model in MODELS_TO_RUN:
        if model not in csv_map or video_stem not in csv_map[model]:
            continue
        df = pd.read_csv(csv_map[model][video_stem])
        ax.plot(df["frame_idx"], df["inference_ms"],
                label=model, color=get_color(model), alpha=0.7, linewidth=0.8)

    ax.axhline(y=16.67, color="red", linestyle="--", alpha=0.5,
               label="16.67ms (60FPS)")
    ax.set_xlabel("Frame Index")
    ax.set_ylabel("Inference Latency (ms)")
    ax.set_title(f"프레임별 추론 지연시간 — {video_stem}")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()

    path = CHART_DIR / f"03_latency_timeline_{video_stem}.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  📊  {path.name}")
    return path


# ══════════════════════════════════════════════════════
#  차트 4: Jitter 비교 Bar Chart
# ══════════════════════════════════════════════════════
def chart_jitter_comparison(summary_df: pd.DataFrame):
    """모델별 Jitter 지표 비교"""
    # static jitter 또는 dynamic residual 이 있는 경우
    has_static = "Static Jitter (px)" in summary_df.columns
    has_dynamic = "Dynamic Residual (px)" in summary_df.columns

    if not has_static and not has_dynamic:
        print("  ⏭️  Jitter 데이터 없음, 스킵")
        return None

    fig, axes = plt.subplots(1, 2 if (has_static and has_dynamic) else 1,
                             figsize=(12, 5))
    if not isinstance(axes, np.ndarray):
        axes = [axes]

    ax_idx = 0

    if has_static:
        ax = axes[ax_idx]
        static_df = summary_df.dropna(subset=["Static Jitter (px)"])
        if not static_df.empty:
            models = static_df["Model"].values
            vals = static_df["Static Jitter (px)"].values
            colors = [get_color(m) for m in models]
            bars = ax.bar(models, vals, color=colors, edgecolor="white")
            for bar, val in zip(bars, vals):
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                        f"{val:.2f}", ha="center", va="bottom", fontsize=9)
            ax.set_ylabel("Jitter (px, std)")
            ax.set_title("정적 Jitter 비교 (낮을수록 안정)")
            ax.grid(axis="y", alpha=0.3)
        ax_idx += 1

    if has_dynamic and ax_idx < len(axes):
        ax = axes[ax_idx]
        dyn_df = summary_df.dropna(subset=["Dynamic Residual (px)"])
        if not dyn_df.empty:
            models = dyn_df["Model"].values
            vals = dyn_df["Dynamic Residual (px)"].values
            colors = [get_color(m) for m in models]
            bars = ax.bar(models, vals, color=colors, edgecolor="white")
            for bar, val in zip(bars, vals):
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                        f"{val:.2f}", ha="center", va="bottom", fontsize=9)
            ax.set_ylabel("Residual RMSE (px)")
            ax.set_title("동적 Jitter 비교 (낮을수록 안정)")
            ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    path = CHART_DIR / "04_jitter_comparison.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  📊  {path.name}")
    return path


# ══════════════════════════════════════════════════════
#  차트 5: 관절 궤적 비교
# ══════════════════════════════════════════════════════
def chart_trajectory_comparison(csv_map: dict, video_stem: str,
                                joint_name: str = "left_knee"):
    """특정 관절의 Y좌표 궤적을 모델별로 겹쳐 비교"""
    fig, ax = plt.subplots(figsize=(12, 5))

    for model in MODELS_TO_RUN:
        if model not in csv_map or video_stem not in csv_map[model]:
            continue
        df = pd.read_csv(csv_map[model][video_stem])
        col_y = f"{joint_name}_y"
        if col_y not in df.columns:
            continue
        ax.plot(df["frame_idx"], df[col_y],
                label=model, color=get_color(model), alpha=0.8, linewidth=1.0)

    ax.set_xlabel("Frame Index")
    ax.set_ylabel(f"{joint_name} Y (px)")
    ax.set_title(f"관절 궤적 비교 — {joint_name} — {video_stem}")
    ax.legend()
    ax.grid(alpha=0.3)
    ax.invert_yaxis()  # 이미지 좌표계 (y 아래로 증가)
    fig.tight_layout()

    path = CHART_DIR / f"05_trajectory_{joint_name}_{video_stem}.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  📊  {path.name}")
    return path


# ══════════════════════════════════════════════════════
#  메인
# ══════════════════════════════════════════════════════
def find_csvs() -> dict[str, dict[str, Path]]:
    """CSV를 {model: {video_stem: path}} 로 수집"""
    result = {}
    for csv_path in sorted(RAW_DIR.glob("*.csv")):
        name = csv_path.stem
        matched_model = None
        for m in MODELS_TO_RUN:
            if name.startswith(m + "_"):
                matched_model = m
                break
        if matched_model is None:
            continue
        video_stem = name[len(matched_model) + 1:]
        result.setdefault(matched_model, {})[video_stem] = csv_path
    return result


def main():
    print()
    print("╔══════════════════════════════════════════════╗")
    print("║   Step 4: 시각화 차트 생성                    ║")
    print("╚══════════════════════════════════════════════╝")

    setup_korean_font()

    # 요약 CSV 로드
    summary_csv = REPORT_DIR / "summary.csv"
    if not summary_csv.exists():
        print("  ❌  summary.csv 가 없습니다. step3 을 먼저 실행하세요.")
        sys.exit(1)

    summary_df = pd.read_csv(summary_csv)
    csv_map = find_csvs()

    if csv_map:
        # 1) FPS 비교
        chart_fps_comparison(summary_df)

        # 2) Latency Box Plot
        chart_latency_boxplot(csv_map)

        # 3) 프레임별 Latency 시계열 (영상별)
        all_stems = set()
        for vd in csv_map.values():
            all_stems.update(vd.keys())
        for vstem in sorted(all_stems):
            chart_latency_timeline(csv_map, vstem)

        # 4) Jitter 비교
        chart_jitter_comparison(summary_df)

        # 5) 관절 궤적 비교 (동적 영상만)
        videos = get_video_list()
        for v in videos:
            if get_video_tag(v) == "dynamic" and v.stem in all_stems:
                chart_trajectory_comparison(csv_map, v.stem, "left_knee")
                chart_trajectory_comparison(csv_map, v.stem, "left_shoulder")

    print(f"\n{'═' * 55}")
    print(f"  ✅  차트 저장 완료 → {CHART_DIR}")
    print(f"{'═' * 55}")


if __name__ == "__main__":
    main()
