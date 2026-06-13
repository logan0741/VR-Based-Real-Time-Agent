from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any, Dict

from measure_latency import RESULTS_DIR, run_probe, write_markdown


def save_report(label: str, report: Dict[str, Any]) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RESULTS_DIR / f"latency_report_{label}.json"
    md_path = RESULTS_DIR / f"latency_report_{label}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(report, md_path)


def load_summary(label: str) -> Dict[str, Any]:
    path = RESULTS_DIR / f"latency_report_{label}.json"
    return json.loads(path.read_text(encoding="utf-8"))["summary"]


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run local and Cloudflare latency probes.")
    parser.add_argument("--local-url", default="ws://127.0.0.1:8000/ws/pose")
    parser.add_argument("--cloud-url", default="wss://pt.gun-hee.com/ws/pose")
    parser.add_argument("--frames", type=int, default=90)
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--exercise", default="squat")
    args = parser.parse_args()

    local_report = await run_probe(args.local_url, args.frames, args.fps, args.exercise)
    save_report("local", local_report)

    cloud_report = await run_probe(args.cloud_url, args.frames, args.fps, args.exercise)
    save_report("cloudflare", cloud_report)

    combined = {
        "metadata": {
            "frames": args.frames,
            "fps": args.fps,
            "exercise": args.exercise,
            "local_url": args.local_url,
            "cloud_url": args.cloud_url,
        },
        "local": local_report["summary"],
        "cloudflare": cloud_report["summary"],
        "conclusion": {
            "local_relay_avg_ms": local_report["summary"]["app_relay_receive"]["avg_ms"],
            "cloudflare_relay_avg_ms": cloud_report["summary"]["app_relay_receive"]["avg_ms"],
            "local_processed_avg_ms": local_report["summary"]["app_processed_feedback"]["avg_ms"],
            "cloudflare_processed_avg_ms": cloud_report["summary"]["app_processed_feedback"]["avg_ms"],
        },
    }
    combined_path = RESULTS_DIR / "latency_suite_summary.json"
    combined_path.write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        "# Latency Suite Summary",
        "",
        f"- Local URL: `{args.local_url}`",
        f"- Cloudflare URL: `{args.cloud_url}`",
        f"- Frames: `{args.frames}`",
        f"- FPS: `{args.fps}`",
        "",
        "## Key Numbers",
        "",
        f"- Local app relay avg: `{combined['conclusion']['local_relay_avg_ms']} ms`",
        f"- Cloudflare app relay avg: `{combined['conclusion']['cloudflare_relay_avg_ms']} ms`",
        f"- Local app processed avg: `{combined['conclusion']['local_processed_avg_ms']} ms`",
        f"- Cloudflare app processed avg: `{combined['conclusion']['cloudflare_processed_avg_ms']} ms`",
        "",
        "## Reading",
        "",
        "- If local latency is low but Cloudflare latency is high, the current bottleneck is outside the backend preprocessing path.",
        "- If both local and Cloudflare are high, inspect backend preprocessing, queueing, and frame dropping.",
        "- `relay` is the live skeleton path. `processed` is the feedback/scoring path.",
    ]
    (RESULTS_DIR / "latency_suite_summary.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(json.dumps(combined["conclusion"], ensure_ascii=False, indent=2))
    print(f"Wrote {combined_path}")


if __name__ == "__main__":
    asyncio.run(main())
