"""
step3_analyze.py — 추론 결과 분석
──────────────────────────────────
Step 2에서 생성된 CSV 파일을 읽어:
  A) 처리량(FPS / Latency) 통계
  B) 정적 Jitter (표준편차)
  C) 동적 Jitter (가속도 변동)
를 계산하고, 요약 테이블을 출력·저장합니다.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import savgol_filter
from tabulate import tabulate

from config import (
    RAW_DIR, REPORT_DIR, MODELS_TO_RUN,
    COCO_KEYPOINT_NAMES, JITTER_JOINTS,
    SMOOTH_WINDOW, SMOOTH_POLYORDER,
    get_video_list, get_video_tag,
)


# ══════════════════════════════════════════════════════
#  CSV 탐색
# ══════════════════════════════════════════════════════
def find_csvs() -> dict[str, dict[str, Path]]:
    """
    RAW_DIR 내 CSV를 {model: {video_stem: path}} 로 수집
    파일명 규칙: {model}_{video_stem}.csv
    """
    result = {}
    for csv_path in sorted(RAW_DIR.glob("*.csv")):
        name = csv_path.stem  # e.g.  mediapipe_squat
        # 모델 이름 분리: 가장 먼저 매칭되는 모델 접두사 사용
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


# ══════════════════════════════════════════════════════
#  A) 처리량 분석
# ══════════════════════════════════════════════════════
def analyze_throughput(df: pd.DataFrame) -> dict:
    """inference_ms 컬럼으로 FPS/Latency 통계 계산"""
    ms = df["inference_ms"].values
    fps = 1000.0 / ms

    return {
        "avg_ms": np.mean(ms),
        "median_ms": np.median(ms),
        "p95_ms": np.percentile(ms, 95),
        "p99_ms": np.percentile(ms, 99),
        "std_ms": np.std(ms),
        "avg_fps": np.mean(fps),
        "min_fps": np.min(fps),
        "frames": len(ms),
    }


# ══════════════════════════════════════════════════════
#  B) 정적 Jitter (Static)
# ══════════════════════════════════════════════════════
def analyze_static_jitter(df: pd.DataFrame) -> dict:
    """
    정지 영상의 각 관절 좌표 표준편차·MAE 계산.
    반환: 관절별 jitter 값 + 평균
    """
    joint_jitters = {}
    for j_idx in JITTER_JOINTS:
        name = COCO_KEYPOINT_NAMES[j_idx]
        x = df[f"{name}_x"].values
        y = df[f"{name}_y"].values

        # 표준편차 (px)
        std_x = np.std(x)
        std_y = np.std(y)
        jitter_px = np.sqrt(std_x ** 2 + std_y ** 2)
        joint_jitters[name] = round(jitter_px, 3)

    avg_jitter = np.mean(list(joint_jitters.values()))
    return {
        "per_joint": joint_jitters,
        "mean_jitter_px": round(avg_jitter, 3),
    }


# ══════════════════════════════════════════════════════
#  C) 동적 Jitter (Dynamic)
# ══════════════════════════════════════════════════════
def analyze_dynamic_jitter(df: pd.DataFrame) -> dict:
    """
    동적 영상에서 궤적의 '떨림' 측정:
    1) Savitzky-Golay 필터로 스무딩
    2) 원본과 스무딩 사이의 잔차(residual) RMSE 계산
    3) 가속도(2차 미분) 표준편차 계산
    """
    n = len(df)
    if n < SMOOTH_WINDOW + 5:
        return {"mean_residual_px": None, "mean_accel_std": None,
                "per_joint": {}}

    joint_metrics = {}
    for j_idx in JITTER_JOINTS:
        name = COCO_KEYPOINT_NAMES[j_idx]
        x = df[f"{name}_x"].values.astype(float)
        y = df[f"{name}_y"].values.astype(float)

        # 스무딩
        win = min(SMOOTH_WINDOW, n - 1)
        if win % 2 == 0:
            win -= 1
        if win < SMOOTH_POLYORDER + 2:
            win = SMOOTH_POLYORDER + 2
            if win % 2 == 0:
                win += 1

        x_smooth = savgol_filter(x, win, SMOOTH_POLYORDER)
        y_smooth = savgol_filter(y, win, SMOOTH_POLYORDER)

        # 잔차 RMSE
        residual = np.sqrt((x - x_smooth) ** 2 + (y - y_smooth) ** 2)
        rmse = np.sqrt(np.mean(residual ** 2))

        # 가속도 (2차 미분) std
        vx = np.diff(x)
        vy = np.diff(y)
        ax = np.diff(vx)
        ay = np.diff(vy)
        accel_mag = np.sqrt(ax ** 2 + ay ** 2)
        accel_std = np.std(accel_mag)

        joint_metrics[name] = {
            "residual_rmse_px": round(rmse, 3),
            "accel_std_px": round(accel_std, 3),
        }

    mean_res = np.mean([v["residual_rmse_px"] for v in joint_metrics.values()])
    mean_acc = np.mean([v["accel_std_px"] for v in joint_metrics.values()])

    return {
        "mean_residual_px": round(mean_res, 3),
        "mean_accel_std": round(mean_acc, 3),
        "per_joint": joint_metrics,
    }


# ══════════════════════════════════════════════════════
#  요약 테이블
# ══════════════════════════════════════════════════════
def build_summary(all_results: dict) -> pd.DataFrame:
    """전체 결과를 하나의 요약 DataFrame으로"""
    rows = []
    for key, data in all_results.items():
        model, video = key
        tp = data["throughput"]
        row = {
            "Model": model,
            "Video": video,
            "Avg FPS": round(tp["avg_fps"], 1),
            "Avg Latency (ms)": round(tp["avg_ms"], 2),
            "P95 Latency (ms)": round(tp["p95_ms"], 2),
            "P99 Latency (ms)": round(tp["p99_ms"], 2),
            "Frames": tp["frames"],
        }

        jitter = data.get("static_jitter") or data.get("dynamic_jitter")
        if jitter:
            if "mean_jitter_px" in jitter:
                row["Static Jitter (px)"] = jitter["mean_jitter_px"]
            if "mean_residual_px" in jitter and jitter["mean_residual_px"] is not None:
                row["Dynamic Residual (px)"] = jitter["mean_residual_px"]
                row["Accel Std (px)"] = jitter["mean_accel_std"]

        rows.append(row)

    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════
#  메인
# ══════════════════════════════════════════════════════
def main():
    print()
    print("╔══════════════════════════════════════════════╗")
    print("║   Step 3: 결과 분석                          ║")
    print("╚══════════════════════════════════════════════╝")

    csv_map = find_csvs()
    if not csv_map:
        print("  ❌  분석할 CSV가 없습니다. step2 를 먼저 실행하세요.")
        sys.exit(1)

    videos = get_video_list()
    video_tag_map = {v.stem: get_video_tag(v) for v in videos}

    all_results = {}

    for model, vid_dict in csv_map.items():
        for vstem, csv_path in vid_dict.items():
            print(f"\n  📊  분석: {model} × {vstem}")
            df = pd.read_csv(csv_path)

            tag = video_tag_map.get(vstem, "dynamic")
            tp = analyze_throughput(df)
            print(f"      Avg FPS: {tp['avg_fps']:.1f}  |  "
                  f"Avg Latency: {tp['avg_ms']:.2f} ms  |  "
                  f"P99: {tp['p99_ms']:.2f} ms")

            result_entry = {"throughput": tp}

            if tag == "static":
                sj = analyze_static_jitter(df)
                result_entry["static_jitter"] = sj
                print(f"      Static Jitter (mean): {sj['mean_jitter_px']} px")
            else:
                dj = analyze_dynamic_jitter(df)
                result_entry["dynamic_jitter"] = dj
                if dj["mean_residual_px"] is not None:
                    print(f"      Dynamic Residual RMSE: {dj['mean_residual_px']} px")
                    print(f"      Accel Std: {dj['mean_accel_std']} px")

            all_results[(model, vstem)] = result_entry

    # 요약 테이블
    summary_df = build_summary(all_results)
    print("\n")
    print("=" * 75)
    print("  📋  요약 (Summary)")
    print("=" * 75)
    print(tabulate(summary_df, headers="keys", tablefmt="rounded_grid",
                   showindex=False))

    # 저장
    summary_csv = REPORT_DIR / "summary.csv"
    summary_df.to_csv(summary_csv, index=False, encoding="utf-8-sig")
    print(f"\n  💾  요약 CSV → {summary_csv}")

    # 상세 JSON
    import json
    detail_path = REPORT_DIR / "detail_results.json"
    serializable = {}
    for (m, v), data in all_results.items():
        serializable[f"{m}__{v}"] = data
    with open(detail_path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)
    print(f"  💾  상세 JSON → {detail_path}")

    print(f"\n  👉  다음 단계: python step4_visualize.py")


if __name__ == "__main__":
    main()
