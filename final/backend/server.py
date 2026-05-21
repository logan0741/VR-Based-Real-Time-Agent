"""FastAPI WebSocket server for real-time pose estimation and avatar control.

Unity sends COCO-17 keypoints to this server. The server runs the MLP lifter,
returns SMPL-X pose parameters for avatar feedback, and saves completed
exercise session summaries to MySQL.
"""

import asyncio
import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import torch
import torch.nn as nn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from .pose_retargeting import PoseRetargeter
from .database import DatabaseSettings, ExerciseSessionRepository, now_utc
from .posture_analyzer import PostureAnalyzer


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


class PoseLifterNet(nn.Module):
    """Lightweight MLP that maps COCO-17 keypoints to SMPL-X pose params."""

    def __init__(self, hidden_dim: int = 512, num_layers: int = 4, dropout: float = 0.1):
        super().__init__()
        layers = []
        in_dim = 17 * 3
        out_dim = 3 + 63

        for layer_index in range(num_layers):
            layers.append(nn.Linear(in_dim if layer_index == 0 else hidden_dim, hidden_dim))
            layers.append(nn.LayerNorm(hidden_dim))
            layers.append(nn.GELU())
            layers.append(nn.Dropout(dropout))

        layers.append(nn.Linear(hidden_dim, out_dim))
        self.network = nn.Sequential(*layers)

    def forward(self, keypoints_17x3: torch.Tensor) -> torch.Tensor:
        batch_size = keypoints_17x3.shape[0]
        return self.network(keypoints_17x3.reshape(batch_size, -1))


class ExerciseSessionTracker:
    """Tracks one active exercise session and persists it when it ends."""

    def __init__(self, repository: ExerciseSessionRepository):
        self.repository = repository
        self.active_session: Optional[Dict[str, Any]] = None

    def start(self, user_id: str = "anonymous", exercise_type: str = "squat") -> Dict[str, Any]:
        self.active_session = {
            "session_id": uuid4().hex,
            "user_id": user_id or "anonymous",
            "exercise_type": exercise_type or "squat",
            "started_at": now_utc(),
            "scores": [],
            "labels": [],
            "frames": 0,
        }
        return self.active_session

    def ensure_active(self, user_id: str = "anonymous", exercise_type: str = "squat") -> Dict[str, Any]:
        if self.active_session is None:
            return self.start(user_id=user_id, exercise_type=exercise_type)
        return self.active_session

    def record_frame(self, score: float, label: str) -> None:
        session = self.ensure_active()
        session["frames"] += 1
        session["scores"].append(float(score))
        session["labels"].append(label or "")

    def finish(self) -> Dict[str, Any]:
        session = self.ensure_active()
        ended_at = now_utc()
        scores = session["scores"] or [0.0]
        summary = {
            "session_id": session["session_id"],
            "user_id": session["user_id"],
            "exercise_type": session["exercise_type"],
            "started_at": session["started_at"],
            "ended_at": ended_at,
            "duration_ms": int((ended_at - session["started_at"]).total_seconds() * 1000),
            "frame_count": int(session["frames"]),
            "avg_score": round(sum(scores) / len(scores), 2),
            "best_score": round(max(scores), 2),
            "worst_score": round(min(scores), 2),
            "final_label": session["labels"][-1] if session["labels"] else "",
        }
        summary["saved_to_db"] = self.repository.save_session(summary)
        summary["started_at"] = summary["started_at"].isoformat()
        summary["ended_at"] = summary["ended_at"].isoformat()
        self.active_session = None
        return summary


