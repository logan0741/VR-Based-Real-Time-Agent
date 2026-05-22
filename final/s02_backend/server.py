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
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn

from .pose_retargeting import PoseRetargeter
from ..s03_database.database import DatabaseSettings, ExerciseSessionRepository, now_utc
from .posture_analyzer import PostureAnalyzer
from ..s01_preprocessing.config import EXERCISES
from ..s01_preprocessing.pose_normalizer import PoseNormalizer
from ..s01_preprocessing.rep_detector import RepDetector
from ..s01_preprocessing.expert_cache import ExpertPoseCache
from ..s01_preprocessing.feedback import FeedbackEngine, FeedbackPolicy

try:
    from ..s01_preprocessing.dtw_comparator import DTWComparator
    from ..s01_preprocessing.score_engine import ScoreEngine
    _DTW_AVAILABLE = True
except ImportError:
    _DTW_AVAILABLE = False
    print("[Pipeline] dtaidistance 미설치 — DTW 점수 비활성화. pip install dtaidistance==2.3.12")

from ..s01_preprocessing.score_engine import GeometricScorer


class PreprocessingSession:
    """연결별 전처리 파이프라인 상태 (PoseNormalizer, RepDetector, ScoreEngine, FeedbackPolicy)."""

    def __init__(
        self,
        cfg: dict,
        comparator: "DTWComparator",
        expert_cache: ExpertPoseCache,
        feedback_engine: FeedbackEngine,
    ) -> None:
        self._cfg = cfg
        self._comparator = comparator
        self._expert_cache = expert_cache
        self._feedback_engine = feedback_engine

        self._normalizer = PoseNormalizer(cfg["normalizer_type"], cfg["norm_buffer_size"])
        self._rep_detector = RepDetector(
            cfg["rep_detector_type"], cfg["normalizer_type"],
            cfg["rep_slope_window"], cfg["min_rep_frames"],
        )
        self._score_engine: Optional["ScoreEngine"] = (
            ScoreEngine(cfg["weights"], cfg["max_distance"], cfg["n_frames"])
            if _DTW_AVAILABLE else None
        )
        self._feedback_policy = FeedbackPolicy(hold_frames=cfg["target_fps"] * 3)

        self._norm_buffer: List[Any] = []
        self._last_dist_matrix: Optional[Any] = None
        self._known_reps: int = 0
        self._frame_idx: int = 0

    def process(self, kpts_np: Any) -> Dict[str, Any]:
        """1프레임 관절 데이터로 점수·횟수·피드백을 계산하고 반환한다."""
        import numpy as _np

        try:
            norm_kp = self._normalizer.normalize(kpts_np)
        except ValueError:
            return {"score": 50, "rep_count": 0, "rep_scores": [], "message": "자세를 화면 중앙에 맞춰주세요.", "body_part": "", "severity": 0.0}

        self._norm_buffer.append(norm_kp)

        # Rep 감지
        all_reps = self._rep_detector.update(norm_kp)
        new_reps = all_reps[self._known_reps:]
        new_rep_matrices: List[Any] = []

        if _DTW_AVAILABLE and self._score_engine is not None:
            for start, end in new_reps:
                if end <= len(self._norm_buffer):
                    try:
                        rep_seq = _np.stack(self._norm_buffer[start:end])
                        rep_dm = self._comparator.compare(rep_seq, self._expert_cache.sequence)
                        new_rep_matrices.append(rep_dm)
                    except Exception:
                        pass

            # DTW 계산 (dtw_interval마다)
            if self._frame_idx % self._cfg["dtw_interval"] == 0 and len(self._norm_buffer) >= 2:
                try:
                    window = _np.stack(self._norm_buffer[-self._cfg["n_frames"]:])
                    self._last_dist_matrix = self._comparator.compare(window, self._expert_cache.sequence)
                except Exception:
                    pass

        self._known_reps = len(all_reps)

        # ── 점수 계산 ──
        geo_fn: str = self._cfg.get("geometric_scorer", "")
        score, rep_scores = 50, []
        _geo_key: str = ""

        if geo_fn == "squat_front":
            # 정면 촬영: DTW 대신 기하학적 스코어링 (1회 계산, 재사용)
            try:
                score, _geo_key = GeometricScorer.squat_front(kpts_np)
                for _ in new_reps:
                    rep_scores.append(score)
            except Exception:
                pass
        elif self._last_dist_matrix is not None and self._score_engine is not None:
            try:
                score, rep_scores = self._score_engine.update(self._last_dist_matrix, new_rep_matrices)
            except Exception:
                pass

        # ── 피드백 ──
        expert_seq = self._expert_cache.sequence
        expert_norm_kp = expert_seq[self._frame_idx % len(expert_seq)]
        joint_distances = self._last_dist_matrix[-1] if self._last_dist_matrix is not None else None
        feedback_result = self._feedback_engine.analyze(kpts_np, norm_kp, expert_norm_kp, joint_distances)

        if new_reps:
            self._feedback_policy.on_rep_complete(self._frame_idx, feedback_result)
        message = self._feedback_policy.update(self._frame_idx)

        # 정면 촬영: 이미 계산한 _geo_key 재사용 (2차 호출 제거)
        if geo_fn == "squat_front" and message in {"측정 중입니다.", "자세를 화면 중앙에 맞춰주세요.", ""}:
            message = GeometricScorer.geo_feedback_message(_geo_key) if _geo_key else message

        self._frame_idx += 1

        return {
            "score": score,
            "rep_count": len(all_reps),
            "rep_scores": rep_scores,
            "message": message,
            "body_part": str(feedback_result.get("body_part", "")),
            "severity": float(feedback_result.get("severity", 0.0)),
        }

    def reset(self) -> None:
        """세션 재시작 시 상태를 초기화한다."""
        self._normalizer.reset()
        self._norm_buffer.clear()
        self._last_dist_matrix = None
        self._known_reps = 0
        self._frame_idx = 0


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

        # 전처리 공유 리소스 (implemented=True 종목만 서버 시작 시 1회 로드)
        self._preprocessing_shared: Dict[str, Any] = {}
        for exercise, cfg in EXERCISES.items():
            if not cfg.get("implemented", False):
                continue
            try:
                expert_cache = ExpertPoseCache(
                    video_path=cfg["video_path"],
                    target_fps=cfg["target_fps"],
                    normalizer_type=cfg["normalizer_type"],
                    norm_buffer_size=cfg["norm_buffer_size"],
                )
                expert_cache.build()
                comparator = DTWComparator(cfg["keypoints_used"]) if _DTW_AVAILABLE else None
                feedback_engine = FeedbackEngine(exercise, cfg["view"])
                self._preprocessing_shared[exercise] = {
                    "cfg": cfg,
                    "expert_cache": expert_cache,
                    "comparator": comparator,
                    "feedback_engine": feedback_engine,
                }
                print(f"[Pipeline] 전처리 파이프라인 로드 완료: {exercise}")
            except Exception as exc:
                print(f"[Pipeline] 전처리 파이프라인 로드 실패 ({exercise}): {exc}")

    def make_preprocessing_session(self, exercise_type: str) -> Optional[PreprocessingSession]:
        """exercise_type에 맞는 PreprocessingSession을 생성한다. 미구현 종목은 None 반환."""
        shared = self._preprocessing_shared.get(exercise_type)
        if shared is None:
            return None
        return PreprocessingSession(
            cfg=shared["cfg"],
            comparator=shared["comparator"],
            expert_cache=shared["expert_cache"],
            feedback_engine=shared["feedback_engine"],
        )

    def process_keypoints(
        self,
        payload: List[List[float]],
        frame_id: str,
        session_tracker: ExerciseSessionTracker,
        preprocessing_session: Optional[PreprocessingSession] = None,
    ) -> Dict[str, Any]:
        start_t = time.perf_counter()
        error = self._validate_keypoints(payload)
        if error:
            return {"status": "error", "message": error, "frame_id": frame_id}

        if self._backend == "optimization":
            return self._process_optimization(payload, frame_id, session_tracker, start_t)
        return self._process_lifter(payload, frame_id, session_tracker, start_t, preprocessing_session)

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
        preprocessing_session: Optional[PreprocessingSession] = None,
    ) -> Dict[str, Any]:
        import numpy as _np
        kpts_np = _np.array(payload, dtype=_np.float32)
        if kpts_np.shape[-1] > 3:
            kpts_np = kpts_np[..., :3]
        kpts_gpu = torch.from_numpy(kpts_np).unsqueeze(0).to(self.device)

        raw_out = self.model(kpts_gpu).squeeze(0)
        if self.device.type != "cpu":
            raw_out = raw_out.cpu()
        output = raw_out.numpy()
        global_orient_raw = output[:3]
        body_pose_raw = output[3:66]

        smoothed = self.retargeter.smooth_all(
            body_pose=body_pose_raw,
            global_orient=global_orient_raw,
            t=time.perf_counter(),
        )
        global_orient = smoothed["global_orient"].tolist()
        body_pose = smoothed["body_pose"].tolist()
        fatigue_state = self.analyzer.analyze(kpts_np)
        high_fatigue = [k for k, v in fatigue_state.items() if v == "high"]
        mid_fatigue = [k for k, v in fatigue_state.items() if v in {"mid", "med"}]
        if high_fatigue:
            fatigue_summary = f"주의: {', '.join(high_fatigue)}"
        elif mid_fatigue:
            fatigue_summary = f"보통: {', '.join(mid_fatigue)}"
        else:
            fatigue_summary = "양호"

        # 실제 DTW 파이프라인 (스쿼트) 또는 stub
        if preprocessing_session is not None:
            prep = preprocessing_session.process(kpts_np)
            pose_score = prep["score"]
            feedback_block = {
                "score": pose_score,
                "label": prep["message"],
                "message": prep["message"],
                "body_part": prep["body_part"],
                "severity": prep["severity"],
                "rep_count": prep["rep_count"],
                "rep_scores": prep["rep_scores"],
                "muscle_fatigue": fatigue_state,
            }
        else:
            pose_score = min(100, max(0, 100 - len(high_fatigue) * 15 - len(mid_fatigue) * 5))
            feedback_block = {
                "score": pose_score,
                "label": fatigue_summary,
                "message": fatigue_summary,
                "rep_count": 0,
                "rep_scores": [],
                "muscle_fatigue": fatigue_state,
            }

        session_tracker.record_frame(pose_score, feedback_block["label"])
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
            "feedback": feedback_block,
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


