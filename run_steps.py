"""Step-by-step pipeline runner matching the project architecture diagram.

Each step can be executed independently or chained together.

Usage:
    python run_steps.py --check          # Check all dependencies
    python run_steps.py --step 1         # Run specific step
    python run_steps.py --all            # Run full pipeline
    python run_steps.py --server         # Start real-time server + viewer
    python run_steps.py --help           # Show all options

Architecture Steps:
    Step 1: Data Preparation   — VideoLoader / WebcamCapture
    Step 2: Pose Estimation    — MoveNet / MediaPipe (17 joints)
    Step 3: Pose Normalization — Hip-centered, scale-invariant
    Step 4: 3D Lifting         — PoseLifterMLP + Pose Retargeting (smoothing)
    Step 5: DTW Comparison     — Expert pose vs user pose alignment
    Step 6: Score Engine       — Joint-weighted scoring
    Step 7: Feedback           — Deviation detection + message generation
    Step 8: UI Rendering       — 2D Web Viewer (Quest VR) / Unity 3D

Pipelines:
    A) Real-time Pipeline:  Webcam → Steps 2-7 → WebSocket → Viewer
    B) Training Pipeline:   Dataset → Train lifter model → Checkpoint
    C) Export Pipeline:     Dataset → Export Unity JSON sequences
    D) Offline Analysis:    Video → Steps 2-7 → Report
"""

from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

# Fix Windows console encoding for Korean/Unicode output
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="VR Pose Pipeline — Step-by-step executor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--check", action="store_true", help="Check environment and dependencies.")
    parser.add_argument("--step", type=int, choices=range(1, 9), help="Run a specific pipeline step (1-8).")
    parser.add_argument("--all", action="store_true", help="Run full offline analysis pipeline.")
    parser.add_argument("--server", action="store_true", help="Start real-time server with 2D viewer.")
    parser.add_argument("--train", action="store_true", help="Run training pipeline.")
    parser.add_argument("--export-unity", action="store_true", help="Run Unity export pipeline.")
    parser.add_argument("--video", type=str, help="Input video path for offline analysis.")
    parser.add_argument("--device", default="auto", help="cpu or cuda (default: auto)")
    args = parser.parse_args(argv)

    if not any([args.check, args.step, args.all, args.server, args.train, args.export_unity]):
        args.check = True

    if args.check:
        return check_environment()
    if args.server:
        return start_server()
    if args.train:
        return run_training_pipeline(args.device)
    if args.export_unity:
        return run_export_pipeline()
    if args.step:
        return run_step(args.step, args.video)
    if args.all:
        return run_full_pipeline(args.video)

    parser.print_help()
    return 0


# ================================================================
# Environment Check
# ================================================================

def check_environment() -> int:
    """Verify all dependencies and data paths."""
    print("=" * 60)
    print("  VR Pose Pipeline — Environment Check")
    print("=" * 60)

    checks = {
        "Python": check_python(),
        "PyTorch": check_import("torch"),
        "FastAPI": check_import("fastapi"),
        "uvicorn": check_import("uvicorn"),
        "NumPy": check_import("numpy"),
        "MediaPipe": check_import("mediapipe"),
        "OpenCV": check_import("cv2"),
        "websockets": check_import("websockets"),
        "matplotlib": check_import("matplotlib"),
    }

    # Check data paths
    data_checks = {
        "model_3d package": (PROJECT_ROOT / "model_3d" / "__init__.py").exists(),
        "pose_retargeting": (PROJECT_ROOT / "model_3d" / "pose_retargeting.py").exists(),
        "2D viewer": (PROJECT_ROOT / "viewer_2d" / "index.html").exists(),
        "server.py": (PROJECT_ROOT / "model_3d" / "server_app" / "server.py").exists(),
    }

    # Check optional paths
    optional_checks = {
        "SMPL-X model": (PROJECT_ROOT / "smplx_locked_head" / "neutral" / "model.npz").exists(),
        "pose_3d_v3 dataset": (PROJECT_ROOT / "pose_3d_v3").exists(),
        "Fitness dataset": any((PROJECT_ROOT / d).exists() for d in os.listdir(PROJECT_ROOT)
                               if d.startswith("013.")) if any(d.startswith("013.") for d in os.listdir(PROJECT_ROOT)) else False,
        "Lifter checkpoint": _find_best_checkpoint() is not None,
    }

    all_ok = True

    print("\n📦 Required Dependencies:")
    for name, ok in checks.items():
        status = "✅" if ok else "❌"
        if not ok:
            all_ok = False
        print(f"  {status} {name}")

    print("\n📂 Required Files:")
    for name, ok in data_checks.items():
        status = "✅" if ok else "❌"
        if not ok:
            all_ok = False
        print(f"  {status} {name}")

    print("\n📂 Optional Resources:")
    for name, ok in optional_checks.items():
        status = "✅" if ok else "⚠️"
        print(f"  {status} {name}")

    print("\n" + "=" * 60)
    if all_ok:
        print("✅ All required checks passed!")
        print("\nQuick start commands:")
        print(f"  {PYTHON} run_steps.py --server      # Start server + viewer")
        print(f"  {PYTHON} run_steps.py --train        # Train lifter model")
    else:
        print("❌ Some checks failed. Install missing dependencies:")
        print(f"  {PYTHON} -m pip install -r requirements.txt")

    print("=" * 60)
    return 0 if all_ok else 1