class FastPosePipeline:
    def __init__(self, checkpoint_path: str, repository: ExerciseSessionRepository):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.analyzer = PostureAnalyzer(exercise_type="squat")
        self.retargeter = PoseRetargeter()
        self.repository = repository
        print(f"[Retargeter] Smoothing enabled: {self.retargeter.enabled}")

        backend_mode = os.environ.get("FITTER_BACKEND", "lifter").lower()
        self._backend = backend_mode

        if backend_mode == "optimization":
            from model_3d.fitter import OptimizationPoseFitter
            print("[Pipeline] Backend: SMPL-X OptimizationFitter")
            self._opt_fitter = OptimizationPoseFitter()
            self.model = None
        else:
            self._opt_fitter = None
            self.model = PoseLifterNet().to(self.device)
            self.model.eval()
            if checkpoint_path and os.path.exists(checkpoint_path):
                print(f"[Lifter] Loading checkpoint: {checkpoint_path}")
                try:
                    try:
                        state_dict = torch.load(checkpoint_path, map_location=self.device, weights_only=True)
                    except TypeError:
                        state_dict = torch.load(checkpoint_path, map_location=self.device)
                    self.model.load_state_dict(state_dict, strict=False)
                    print("[Lifter] Weights loaded successfully.")
                except Exception as exc:
                    print(f"[Lifter] Warning - weight load error: {exc}")
            else:
                print("[Lifter] No checkpoint found. Running with initialized weights.")

    def process_keypoints(
        self,
        payload: List[List[float]],
        frame_id: str,
        session_tracker: ExerciseSessionTracker,
    ) -> Dict[str, Any]:
        start_t = time.perf_counter()
        error = self._validate_keypoints(payload)
        if error:
            return {"status": "error", "message": error, "frame_id": frame_id}

        if self._backend == "optimization":
            return self._process_optimization(payload, frame_id, session_tracker, start_t)
        return self._process_lifter(payload, frame_id, session_tracker, start_t)

    def _process_optimization(
        self,
        payload: List[List[float]],
        frame_id: str,
        session_tracker: ExerciseSessionTracker,
        start_t: float,
    ) -> Dict[str, Any]:
        import numpy as np
        result = self._opt_fitter.forward(payload)

        smoothed = self.retargeter.smooth_all(
            body_pose=result.body_pose,
            global_orient=result.global_orient,
            joints_3d=result.joints_3d,
            t=time.perf_counter(),
        )
        global_orient = smoothed["global_orient"].tolist()
        body_pose = smoothed["body_pose"].tolist()
        joints_3d = smoothed["joints_3d"].tolist()

        kpts_np = np.array(payload, dtype=np.float32)
        fatigue_state = self.analyzer.analyze(kpts_np)
        high_fatigue = [k for k, v in fatigue_state.items() if v == "high"]
        mid_fatigue = [k for k, v in fatigue_state.items() if v in {"mid", "med"}]
        if high_fatigue:
            fatigue_summary = f"주의: {', '.join(high_fatigue)}"
        elif mid_fatigue:
            fatigue_summary = f"보통: {', '.join(mid_fatigue)}"
        else:
            fatigue_summary = "양호"

        pose_score = min(100, max(0, 100 - len(high_fatigue) * 15 - len(mid_fatigue) * 5))
        session_tracker.record_frame(pose_score, fatigue_summary)
        session_id = session_tracker.ensure_active()["session_id"]
        dur_ms = (time.perf_counter() - start_t) * 1000

        return {
            "status": "ok",
            "frame_id": frame_id,
            "session_id": session_id,
            "keypoints_2d": payload,
            "fit": {
                "backend": "optimization",
                "global_orient": global_orient,
                "body_pose": body_pose,
                "joints_3d": joints_3d,
                "reprojection_loss": result.reprojection_loss,
            },
            "feedback": {
                "score": pose_score,
                "label": fatigue_summary,
                "muscle_fatigue": fatigue_state,
            },
            "debug": {
                "inference_ms": round(dur_ms, 2),
                "smoothing_enabled": self.retargeter.enabled,
                "smoothing_frame": self.retargeter.frame_count,
            },
        }

    @torch.no_grad()
    def _process_lifter(
        self,
        payload: List[List[float]],
        frame_id: str,
        session_tracker: ExerciseSessionTracker,
        start_t: float,
    ) -> Dict[str, Any]:
        kpts = torch.tensor(payload, dtype=torch.float32, device=self.device)
        if kpts.shape[-1] > 3:
            kpts = kpts[..., :3]
        if kpts.dim() == 2:
            kpts = kpts.unsqueeze(0)

        output = self.model(kpts).squeeze(0).cpu().numpy()
        global_orient_raw = output[:3]
        body_pose_raw = output[3:66]

        smoothed = self.retargeter.smooth_all(
            body_pose=body_pose_raw,
            global_orient=global_orient_raw,
            t=time.perf_counter(),
        )
        global_orient = smoothed["global_orient"].tolist()
        body_pose = smoothed["body_pose"].tolist()

        kpts_np = kpts.squeeze(0).cpu().numpy()
        fatigue_state = self.analyzer.analyze(kpts_np)
        high_fatigue = [k for k, v in fatigue_state.items() if v == "high"]
        mid_fatigue = [k for k, v in fatigue_state.items() if v in {"mid", "med"}]
        if high_fatigue:
            fatigue_summary = f"주의: {', '.join(high_fatigue)}"
        elif mid_fatigue:
            fatigue_summary = f"보통: {', '.join(mid_fatigue)}"
        else:
            fatigue_summary = "양호"

        pose_score = min(100, max(0, 75 + int(self.retargeter.frame_count % 20) - 10))
        session_tracker.record_frame(pose_score, fatigue_summary)
        session_id = session_tracker.ensure_active()["session_id"]
        dur_ms = (time.perf_counter() - start_t) * 1000

        return {
            "status": "ok",
            "frame_id": frame_id,
            "session_id": session_id,
            "keypoints_2d": payload,
            "fit": {
                "backend": "lifter",
                "global_orient": global_orient,
                "body_pose": body_pose,
            },
            "feedback": {
                "score": pose_score,
                "label": fatigue_summary,
                "muscle_fatigue": fatigue_state,
            },
            "debug": {
                "inference_ms": round(dur_ms, 2),
                "smoothing_enabled": self.retargeter.enabled,
                "smoothing_frame": self.retargeter.frame_count,
            },
        }

    def reset_smoothing(self) -> None:
        self.retargeter.reset()

    def start_session(
        self,
        session_tracker: ExerciseSessionTracker,
        user_id: str = "anonymous",
        exercise_type: str = "squat",
    ) -> Dict[str, Any]:
        self.reset_smoothing()
        session = session_tracker.start(user_id=user_id, exercise_type=exercise_type)
        return {
            "status": "ok",
            "data_type": "session_start",
            "session_id": session["session_id"],
            "user_id": session["user_id"],
            "exercise_type": session["exercise_type"],
        }

    def finish_session(self, session_tracker: ExerciseSessionTracker) -> Dict[str, Any]:
        return {
            "status": "ok",
            "data_type": "session_end",
            "summary": session_tracker.finish(),
        }

    @staticmethod
    def _validate_keypoints(payload: Any) -> Optional[str]:
        if not isinstance(payload, list) or len(payload) != 17:
            return "keypoints payload must be a list of 17 joints"
        for index, joint in enumerate(payload):
            if not isinstance(joint, list) or len(joint) < 3:
                return f"joint {index} must contain at least [x, y, confidence]"
            for value in joint[:3]:
                if not isinstance(value, (int, float)):
                    return f"joint {index} contains a non-numeric value"
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    project_root = Path(__file__).resolve().parents[2]
    load_env_file(project_root / ".env")

    checkpoint_path = os.environ.get(
        "LIFTER_CHECKPOINT",
        r"model_3d\artifacts\checkpoints\fitness_pose_lifter_latest_best.pt",
    )

    app.state.exercise_repository = ExerciseSessionRepository(DatabaseSettings.from_env())
    app.state.pose_pipeline = FastPosePipeline(checkpoint_path, app.state.exercise_repository)
    app.state.http_session_tracker = ExerciseSessionTracker(app.state.exercise_repository)
    print(f"[Lifter] Pipeline Ready. Device: {app.state.pose_pipeline.device}")
    yield