class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/viewer/"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
        return response


app.add_middleware(NoCacheMiddleware)

_viewer_dir = Path(__file__).resolve().parents[1] / "s05_frontend"
if _viewer_dir.exists():
    app.mount("/viewer", StaticFiles(directory=str(_viewer_dir), html=True), name="viewer_2d")

_react_dist_dir = Path(__file__).resolve().parents[2] / "dist"
if _react_dist_dir.exists():
    app.mount("/app", StaticFiles(directory=str(_react_dist_dir), html=True), name="react_app")


@app.get("/app")
async def redirect_app():
    return RedirectResponse(url="/app/", status_code=301)


@app.get("/viewer")
async def redirect_viewer():
    return RedirectResponse(url="/viewer/", status_code=301)


@app.get("/viewer/viewer.js")
async def serve_viewer_js():
    path = _viewer_dir / "viewer.js"
    content = path.read_bytes()
    return Response(content=content, media_type="application/javascript",
                    headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@app.get("/")
async def root():
    if _viewer_dir.exists() and (_viewer_dir / "index.html").exists():
        return FileResponse(str(_viewer_dir / "index.html"))
    return {
        "service": "VR Pose Estimation Server",
        "websocket": "/ws/pose",
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


@app.get("/api/expert-smplx")
async def get_expert_smplx():
    """Pre-lift expert 2D keypoints to SMPL-X params via PoseLifterNet.
    Result is cached after first call. Used by Unity ExpertAvatarController.
    """
    if getattr(app.state, "expert_smplx_cache", None) is not None:
        cached = app.state.expert_smplx_cache
        return {"status": "ok", "total_frames": len(cached), "frames": cached}

    project_root = Path(__file__).resolve().parents[2]
    candidates = [project_root / "squat_left_1_keypoints.json"]
    candidates.extend(sorted(project_root.glob("*_keypoints.json")))

    for path in candidates:
        if not path.exists():
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            pipeline: FastPosePipeline = app.state.pose_pipeline
            if pipeline.model is None:
                return {"status": "error", "message": "Lifter model not available (optimization backend active)."}

            frames = []
            for frame_data in raw:
                kp_list = frame_data.get("keypoints") if isinstance(frame_data, dict) else frame_data
                if not isinstance(kp_list, list) or len(kp_list) != 17:
                    continue
                kpts = torch.tensor(kp_list, dtype=torch.float32, device=pipeline.device)
                kpts = kpts[..., :3].unsqueeze(0)
                with torch.no_grad():
                    out = pipeline.model(kpts).squeeze(0).cpu().numpy()
                frames.append({
                    "global_orient": out[:3].tolist(),
                    "body_pose": out[3:66].tolist(),
                })

            app.state.expert_smplx_cache = frames
            return {"status": "ok", "total_frames": len(frames), "frames": frames, "source": path.name}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    return {"status": "error", "message": "No expert keypoints JSON found in project root."}


@app.get("/api/expert-keypoints")
async def get_expert_keypoints():
    """서버 시작 시 캐시된 전문가 원본 2D keypoints 시퀀스를 반환한다.
    React 앱 RenderSlot에서 강사 스켈레톤 루프 재생에 사용.
    shape: (N, 17, 3) — [y, x, confidence], normalized 0-1.
    """
    pipeline: FastPosePipeline = app.state.pose_pipeline
    shared = pipeline._preprocessing_shared.get("squat")
    if shared is None:
        return {"status": "error", "message": "expert keypoints not loaded (squat not implemented)"}
    raw = shared["expert_cache"].raw_sequence
    return {
        "status": "ok",
        "total_frames": int(raw.shape[0]),
        "target_fps": int(shared["cfg"]["target_fps"]),
        "frames": raw.tolist(),
    }


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
        if not self.active_connections:
            return
        payload = json.dumps(message)
        results = await asyncio.gather(
            *[c.send_text(payload) for c in list(self.active_connections)],
            return_exceptions=True,
        )
        for c, r in zip(list(self.active_connections), results):
            if isinstance(r, Exception):
                self.disconnect(c)


manager = ConnectionManager()


@app.websocket("/ws/pose")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    pipeline: FastPosePipeline = websocket.app.state.pose_pipeline
    session_tracker = ExerciseSessionTracker(websocket.app.state.exercise_repository)
    preprocessing_session: Optional[PreprocessingSession] = pipeline.make_preprocessing_session("squat")
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
                    preprocessing_session,
                )
                # React 앱(뷰어)도 포즈 수신이 필요하므로 broadcast 유지
                await manager.broadcast_json(response)
                continue
            elif data_type == "session_start":
                exercise_type = msg.get("exercise_type", "squat")
                preprocessing_session = pipeline.make_preprocessing_session(exercise_type)
                response = pipeline.start_session(
                    session_tracker,
                    user_id=msg.get("user_id", "anonymous"),
                    exercise_type=exercise_type,
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
