"""Quick test: send sample keypoints to the server via WebSocket."""
import asyncio
import json
import sys

try:
    import websockets
except ImportError:
    print("Installing websockets...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "websockets"])
    import websockets

SERVER = "ws://127.0.0.1:8000/ws/pose"

# Sample MoveNet-style keypoints (17 joints × [y, x, confidence])
SAMPLE_PAYLOAD = [
    [0.20, 0.50, 0.90],  # nose
    [0.18, 0.48, 0.85],  # left_eye
    [0.18, 0.52, 0.85],  # right_eye
    [0.19, 0.46, 0.80],  # left_ear
    [0.19, 0.54, 0.80],  # right_ear
    [0.34, 0.42, 0.92],  # left_shoulder
    [0.34, 0.58, 0.92],  # right_shoulder
    [0.50, 0.38, 0.88],  # left_elbow
    [0.50, 0.62, 0.88],  # right_elbow
    [0.64, 0.36, 0.80],  # left_wrist
    [0.64, 0.64, 0.80],  # right_wrist
    [0.58, 0.45, 0.93],  # left_hip
    [0.58, 0.55, 0.93],  # right_hip
    [0.78, 0.43, 0.94],  # left_knee
    [0.78, 0.57, 0.94],  # right_knee
    [0.95, 0.42, 0.90],  # left_ankle
    [0.95, 0.58, 0.90],  # right_ankle
]


async def main():
    print(f"Connecting to {SERVER}...")
    async with websockets.connect(SERVER) as ws:
        print("Connected! Sending 50 frames at 10 FPS...")
        for i in range(50):
            msg = json.dumps({
                "data_type": "keypoints",
                "frame_id": f"test-{i}",
                "payload": SAMPLE_PAYLOAD,
            })
            await ws.send(msg)
            resp = json.loads(await ws.recv())
            feedback = resp.get("feedback", {}).get("label", "?")
            knee = resp.get("feedback", {}).get("knee_angle_deg", 0)
            print(f"  Frame {i:3d}: {feedback} (knee={knee:.1f}°)")
            await asyncio.sleep(0.1)
    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
