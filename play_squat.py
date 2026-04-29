"""Play squat keypoints through the server to the 2D viewer.

Streams the squat_left_1_keypoints.json data at ~30 FPS through the WebSocket
server.  The server broadcasts to ALL connected clients (including the 2D viewer),
so you can watch the skeleton move in the browser.

Usage:
    1. Start server:  python run_steps.py --server
    2. Open viewer:   http://localhost:8000/viewer/
    3. Run this:      python play_squat.py [--loops N]
"""
import asyncio
import json
import sys
import argparse

try:
    import websockets
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "websockets"])
    import websockets

SERVER = "ws://127.0.0.1:8000/ws/pose"


async def main(loops: int = 1):
    print("Loading squat_left_1_keypoints.json...")
    with open("squat_left_1_keypoints.json", "r") as f:
        frames = json.load(f)

    print(f"Loaded {len(frames)} frames. Loops: {loops}")

    print(f"Connecting to {SERVER}...")
    try:
        async with websockets.connect(SERVER, ping_interval=None) as ws:
            print("Connected! Streaming squat animation...")
            print("Open http://localhost:8000/viewer/ to watch the skeleton.")

            # Background consumer: read server responses without blocking
            # This prevents the recv buffer from filling up
            async def consume():
                try:
                    while True:
                        await ws.recv()
                except Exception:
                    pass

            asyncio.create_task(consume())

            for loop in range(1, loops + 1):
                if loops > 1:
                    print(f"\n--- Loop {loop}/{loops} ---")

                for i, frame_data in enumerate(frames):
                    frame_idx = frame_data.get("frame", i)
                    payload = frame_data.get("keypoints", [])

                    if not payload:
                        continue

                    msg = json.dumps({
                        "data_type": "keypoints",
                        "frame_id": f"squat-{frame_idx}",
                        "payload": payload,
                    })

                    await ws.send(msg)

                    # Progress indicator every 50 frames
                    if i % 50 == 0:
                        print(f"  Frame {i}/{len(frames)}")

                    # ~30 FPS playback speed
                    await asyncio.sleep(0.033)

            print("\nStreaming finished!")
    except ConnectionRefusedError:
        print("Connection failed! Make sure the server is running:")
        print("  python run_steps.py --server")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Play squat keypoints animation")
    parser.add_argument("--loops", type=int, default=2, help="Number of playback loops (default: 2)")
    args = parser.parse_args()

    try:
        asyncio.run(main(args.loops))
    except KeyboardInterrupt:
        print("\nStopped.")