app = FastAPI(lifespan=lifespan, title="VR Pose Estimation Server")

_viewer_dir = Path(__file__).resolve().parents[1] / "frontend"
if _viewer_dir.exists():
    app.mount("/viewer", StaticFiles(directory=str(_viewer_dir), html=True), name="viewer_2d")

_react_dist_dir = Path(__file__).resolve().parents[2] / "dist"
if _react_dist_dir.exists():
    app.mount("/app", StaticFiles(directory=str(_react_dist_dir), html=True), name="react_app")


@app.get("/")
async def root():
    if _viewer_dir.exists() and (_viewer_dir / "index.html").exists():
        return FileResponse(str(_viewer_dir / "index.html"))
    return {
        "service": "VR Pose Estimation Server",
        "websocket": "/ws/pose",
        "database": app.state.exercise_repository.health(),
        "react_app": "/app/" if _react_dist_dir.exists() else "not built",
        "viewer": "/viewer/" if _viewer_dir.exists() else "not available",
    }


@app.get("/api/health")
async def health():
    return {"status": "ok", "database": app.state.exercise_repository.health()}


@app.post("/api/reset")
async def reset_smoothing():
    app.state.pose_pipeline.reset_smoothing()
    return {"status": "ok", "message": "Smoothing filters reset."}


