import asyncio
import json
import websockets
import time
from pathlib import Path

async def send_mock_data():
    uri = "ws://127.0.0.1:8000/ws/pose"
    project_root = Path(r"C:\Project\VR-Based-Real-Time-Agent")
    json_path = project_root / "squat_left_1_keypoints.json"
    
    if not json_path.exists():
        print(f"Error: Could not find {json_path}")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        frames = json.load(f)

    print(f"Loaded {len(frames)} frames. Connecting to {uri}...")
    
    while True:
        try:
            async with websockets.connect(uri) as websocket:
                print("Connected! Sending frames...")
                frame_idx = 0
                while True:
                    for frame_data in frames:
                        # Depending on JSON structure, extract keypoints array
                        kp_list = frame_data.get("keypoints") if isinstance(frame_data, dict) else frame_data
                        if not isinstance(kp_list, list) or len(kp_list) != 17:
                            continue
                        
                        payload = {
                            "data_type": "keypoints",
                            "frame_id": f"mock_{frame_idx}",
                            "client_timestamp_ms": int(time.time() * 1000),
                            "payload": kp_list
                        }
                        await websocket.send(json.dumps(payload))
                        frame_idx += 1
                        await asyncio.sleep(1/30.0) # 30 FPS
        except Exception as e:
            print(f"Connection failed: {e}. Retrying in 2 seconds...")
            await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(send_mock_data())
