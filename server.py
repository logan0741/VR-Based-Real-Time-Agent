"""
FastAPI + ngrok WebSocket server for the VR real-time 3D pose pipeline.

Run:
    python server.py

Client WebSocket message shape:
    {"data_type": "keypoints", "payload": [[y, x, score], ... 17 items ...]}

Phase 2 image message shape:
    {"data_type": "image", "payload": "base64_string"}
"""

from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from model_3d import build_pose_pipeline, env_bool
from model_3d.pipeline import PosePipeline

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - only used when python-dotenv is absent.
    load_dotenv = None


if load_dotenv is not None:
    load_dotenv()


async def enqueue_latest(queue: asyncio.Queue, item: Dict[str, Any]) -> None:
    """
    Keep only a small backlog of fresh frames.

    For real-time pose feedback, stale frames are worse than dropped frames. This
    policy prevents memory growth when the optimizer is slower than the VR client.
    """
    if queue.full():
        with suppress(asyncio.QueueEmpty):
            queue.get_nowait()
            queue.task_done()
    await queue.put(item)


async def pose_worker(
    websocket: WebSocket,
    queue: asyncio.Queue,
    send_lock: asyncio.Lock,
) -> None:
    pipeline: PosePipeline = websocket.app.state.pose_pipeline

    while True:
        message = await queue.get()
        try:
            data_type = message.get("data_type")
            frame_id = message.get("frame_id")
            if data_type == "keypoints":
                response = await asyncio.to_thread(
                    pipeline.process_keypoints,
                    message.get("payload"),
                    frame_id,
                )
            elif data_type == "image":
                response = pipeline.process_image(message.get("payload"), frame_id)
            else:
                response = {
                    "status": "error",
                    "message": f"Unsupported data_type={data_type}",
                }

            async with send_lock:
                await websocket.send_json(response)
        except Exception as exc:
            async with send_lock:
                await websocket.send_json(
                    {
                        "status": "error",
                        "data_type": message.get("data_type"),
                        "frame_id": message.get("frame_id"),
                        "message": str(exc),
                    }
                )
        finally:
            queue.task_done()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pose_pipeline = build_pose_pipeline()
    tunnel = None

    if env_bool("ENABLE_NGROK", True):
        try:
            from pyngrok import ngrok
        except ImportError as exc:
            raise RuntimeError(
                "pyngrok is required when ENABLE_NGROK=true. "
                "Install it with `pip install pyngrok` or set ENABLE_NGROK=false."
            ) from exc

        auth_token = os.getenv("NGROK_AUTHTOKEN")
        if auth_token:
            ngrok.set_auth_token(auth_token)

        port = int(os.getenv("API_PORT", "8000"))
        tunnel = ngrok.connect(addr=port, proto="http", bind_tls=True)
        app.state.ngrok_tunnel = tunnel

        http_url = tunnel.public_url
        websocket_url = http_url.replace("https://", "wss://").replace("http://", "ws://")
        print(f"[ngrok] Public HTTP URL: {http_url}")
        print(f"[ngrok] Public WebSocket URL: {websocket_url}/ws/pose")

    try:
        yield
    finally:
        if tunnel is not None:
            from pyngrok import ngrok

            ngrok.disconnect(tunnel.public_url)


app = FastAPI(
    title="VR-Based Real-Time Agent API",
    debug=env_bool("DEBUG", False),
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> Dict[str, Any]:
    pipeline = getattr(app.state, "pose_pipeline", None)
    return {
        "status": "ok",
        "backend": getattr(pipeline, "backend", os.getenv("FITTER_BACKEND", "unknown")),
        "websocket": "/ws/pose",
        "diagnostics_enabled": env_bool("DIAGNOSTICS_ENABLED", True),
    }


@app.websocket("/ws/pose")
async def websocket_pose(websocket: WebSocket) -> None:
    await websocket.accept()
    max_queue_size = int(os.getenv("POSE_QUEUE_MAXSIZE", "2"))
    frame_queue = asyncio.Queue(maxsize=max_queue_size)
    send_lock = asyncio.Lock()
    worker_task = asyncio.create_task(pose_worker(websocket, frame_queue, send_lock))

    try:
        while True:
            raw_message = await websocket.receive_text()
            try:
                message = json.loads(raw_message)
            except json.JSONDecodeError:
                async with send_lock:
                    await websocket.send_json(
                        {"status": "error", "message": "WebSocket payload must be valid JSON."}
                    )
                continue

            data_type = message.get("data_type")
            if data_type not in {"keypoints", "image"}:
                async with send_lock:
                    await websocket.send_json(
                        {
                            "status": "error",
                            "message": "data_type must be either 'keypoints' or 'image'.",
                        }
                    )
                continue

            if "payload" not in message:
                async with send_lock:
                    await websocket.send_json(
                        {"status": "error", "message": "Missing required field: payload."}
                    )
                continue

            await enqueue_latest(frame_queue, message)
    except WebSocketDisconnect:
        pass
    finally:
        worker_task.cancel()
        with suppress(asyncio.CancelledError):
            await worker_task


if __name__ == "__main__":
    import uvicorn

    module_name = Path(__file__).stem
    uvicorn.run(
        f"{module_name}:app",
        host=os.getenv("API_HOST", "127.0.0.1"),
        port=int(os.getenv("API_PORT", "8000")),
        reload=env_bool("API_RELOAD", False),
    )