@app.post("/api/session/start")
async def start_session(payload: Dict[str, Any]):
    return app.state.pose_pipeline.start_session(
        app.state.http_session_tracker,
        user_id=payload.get("user_id", "anonymous"),
        exercise_type=payload.get("exercise_type", "squat"),
    )


@app.post("/api/session/end")
async def end_session():
    return app.state.pose_pipeline.finish_session(app.state.http_session_tracker)


@app.get("/api/expert")
async def get_expert_poses():
    project_root = Path(__file__).resolve().parents[2]
    candidates = [project_root / "squat_left_1_keypoints.json"]
    candidates.extend(sorted(project_root.glob("*_keypoints.json")))

    for path in candidates:
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return {
                    "status": "ok",
                    "filename": path.name,
                    "total_frames": len(data),
                    "frames": data,
                }
            except Exception as exc:
                return {"status": "error", "message": str(exc)}

    return {"status": "error", "message": "No expert keypoints file found."}


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_json(self, message: Dict[str, Any]):
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
    session_tracker = ExerciseSessionTracker(websocket.app.state.exercise_repository)
    loop = asyncio.get_running_loop()

    try:
        while True:
            raw_msg = await websocket.receive_text()
            msg = json.loads(raw_msg)
            data_type = msg.get("data_type")
            frame_id = msg.get("frame_id", "unknown")

            if data_type == "keypoints":
                response = await loop.run_in_executor(
                    None,
                    pipeline.process_keypoints,
                    msg.get("payload"),
                    frame_id,
                    session_tracker,
                )
            elif data_type == "session_start":
                response = pipeline.start_session(
                    session_tracker,
                    user_id=msg.get("user_id", "anonymous"),
                    exercise_type=msg.get("exercise_type", "squat"),
                )
            elif data_type == "session_end":
                response = pipeline.finish_session(session_tracker)
            elif data_type == "reset":
                pipeline.reset_smoothing()
                response = {"status": "ok", "data_type": "reset", "message": "Smoothing filters reset."}
            else:
                response = {
                    "status": "error",
                    "data_type": data_type,
                    "message": "Supported data_type values: keypoints, session_start, session_end, reset.",
                }

            await manager.broadcast_json(response)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as exc:
        print(f"[WS Error] {exc}")
        manager.disconnect(websocket)


if __name__ == "__main__":
    uvicorn.run(
        "model_3d.server_app.server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
