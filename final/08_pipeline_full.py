"""
Pipeline B: Full Pipeline (Unity 포함 전체 시스템)

구성: FastAPI 서버 + SMPL-X OptimizationFitter + Unity WebSocket + 2D 뷰어
백엔드: SMPL-X optimization (정확한 body_pose/global_orient 생성)

Unity 연결:
    ws://<PC_IP>:8000/ws/pose    (LAN)
    wss://<cloudflare-url>/ws/pose  (외부/HTTPS)

실행:
    python final/08_pipeline_full.py
    python final/08_pipeline_full.py --cloudflare   # Unity 외부 접속 시
"""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def get_local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def main() -> int:
    parser = argparse.ArgumentParser(description="Full Pipeline with Unity")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--cloudflare", action="store_true")
    parser.add_argument("--iters", type=int, default=15, help="SMPL-X 최적화 반복 횟수 (낮을수록 빠름)")
    args = parser.parse_args()

    # SMPL-X optimization 강제 설정
    os.environ["FITTER_BACKEND"] = "optimization"
    os.environ["SMPLX_MODEL_PATH"] = str(PROJECT_ROOT / "smplx_locked_head" / "neutral" / "model.npz")
    os.environ["SMPLX_OPT_ITERS"] = str(args.iters)
    os.environ.setdefault("DB_ENABLED", "true")

    local_ip = get_local_ip()

    print("=" * 60)
    print("  VR PT — Full Pipeline (Unity + Web Viewer)")
    print("=" * 60)
    print(f"  Backend    : SMPL-X OptimizationFitter ({args.iters} iters/frame)")
    print(f"  Port       : {args.port}")
    print(f"  2D Viewer  : http://{local_ip}:{args.port}/viewer/")
    print(f"  React App  : http://{local_ip}:{args.port}/app/")
    print("")
    print("  [Unity Inspector 설정]")
    print(f"  serverUrl  : ws://{local_ip}:{args.port}/ws/pose")
    print("")
    print("  [서버 → Unity 전송 포맷]")
    print("  fit.global_orient : [rx, ry, rz]  (axis-angle, 라디안, SMPL-X 좌표계)")
    print("  fit.body_pose     : [rx,ry,rz x21] (21관절 axis-angle)")
    print("  fit.joints_3d     : [[x,y,z] x17]  (COCO-17 3D 참고좌표)")
    print("")
    print("  [Unity 변환 공식]")
    print("  axis = new Vector3(-axisAngle.x, axisAngle.y, axisAngle.z)")
    print("  angle = -axis.magnitude * Rad2Deg")
    print("=" * 60)

    if is_port_in_use(args.port):
        print(f"[오류] 포트 {args.port} 사용 중.")
        return 1

    if args.cloudflare:
        return run_with_cloudflare(args.port)

    return subprocess.call([
        PYTHON, "-m", "uvicorn",
        "final.s02_backend.server:app",
        "--host", "0.0.0.0",
        "--port", str(args.port),
    ], cwd=str(PROJECT_ROOT))


def run_with_cloudflare(port: int) -> int:
    cloudflared = shutil.which("cloudflared")
    if not cloudflared:
        local_path = (
            Path(os.environ.get("LOCALAPPDATA", ""))
            / "Microsoft" / "WinGet" / "Packages"
        )
        matches = sorted(local_path.glob("Cloudflare.cloudflared_*/*cloudflared.exe")) if local_path.exists() else []
        cloudflared = str(matches[-1]) if matches else None

    if not cloudflared:
        print("[오류] cloudflared 미설치. winget install Cloudflare.cloudflared 후 재시도")
        return 1

    server = subprocess.Popen([
        PYTHON, "-m", "uvicorn",
        "final.s02_backend.server:app",
        "--host", "0.0.0.0", "--port", str(port),
    ], cwd=str(PROJECT_ROOT))

    try:
        time.sleep(3)
        print("\n[Cloudflare] 터널 시작... 출력된 https:// URL을 Unity serverUrl에 wss://로 변경해서 입력\n")
        return subprocess.call([cloudflared, "tunnel", "--url", f"http://127.0.0.1:{port}"])
    finally:
        server.terminate()


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


if __name__ == "__main__":
    raise SystemExit(main())
