"""Debug: see what the server actually responds with."""
import asyncio
import json
import sys

try:
    import websockets
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "websockets"])
    import websockets

SERVER = "ws://127.0.0.1:8000/ws/pose"

SAMPLE_PAYLOAD = [
    [0.20, 0.50, 0.90], [0.18, 0.48, 0.85], [0.18, 0.52, 0.85],
    [0.19, 0.46, 0.80], [0.19, 0.54, 0.80], [0.34, 0.42, 0.92],
    [0.34, 0.58, 0.92], [0.50, 0.38, 0.88], [0.50, 0.62, 0.88],
    [0.64, 0.36, 0.80], [0.64, 0.64, 0.80], [0.58, 0.45, 0.93],
    [0.58, 0.55, 0.93], [0.78, 0.43, 0.94], [0.78, 0.57, 0.94],
    [0.95, 0.42, 0.90], [0.95, 0.58, 0.90],
]


async def main():
    print(f"Connecting to {SERVER}...")
    async with websockets.connect(SERVER) as ws:
        print("Connected! Sending 1 frame...")
        msg = json.dumps({
            "data_type": "keypoints",
            "frame_id": "debug-0",
            "payload": SAMPLE_PAYLOAD,
        })
        await ws.send(msg)
        print("Sent. Waiting for response...")
        resp_raw = await asyncio.wait_for(ws.recv(), timeout=30)
        print(f"\n=== RAW RESPONSE (first 2000 chars) ===")
        print(resp_raw[:2000])
        print(f"\n=== RESPONSE KEYS ===")
        try:
            data = json.loads(resp_raw)
            print(f"Top-level keys: {list(data.keys())}")
            if "fit" in data:
                print(f"fit keys: {list(data['fit'].keys())}")
                bp = data['fit'].get('body_pose')
                go = data['fit'].get('global_orient')
                print(f"body_pose length: {len(bp) if bp else 'None'}")
                print(f"global_orient length: {len(go) if go else 'None'}")
            if "feedback" in data:
                print(f"feedback: {data['feedback']}")
            else:
                print("NO 'feedback' key found!")
        except Exception as e:
            print(f"Parse error: {e}")
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
