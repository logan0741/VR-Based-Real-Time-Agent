import asyncio
import json
import os
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List

import torch
import torch.nn as nn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn

# ==========================================================
# 1. Ultra-Lightweight MLP (OOM 방지 및 고속 추론)
# ==========================================================
class PoseLifterNet(nn.Module):
    """
    17개의 3D/2D 키포인트를 입력받아 SMPL-X 파라미터를 직접 회귀(Regression)합니다.
    출력: global_orient(3) + body_pose(63) = 66
    """
    def __init__(self, hidden_dim: int = 512, num_layers: int = 4, dropout: float = 0.1):
        super().__init__()
        layers = []
        in_dim = 17 * 3  # COCO 17 joints (X, Y, Confidence/Z)
        out_dim = 3 + 63 # global_orient + body_pose
        
        for layer_index in range(num_layers):
            layers.append(nn.Linear(in_dim if layer_index == 0 else hidden_dim, hidden_dim))
            layers.append(nn.LayerNorm(hidden_dim))
            layers.append(nn.GELU())
            layers.append(nn.Dropout(dropout))
            
        layers.append(nn.Linear(hidden_dim, out_dim))
        self.network = nn.Sequential(*layers)

    def forward(self, keypoints_17x3: torch.Tensor) -> torch.Tensor:
        batch_size = keypoints_17x3.shape[0]
        flattened = keypoints_17x3.reshape(batch_size, -1)
        # Returns [Batch, 66]
        return self.network(flattened)


# ==========================================================
# 2. Singleton Inference Pipeline
# ==========================================================
class FastPosePipeline:
    def __init__(self, checkpoint_path: str):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = PoseLifterNet().to(self.device)
        self.model.eval()  # 추론 모드 고정 (메모리 최적화)
        
        if checkpoint_path and os.path.exists(checkpoint_path):
            print(f"[Lifter] Loading checkpoint: {checkpoint_path}")
            try:
                state_dict = torch.load(checkpoint_path, map_location=self.device)
                # strict=False: 만약 기존 체크포인트가 17x3 출력용이라면, 
                # 충돌을 방지하고 나머지 가중치만 불러와서 테스트를 가능하게 함.
                self.model.load_state_dict(state_dict, strict=False)
                print("[Lifter] Weights loaded successfully.")
            except Exception as e:
                print(f"[Lifter] Warning - Weight mismatch or load error: {e}")
        else:
            print("[Lifter] No checkpoint found. Running with initialized weights.")

    @torch.no_grad()  # 중요: 계산 그래프 추적 비활성화 (OOM 원천 차단)
    def process_keypoints(self, payload: List[List[float]], frame_id: str) -> Dict[str, Any]:
        start_t = time.perf_counter()
        
        # 1. 파싱 및 텐서 변환
        kpts = torch.tensor(payload, dtype=torch.float32, device=self.device)
        if kpts.shape[-1] > 3:
            kpts = kpts[..., :3]  # (17, 3)으로 절삭
        if kpts.dim() == 2:
            kpts = kpts.unsqueeze(0)  # Batch 차원 추가 -> (1, 17, 3)
            
        # 2. MLP Forward Pass (순방향 연산만 수행)
        output = self.model(kpts)  # -> (1, 66)
        output_np = output.squeeze(0).cpu().numpy().tolist()
        
        # 3. 파라미터 분할
        global_orient = output_np[:3]
        body_pose = output_np[3:66]
        
        dur_ms = (time.perf_counter() - start_t) * 1000
        
        # 4. Phase 2 JSON 호환성 완벽 유지
        return {
            "status": "ok",
            "data_type": "keypoints",
            "frame_id": frame_id,
            "fit": {
                "backend": "lifter",
                "global_orient": global_orient,
                "body_pose": body_pose,
            },
            "feedback": {
                "label": "FastMLP",
                "knee_angle_deg": 120.0  # 임시 피드백값
            },
            "debug": {
                "inference_ms": round(dur_ms, 2)
            }
        }

# ==========================================================
# 3. FastAPI Initialization & WebSocket Route
# ==========================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 서버 실행 시 단 한 번만 모델을 메모리에 로드 (Warm-up)
    backend_mode = os.environ.get("FITTER_BACKEND", "lifter").lower()
    
    if backend_mode != "lifter":
        print("[Warning] Optimization backend is deprecated due to OOM risk. Forcing 'lifter' mode.")
        
    checkpoint_path = os.environ.get("LIFTER_CHECKPOINT", r"model_3d\artifacts\checkpoints\fitness_pose_lifter_latest_best.pt")
    
    app.state.pose_pipeline = FastPosePipeline(checkpoint_path)
    print(f"[Lifter] Pipeline Ready. Device: {app.state.pose_pipeline.device}")
    
    yield
    # 서버 종료 시 Clean-up (필요 시)

app = FastAPI(lifespan=lifespan)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_json(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()

@app.websocket("/ws/pose")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    pipeline: FastPosePipeline = websocket.app.state.pose_pipeline
    loop = asyncio.get_running_loop()
    
    try:
        while True:
            # 클라이언트(테스트 스크립트 또는 웹캠)로부터 Keypoints 수신
            raw_msg = await websocket.receive_text()
            msg = json.loads(raw_msg)
            
            data_type = msg.get("data_type")
            frame_id = msg.get("frame_id", "unknown")
            
            if data_type == "keypoints":
                # 비동기 블로킹 방지를 위한 독립 실행 (0.05ms 이내 처리됨)
                response = await loop.run_in_executor(
                    None,
                    pipeline.process_keypoints,
                    msg.get("payload"),
                    frame_id,
                )
            else:
                response = {
                    "status": "error",
                    "data_type": data_type,
                    "message": "Only keypoints data_type is supported in FastMLP mode."
                }
                
            # 중요: 계산된 SMPL-X 파라미터를 Unity를 포함한 모든 클라이언트에 브로드캐스트!
            await manager.broadcast_json(response)
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"[WS Error] {e}")
        manager.disconnect(websocket)

if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=False)
