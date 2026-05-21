"""
07_pipeline_web.py — Pipeline A: Web-Only (Unity 없이 실행)

구성: FastAPI 서버 + 2D 웹 뷰어 (Quest 3 브라우저 대응)
백엔드: SMPL-X OptimizationFitter
입력: 웹캠 또는 영상 파일 (별도 터미널에서 클라이언트 실행)

실행:
    python final/07_pipeline_web.py
    python final/07_pipeline_web.py --port 8080
    python final/07_pipeline_web.py --cloudflare
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Web-Only Pipeline (no Unity)")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--cloudflare", action="store_true", help="Expose via Cloudflare Tunnel")
    parser.add_argument("--backend", default="lifter", choices=["optimization", "lifter"],
                        help="lifter=MLP 빠름(기본, 웹캠용), optimization=SMPL-X 피팅 정확(Unity용)")
    args = parser.parse_args()

    # 환경 설정
    os.environ.setdefault("FITTER_BACKEND", args.backend)
    os.environ.setdefault("DB_ENABLED", "true")

    print("=" * 55)
    print("  VR PT — Web-Only Pipeline")
    print("=" * 55)
    print(f"  Backend  : {args.backend}")
    print(f"  Port     : {args.port}")
    print(f"  2D Viewer: http://localhost:{args.port}/viewer/")
    print(f"  React App: http://localhost:{args.port}/app/")
    print("")
    print("  입력 클라이언트 (별도 터미널):")
    print(f"    웹캠:  python -m model_3d.server_app.clients.webcam_client")
    print(f"    영상:  python -m model_3d.server_app.clients.video_client --video <파일>")
    print(f"    재생:  python play_squat.py")
    print("=" * 55)

    if is_port_in_use(args.port):
        print(f"[오류] 포트 {args.port} 사용 중. --port 옵션으로 변경하세요.")
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
        print("\n[Cloudflare] 터널 시작 중... 출력된 https URL로 Quest 3 접속\n")
        return subprocess.call([cloudflared, "tunnel", "--url", f"http://127.0.0.1:{port}"])
    finally:
        server.terminate()


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


if __name__ == "__main__":
    raise SystemExit(main())
