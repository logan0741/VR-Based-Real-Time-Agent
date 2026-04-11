import asyncio
import json
import pickle
import time
import numpy as np
import websockets

SERVER_URL = "ws://127.0.0.1:8000/ws/pose"
DATA_PATH = r"c:\Project\VR-Based-Real-Time-Agent\pose_3d_v3\valid.pkl"

async def main():
    print(f"[{time.strftime('%H:%M:%S')}] 대용량 데이터셋 로딩 중... (최대 10초 소요될 수 있습니다)")
    print(f"경로: {DATA_PATH}")
    
    try:
        with open(DATA_PATH, "rb") as f:
            data = pickle.load(f)
            
        print(f"[{time.strftime('%H:%M:%S')}] 데이터 로드 완료! 총 {len(data)} 프레임을 찾았습니다.")
        
    except Exception as e:
        print(f"데이터 로드 실패: {e}")
        return

    print(f"[{time.strftime('%H:%M:%S')}] 서버에 연결합니다: {SERVER_URL}")
    async with websockets.connect(SERVER_URL, ping_interval=None) as ws:
        print("연결 성공! 피겨스케이팅 점프(S1_Salchow) 모션 스트리밍을 시작합니다. (중지: Ctrl+C)")
        
        # 서버에서 응답오는 것을 백그라운드에서 계속 읽어버리기 (버퍼 가득차서 터지는 것 방지)
        async def consume_messages():
            try:
                while True:
                    await ws.recv()
            except Exception:
                pass
                
        asyncio.create_task(consume_messages())
        
        # 피겨스케이팅 점프 프레임 구간: 0 ~ 756
        start_idx = 0
        end_idx = 757
        loop_count = 1
        num_frames = end_idx - start_idx
        
        while True:
            print(f"--- [재생 시작] 피겨스케이팅 반복: {loop_count} ---")
            for i in range(start_idx, end_idx):
                frame_kpts = data[i].get('joint_3d_image')
                if frame_kpts is None:
                    continue
                    
                frame_kpts = np.array(frame_kpts, dtype=np.float32)
                
                payload = frame_kpts.tolist()
                
                msg = {
                    "data_type": "keypoints",
                    "frame_id": f"dataset-salchow{loop_count}-frame{i}",
                    "payload": payload
                }
                
                # 송신
                await ws.send(json.dumps(msg))
                
                # 실시간 30 FPS 전송 대기
                await asyncio.sleep(0.033)
                
                if (i - start_idx) % 150 == 0 and i > start_idx:
                    print(f"  진행 상황: {i - start_idx} / {num_frames} 프레임 전송 중...")
            
            loop_count += 1

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n스트리밍을 종료합니다.")
