from __future__ import annotations

import argparse
import asyncio
import json
import math
import platform
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import websockets


ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "sample_coco17_keypoints.json"
RESULTS_DIR = ROOT / "results"


def now_ms() -> float:
    return time.perf_counter() * 1000.0


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_keypoints() -> List[List[float]]:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def animated_keypoints(base: List[List[float]], frame_index: int) -> List[List[float]]:
    phase = math.sin(frame_index / 7.0)
    out: List[List[float]] = []
    for idx, point in enumerate(base):
        y, x, conf = point
        y_offset = 0.025 * phase if idx in {11, 12, 13, 14, 15, 16} else 0.006 * phase
        out.append([max(0.03, min(0.97, y + y_offset)), x, conf])
    return out


def percentile(values: List[float], pct: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * pct
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[int(index)]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def summarize(values: List[float]) -> Dict[str, Optional[float]]:
    if not values:
        return {
            "count": 0,
            "min_ms": None,
            "avg_ms": None,
            "median_ms": None,
            "p90_ms": None,
            "p95_ms": None,
            "max_ms": None,
        }
    return {
        "count": len(values),
        "min_ms": round(min(values), 3),
        "avg_ms": round(statistics.fmean(values), 3),
        "median_ms": round(statistics.median(values), 3),
        "p90_ms": round(percentile(values, 0.90) or 0.0, 3),
        "p95_ms": round(percentile(values, 0.95) or 0.0, 3),
        "max_ms": round(max(values), 3),
    }


async def receiver(name: str, ws: Any, send_times: Dict[str, float], samples: List[Dict[str, Any]], stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
        except asyncio.TimeoutError:
            continue

        received_at = now_ms()
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue

        frame_id = str(msg.get("frame_id", ""))
        if not frame_id or frame_id not in send_times:
            continue

        debug = msg.get("debug") or {}
        relay_only = bool(debug.get("relay_only"))
        sample_type = "relay_pose" if relay_only else "processed_feedback"
        latency_ms = received_at - send_times[frame_id]
        samples.append(
            {
                "client": name,
                "frame_id": frame_id,
                "sample_type": sample_type,
                "latency_ms": round(latency_ms, 3),
                "received_data_type": msg.get("data_type"),
                "status": msg.get("status"),
                "message": msg.get("message"),
                "body_part": msg.get("body_part"),
                "debug": debug,
            }
        )


async def run_probe(ws_url: str, frames: int, fps: float, exercise_type: str) -> Dict[str, Any]:
    base = load_keypoints()
    interval_sec = 1.0 / fps
    send_times: Dict[str, float] = {}
    samples: List[Dict[str, Any]] = []
    stop = asyncio.Event()

    async with websockets.connect(ws_url, max_size=8 * 1024 * 1024) as viewer_ws, websockets.connect(
        ws_url, max_size=8 * 1024 * 1024
    ) as app_ws:
        recv_tasks = [
            asyncio.create_task(receiver("viewer_echo", viewer_ws, send_times, samples, stop)),
            asyncio.create_task(receiver("app_receiver", app_ws, send_times, samples, stop)),
        ]

        await viewer_ws.send(
            json.dumps(
                {
                    "data_type": "session_config",
                    "user_id": "latency_lab",
                    "exercise_type": exercise_type,
                    "sets": 1,
                    "reps_per_set": 8,
                }
            )
        )
        await asyncio.sleep(0.2)

        started = now_ms()
        for frame_index in range(frames):
            frame_id = f"latency_lab_{int(started)}_{frame_index:04d}"
            send_times[frame_id] = now_ms()
            await viewer_ws.send(
                json.dumps(
                    {
                        "data_type": "keypoints",
                        "frame_id": frame_id,
                        "client_timestamp_ms": int(time.time() * 1000),
                        "payload": animated_keypoints(base, frame_index),
                    }
                )
            )
            await asyncio.sleep(interval_sec)

        await asyncio.sleep(3.0)
        stop.set()
        await asyncio.gather(*recv_tasks, return_exceptions=True)

    relay_viewer = [s["latency_ms"] for s in samples if s["client"] == "viewer_echo" and s["sample_type"] == "relay_pose"]
    relay_app = [s["latency_ms"] for s in samples if s["client"] == "app_receiver" and s["sample_type"] == "relay_pose"]
    processed_viewer = [
        s["latency_ms"] for s in samples if s["client"] == "viewer_echo" and s["sample_type"] == "processed_feedback"
    ]
    processed_app = [
        s["latency_ms"] for s in samples if s["client"] == "app_receiver" and s["sample_type"] == "processed_feedback"
    ]

    return {
        "metadata": {
            "created_at_utc": utc_iso(),
            "ws_url": ws_url,
            "frames_sent": frames,
            "target_fps": fps,
            "exercise_type": exercise_type,
            "python": platform.python_version(),
            "platform": platform.platform(),
            "method": "Synthetic COCO-17 keypoints sent as viewer; separate app-like receiver measures broadcast latency.",
            "scope_note": "Browser camera inference and canvas draw time are not included.",
        },
        "summary": {
            "viewer_relay_echo": summarize(relay_viewer),
            "app_relay_receive": summarize(relay_app),
            "viewer_processed_feedback": summarize(processed_viewer),
            "app_processed_feedback": summarize(processed_app),
            "frame_delivery": {
                "relay_frames_at_viewer": len({s["frame_id"] for s in samples if s["client"] == "viewer_echo" and s["sample_type"] == "relay_pose"}),
                "relay_frames_at_app": len({s["frame_id"] for s in samples if s["client"] == "app_receiver" and s["sample_type"] == "relay_pose"}),
                "processed_frames_at_viewer": len({s["frame_id"] for s in samples if s["client"] == "viewer_echo" and s["sample_type"] == "processed_feedback"}),
                "processed_frames_at_app": len({s["frame_id"] for s in samples if s["client"] == "app_receiver" and s["sample_type"] == "processed_feedback"}),
            },
        },
        "samples": samples,
    }


def write_markdown(report: Dict[str, Any], path: Path) -> None:
    meta = report["metadata"]
    summary = report["summary"]
    lines = [
        "# App / Viewer Latency Report",
        "",
        f"- Created: `{meta['created_at_utc']}`",
        f"- WebSocket URL: `{meta['ws_url']}`",
        f"- Frames sent: `{meta['frames_sent']}`",
        f"- Target FPS: `{meta['target_fps']}`",
        f"- Exercise: `{meta['exercise_type']}`",
        "",
        "## Result Summary",
        "",
        "| Path | Count | Avg | Median | P90 | P95 | Max |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    labels = {
        "viewer_relay_echo": "viewer echo, live skeleton relay",
        "app_relay_receive": "app receive, live skeleton relay",
        "viewer_processed_feedback": "viewer receive, processed feedback",
        "app_processed_feedback": "app receive, processed feedback",
    }
    for key, label in labels.items():
        row = summary[key]
        lines.append(
            f"| {label} | {row['count']} | {row['avg_ms']} ms | {row['median_ms']} ms | "
            f"{row['p90_ms']} ms | {row['p95_ms']} ms | {row['max_ms']} ms |"
        )

    delivery = summary["frame_delivery"]
    lines.extend(
        [
            "",
            "## Delivery Counts",
            "",
            f"- Relay frames at viewer: `{delivery['relay_frames_at_viewer']}`",
            f"- Relay frames at app: `{delivery['relay_frames_at_app']}`",
            f"- Processed frames at viewer: `{delivery['processed_frames_at_viewer']}`",
            f"- Processed frames at app: `{delivery['processed_frames_at_app']}`",
            "",
            "## Interpretation",
            "",
            "- The relay path is the live 2D skeleton path. This should stay close to real time.",
            "- The processed feedback path includes backend preprocessing, rep counting, scoring, and feedback policy.",
            "- If processed frame count is lower than sent frames, it is expected when the backend drops old frames and keeps the latest frame.",
            "- Browser TF.js pose extraction and canvas rendering are outside this synthetic measurement.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Measure app/viewer WebSocket latency.")
    parser.add_argument("--ws-url", default="ws://127.0.0.1:8000/ws/pose")
    parser.add_argument("--frames", type=int, default=90)
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--exercise", default="squat")
    parser.add_argument("--label", default="latest", help="Output label, for example local or cloudflare.")
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    report = await run_probe(args.ws_url, args.frames, args.fps, args.exercise)
    safe_label = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in args.label)
    json_path = RESULTS_DIR / f"latency_report_{safe_label}.json"
    md_path = RESULTS_DIR / f"latency_report_{safe_label}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(report, md_path)
    (RESULTS_DIR / "latency_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(report, RESULTS_DIR / "latency_report.md")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    asyncio.run(main())