def check_python() -> bool:
    return sys.version_info >= (3, 8)


def check_import(module_name: str) -> bool:
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False


def _find_best_checkpoint() -> Optional[Path]:
    """Find the best available lifter checkpoint."""
    candidates = [
        PROJECT_ROOT / "model_3d" / "artifacts" / "checkpoints" / "fitness_pose_lifter_latest_best.pt",
        PROJECT_ROOT / "model_3d" / "artifacts" / "checkpoints" / "fitness_pose_lifter_latest.pt",
        PROJECT_ROOT / "model_3d" / "artifacts" / "checkpoints" / "pose_lifter_latest.pt",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


# ================================================================
# Pipeline A: Real-time Server
# ================================================================

def start_server() -> int:
    """Start the FastAPI server with 2D viewer."""
    print("🚀 Starting Real-time Pose Server...")
    print("   WebSocket: ws://0.0.0.0:8000/ws/pose")
    print("   2D Viewer: http://0.0.0.0:8000/viewer/")
    print("")
    print("   Quest 3: Open browser → http://<PC_IP>:8000/viewer/")
    print("   Press Ctrl+C to stop.")
    print("")

    return subprocess.call([
        PYTHON, "-m", "uvicorn",
        "model_3d.server_app.server:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--reload",
    ], cwd=str(PROJECT_ROOT))


# ================================================================
# Pipeline B: Training
# ================================================================

def run_training_pipeline(device: str = "auto") -> int:
    """Train the 2D→3D pose lifter model."""
    print("🏋️ Starting Training Pipeline...")

    device_arg = []
    if device != "auto":
        device_arg = ["--device", device]

    return subprocess.call([
        PYTHON, "-m", "model_3d.train_fitness_lifter",
        "--epochs", "800",
        "--batch-size", "256",
        *device_arg,
    ], cwd=str(PROJECT_ROOT))


# ================================================================
# Pipeline C: Unity Export
# ================================================================

def run_export_pipeline() -> int:
    """Export fitness sequences as Unity-ready JSON."""
    print("📦 Starting Unity Export Pipeline...")

    return subprocess.call([
        PYTHON, "-m", "model_3d.export_fitness_unity",
        "--split", "train", "val",
        "--limit", "0",
        "--view", "view1",
    ], cwd=str(PROJECT_ROOT))


# ================================================================
# Pipeline D: Step-by-step (Offline)
# ================================================================

STEP_DESCRIPTIONS = {
    1: "Data Preparation (VideoLoader / WebcamCapture)",
    2: "Pose Estimation (MoveNet / MediaPipe → 17 joints)",
    3: "Pose Normalization (Hip-centered, scale-invariant)",
    4: "3D Lifting + Retargeting (PoseLifterMLP + smoothing)",
    5: "DTW Comparison (Expert vs User pose alignment)",
    6: "Score Engine (Joint-weighted scoring)",
    7: "Feedback Generator (Deviation detection + messages)",
    8: "UI Rendering (2D Web Viewer / Unity 3D)",
}


def run_step(step: int, video_path: Optional[str] = None) -> int:
    """Run a specific pipeline step."""
    desc = STEP_DESCRIPTIONS.get(step, "Unknown")
    print(f"\n{'=' * 50}")
    print(f"  Step {step}: {desc}")
    print(f"{'=' * 50}\n")

    if step == 1:
        return step_1_data_check(video_path)
    elif step == 2:
        return step_2_pose_estimation(video_path)
    elif step == 3:
        print("  → Normalization is integrated into Step 2 output.")
        print("  → Hip-centered coordinates are produced automatically.")
        return 0
    elif step == 4:
        return step_4_lifting()
    elif step == 5:
        print("  → DTW comparison is performed during real-time pipeline.")
        print("  → Run: python run_steps.py --server")
        return 0
    elif step == 6:
        print("  → Scoring is integrated into the server pipeline.")
        print("  → Run: python run_steps.py --server")
        return 0
    elif step == 7:
        print("  → Feedback generation is integrated into the server pipeline.")
        print("  → PostureAnalyzer in server_app/posture_analyzer.py")
        return 0
    elif step == 8:
        return start_server()
    return 1


def step_1_data_check(video_path: Optional[str] = None) -> int:
    """Check input data availability."""
    print("Checking input sources...\n")

    if video_path and Path(video_path).exists():
        print(f"  ✅ Video: {video_path}")
    else:
        videos = list(PROJECT_ROOT.glob("*.mp4"))
        if videos:
            print(f"  ✅ Found {len(videos)} video(s):")
            for v in videos[:5]:
                print(f"     - {v.name}")
        else:
            print("  ⚠️ No video files found in project root.")

    keypoints_file = PROJECT_ROOT / "squat_left_1_keypoints.json"
    if keypoints_file.exists():
        with open(keypoints_file) as f:
            data = json.load(f)
        print(f"  ✅ Keypoints: {keypoints_file.name} ({len(data)} frames)")
    else:
        print("  ⚠️ No pre-extracted keypoints file found.")

    print("\n  → To capture from webcam: python -m model_3d.server_app.clients.webcam_client")
    print("  → To process video: python -m model_3d.server_app.clients.video_client --video <path>")
    return 0


def step_2_pose_estimation(video_path: Optional[str] = None) -> int:
    """Run pose estimation on video."""
    if not video_path:
        print("  Pose estimation requires a video input.")
        print("  Usage: python run_steps.py --step 2 --video <path>")
        print("  Or start the server for real-time: python run_steps.py --server")
        return 0

    print(f"  Processing: {video_path}")
    return subprocess.call([
        PYTHON, "-m", "model_3d.server_app.clients.video_client",
        "--video", video_path,
    ], cwd=str(PROJECT_ROOT))


def step_4_lifting() -> int:
    """Check lifting model availability."""
    checkpoint = _find_best_checkpoint()
    if checkpoint:
        print(f"  ✅ Checkpoint found: {checkpoint.name}")
        print(f"     Path: {checkpoint}")

        # Quick validation
        return subprocess.call([
            PYTHON, "-m", "model_3d",
            "--lifter-checkpoint", str(checkpoint),
            "--dummy",
        ], cwd=str(PROJECT_ROOT))
    else:
        print("  ⚠️ No lifter checkpoint found.")
        print("  → Train one: python run_steps.py --train")
        return 1


def run_full_pipeline(video_path: Optional[str] = None) -> int:
    """Run all steps in sequence."""
    print("🔄 Running Full Offline Pipeline...\n")

    for step in range(1, 8):
        result = run_step(step, video_path)
        if result != 0:
            print(f"\n❌ Step {step} failed with exit code {result}")
            return result
        print("")

    print("✅ Full pipeline completed!")
    return 0


# ================================================================
# Entry Point
# ================================================================

if __name__ == "__main__":
    raise SystemExit(main())
