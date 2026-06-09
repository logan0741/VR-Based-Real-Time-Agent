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

from .config import env_bool
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
    print("[Pipeline] dtaidistance 亦껋꼶梨룩땻類잆럦???DTW ??????????繹먮봿?? pip install dtaidistance==2.3.12")


EXERCISE_ALIASES = {
    "pull_up": "pullup",
}


def normalize_exercise_type(exercise_type: Any) -> str:
    raw = str(exercise_type or "squat")
    return EXERCISE_ALIASES.get(raw, raw)


def exercise_file_candidates(exercise_type: str) -> List[str]:
    canonical = normalize_exercise_type(exercise_type)
    names = [str(exercise_type or "squat"), canonical]
    if canonical == "pullup":
        names.append("pull_up")
    seen = set()
    return [name for name in names if not (name in seen or seen.add(name))]


MUSCLE_LABELS = {
    "chest": "\uac00\uc2b4",
    "abs": "\ubcf5\uadfc",
    "lower_back": "\ud558\ubd80 \ud5c8\ub9ac",
    "left_quad": "\uc88c \ub300\ud1f4",
    "right_quad": "\uc6b0 \ub300\ud1f4",
    "left_hamstring": "\uc88c \ud584\uc2a4\ud2b8\ub9c1",
    "right_hamstring": "\uc6b0 \ud584\uc2a4\ud2b8\ub9c1",
    "left_glute": "\uc88c \ub454\uadfc",
    "right_glute": "\uc6b0 \ub454\uadfc",
}


def format_fatigue_summary(prefix: str, muscles: List[str]) -> str:
    labels = [MUSCLE_LABELS.get(muscle, muscle) for muscle in muscles]
    return f"{prefix}: {', '.join(labels)}"


def is_pending_feedback(feedback: Dict[str, Any]) -> bool:
    message = str(feedback.get("message", ""))
    body_part = str(feedback.get("body_part", ""))
    return body_part in {"", "pending"} or message in {"", "measuring", "\uce21\uc815 \uc911\uc785\ub2c8\ub2e4."}



class PreprocessingSession:
    """??⑤슡?숂솻??熬곣뫗??????逾?熬곣뫁逾????⑤객臾?(PoseNormalizer, RepDetector, ScoreEngine, FeedbackPolicy)."""

    def __init__(
        self,
        cfg: dict,
        comparator: "DTWComparator",
        expert_cache: ExpertPoseCache,
        feedback_engine: FeedbackEngine,
    ) -> None:
        self._cfg = dict(cfg)
        if os.environ.get("DTW_INTERVAL_OVERRIDE"):
            self._cfg["dtw_interval"] = max(1, int(os.environ["DTW_INTERVAL_OVERRIDE"]))
        if os.environ.get("DTW_N_FRAMES_OVERRIDE"):
            self._cfg["n_frames"] = max(2, int(os.environ["DTW_N_FRAMES_OVERRIDE"]))
        if os.environ.get("SCORE_MAX_DISTANCE_OVERRIDE"):
            self._cfg["max_distance"] = max(0.001, float(os.environ["SCORE_MAX_DISTANCE_OVERRIDE"]))
        self._comparator = comparator
        self._expert_cache = expert_cache
        self._feedback_engine = feedback_engine
        self._expert_stride = max(1, int(os.environ.get("DTW_EXPERT_STRIDE", "1")))
        self._dtw_expert_sequence = expert_cache.sequence[::self._expert_stride]

        self._normalizer = PoseNormalizer(self._cfg["normalizer_type"], self._cfg["norm_buffer_size"])
        self._rep_detector = RepDetector(
            self._cfg["rep_detector_type"], self._cfg["normalizer_type"],
            self._cfg["rep_slope_window"], self._cfg["min_rep_frames"],
        )
        self._score_engine: Optional["ScoreEngine"] = (
            ScoreEngine(self._cfg["weights"], self._cfg["max_distance"], self._cfg["n_frames"])
            if _DTW_AVAILABLE else None
        )
        self._feedback_policy = FeedbackPolicy(hold_frames=self._cfg["target_fps"] * 3)

        self._norm_buffer: List[Any] = []
        self._last_dist_matrix: Optional[Any] = None
        self._last_result: Dict[str, Any] = {
            "score": 50,
            "rep_count": 0,
            "rep_scores": [],
            "message": "measuring",
            "body_part": "",
            "severity": 0.0,
        }
        self._run_realtime_dtw = env_bool("PREPROCESSING_REALTIME_DTW", True)
        self._feedback_interval_frames = max(1, int(os.environ.get("FEEDBACK_INTERVAL_FRAMES", "1")))
        self._known_reps: int = 0
        self._frame_idx: int = 0

    def process(self, kpts_np: Any) -> Dict[str, Any]:
        """1?熬곣뫁?????㉱????⑥щ턄??⑤벡夷?????얍ㅇ???낅빢鸚??怨뺢덧?꾩룄?????ｌ뫒亦???겶??꾩룇瑗???類ｋ펲."""
        import numpy as _np

        try:
            norm_kp = self._normalizer.normalize(kpts_np)
        except ValueError:
            return {"score": 50, "rep_count": 0, "rep_scores": [], "message": "????????븐뻼??繞벿살탳???嶺뚮씮??議쏀떊?源껋돪??", "body_part": "", "severity": 0.0}

        self._norm_buffer.append(norm_kp)

        # Rep ?띠룆흮?
        all_reps = self._rep_detector.update(norm_kp)
        new_reps = all_reps[self._known_reps:]
        new_rep_matrices: List[Any] = []

        if _DTW_AVAILABLE and self._score_engine is not None:
            for start, end in new_reps:
                if end <= len(self._norm_buffer):
                    try:
                        rep_seq = _np.stack(self._norm_buffer[start:end])
                        rep_dm = self._comparator.compare(rep_seq, self._dtw_expert_sequence)
                        new_rep_matrices.append(rep_dm)
                    except Exception:
                        pass

            # DTW ??ｌ뫒亦?(dtw_interval嶺뚮씭???
            if new_rep_matrices and not self._run_realtime_dtw:
                self._last_dist_matrix = new_rep_matrices[-1]

            if (
                self._run_realtime_dtw
                and self._frame_idx % self._cfg["dtw_interval"] == 0
                and len(self._norm_buffer) >= 2
            ):
                try:
                    window = _np.stack(self._norm_buffer[-self._cfg["n_frames"]:])
                    self._last_dist_matrix = self._comparator.compare(window, self._dtw_expert_sequence)
                except Exception:
                    pass

        self._known_reps = len(all_reps)

        # ???? ???????ｌ뫒亦?????
        score, rep_scores = 50, []

        if self._last_dist_matrix is not None and self._score_engine is not None:
            try:
                score, rep_scores = self._score_engine.update(self._last_dist_matrix, new_rep_matrices)
            except Exception:
                pass

        # ???? ??怨뺢덧??????
        if (
            not new_reps
            and self._frame_idx % self._feedback_interval_frames != 0
            and self._last_result is not None
        ):
            result = dict(self._last_result)
            result["rep_count"] = len(all_reps)
            result["rep_scores"] = rep_scores
            self._frame_idx += 1
            return result

        expert_seq = self._expert_cache.sequence
        expert_norm_kp = expert_seq[self._frame_idx % len(expert_seq)]
        joint_distances = self._last_dist_matrix[-1] if self._last_dist_matrix is not None else None
        feedback_result = self._feedback_engine.analyze(kpts_np, norm_kp, expert_norm_kp, joint_distances)

        if new_reps:
            self._feedback_policy.on_rep_complete(self._frame_idx, feedback_result)

        policy_message = self._feedback_policy.update(self._frame_idx)
        live_message = str(feedback_result.get("message", policy_message))
        body_part = str(feedback_result.get("body_part", ""))
        message = live_message if body_part not in {"", "pending"} else policy_message

        self._frame_idx += 1

        result = {
            "score": score,
            "rep_count": len(all_reps),
            "rep_scores": rep_scores,
            "message": message,
            "body_part": body_part,
            "severity": float(feedback_result.get("severity", 0.0)),
        }
        self._last_result = result
        return result

    def reset(self) -> None:
        """?筌뤾쑬???????????⑤객臾???貫?껆뵳??됀???"""
        self._normalizer.reset()
        self._norm_buffer.clear()
        self._last_dist_matrix = None
        self._last_result = {
            "score": 50,
            "rep_count": 0,
            "rep_scores": [],
            "message": "measuring",
            "body_part": "",
            "severity": 0.0,
        }
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
        self._realtime_2d_only = env_bool("REALTIME_2D_ONLY", True)

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

        # ?熬곣뫗?????ㅻ쾴?? ?洹먮봾爰??(implemented=True ??リ턁??듭춹???類ㅼ뮅 ??戮곗굚 ??1???β돦裕녻キ?
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
                print(f"[Pipeline] ?熬곣뫗??????逾?熬곣뫁逾???β돦裕녻キ??熬곣뫁?? {exercise}")
            except Exception as exc:
                print(f"[Pipeline] ?熬곣뫗??????逾?熬곣뫁逾???β돦裕녻キ????덉넮 ({exercise}): {exc}")

    def make_preprocessing_session(self, exercise_type: str) -> Optional[PreprocessingSession]:
        """exercise_type??嶺뚮씮???PreprocessingSession????諛댁뎽??類ｋ펲. 亦껋꼶??????リ턁??? None ?꾩룇瑗??"""
        shared = self._preprocessing_shared.get(normalize_exercise_type(exercise_type))
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
            fatigue_summary = format_fatigue_summary("\uc8fc\uc758", high_fatigue)
        elif mid_fatigue:
            fatigue_summary = format_fatigue_summary("\ubcf4\ud1b5", mid_fatigue)
        else:
            fatigue_summary = "\uc591\ud638"

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
        if self._realtime_2d_only:
            return self._process_2d_only(
                kpts_np,
                payload,
                frame_id,
                session_tracker,
                start_t,
                preprocessing_session,
            )
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
            fatigue_summary = format_fatigue_summary("\uc8fc\uc758", high_fatigue)
        elif mid_fatigue:
            fatigue_summary = format_fatigue_summary("\ubcf4\ud1b5", mid_fatigue)
        else:
            fatigue_summary = "\uc591\ud638"

        # ???깆젷 DTW ???逾?熬곣뫁逾??(???깆굯?? ???裕?stub
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
            if is_pending_feedback(feedback_block):
                pose_score = min(100, max(0, 100 - len(high_fatigue) * 15 - len(mid_fatigue) * 5))
                feedback_block.update({
                    "score": pose_score,
                    "label": fatigue_summary,
                    "message": fatigue_summary,
                    "body_part": "ok",
                    "severity": 0.0,
                })
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

    def _process_2d_only(
        self,
        kpts_np: Any,
        payload: List[List[float]],
        frame_id: str,
        session_tracker: ExerciseSessionTracker,
        start_t: float,
        preprocessing_session: Optional[PreprocessingSession] = None,
    ) -> Dict[str, Any]:
        fatigue_state = self.analyzer.analyze(kpts_np)
        high_fatigue = [k for k, v in fatigue_state.items() if v == "high"]
        mid_fatigue = [k for k, v in fatigue_state.items() if v in {"mid", "med"}]
        if high_fatigue:
            fatigue_summary = format_fatigue_summary("\uc8fc\uc758", high_fatigue)
        elif mid_fatigue:
            fatigue_summary = format_fatigue_summary("\ubcf4\ud1b5", mid_fatigue)
        else:
            fatigue_summary = "\uc591\ud638"

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
            if is_pending_feedback(feedback_block):
                pose_score = min(100, max(0, 100 - len(high_fatigue) * 15 - len(mid_fatigue) * 5))
                feedback_block.update({
                    "score": pose_score,
                    "label": fatigue_summary,
                    "message": fatigue_summary,
                    "body_part": "ok",
                    "severity": 0.0,
                })
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
            "data_type": "feedback",
            "frame_id": frame_id,
            "session_id": session_id,
            "keypoints_2d": payload,
            "feedback": feedback_block,
            "debug": {
                "backend": "2d_only",
                "inference_ms": round(dur_ms, 2),
                "smoothing_enabled": False,
                "smoothing_frame": 0,
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
        exercise_type = normalize_exercise_type(exercise_type)
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
        if request.url.path.startswith("/viewer/") or request.url.path.startswith("/app/"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
        if request.url.path.startswith("/viewer/"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' https://cdn.jsdelivr.net 'unsafe-eval' 'wasm-unsafe-eval'; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com; "
                "img-src 'self' data: blob:; "
                "media-src 'self' blob:; "
                "connect-src 'self' ws: wss: https://cdn.jsdelivr.net https://tfhub.dev https://storage.googleapis.com https://www.kaggle.com https://kaggle.com; "
                "worker-src 'self' blob:;"
            )
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
async def root(request: Request):
    host = request.headers.get("host", "").split(":", 1)[0].lower()
    if host.startswith("viewer."):
        return RedirectResponse(url="/viewer/", status_code=302)
    if host.startswith("app.") or host.startswith("pt."):
        return RedirectResponse(url="/app/", status_code=302)
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
async def get_expert_smplx(exercise: str = "squat"):
    """Pre-lift expert 2D keypoints to SMPL-X params via PoseLifterNet.
    Result is cached after first call. Used by Unity ExpertAvatarController.
    """
    if getattr(app.state, "expert_smplx_cache", None) is not None:
        cached = app.state.expert_smplx_cache
        return {"status": "ok", "total_frames": len(cached), "frames": cached}

    pipeline: FastPosePipeline = app.state.pose_pipeline
    if pipeline.model is None:
        return {"status": "error", "message": "Lifter model not available (optimization backend active)."}

    # 1??戮곕쭊: ??類ㅼ뮅 ??戮곗굚 ???β돦裕녻キ??ExpertPoseCache.raw_sequence ????(?筌먐쇰꼪??MLP ???놁졑 ?筌먦끇六?
    shared = pipeline._preprocessing_shared.get(normalize_exercise_type(exercise))
    if shared is not None:
        try:
            import numpy as _np
            raw_seq = shared["expert_cache"].raw_sequence  # (N, 17, 3), float32
            frames = []
            with torch.no_grad():
                for kp in raw_seq:
                    kpts = torch.tensor(kp, dtype=torch.float32, device=pipeline.device).unsqueeze(0)
                    out = pipeline.model(kpts).squeeze(0).cpu().numpy()
                    frames.append({
                        "global_orient": out[:3].tolist(),
                        "body_pose": out[3:66].tolist(),
                    })
            app.state.expert_smplx_cache = frames
            return {"status": "ok", "total_frames": len(frames), "frames": frames, "source": "npy_raw_sequence"}
        except Exception as exc:
            print(f"[expert-smplx] raw_sequence 嶺뚳퐣瑗?????덉넮: {exc}")

    # 2??戮곕쭊: JSON ???逾??????(fallback)
    project_root = Path(__file__).resolve().parents[2]
    for path in sorted(project_root.glob("*_keypoints.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
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

    return {"status": "error", "message": "No expert keypoints source available."}


@app.get("/api/expert-keypoints")
async def get_expert_keypoints():
    """??類ㅼ뮅 ??戮곗굚 ??嶺?흮????熬곣뱭?泥? ???沅?2D keypoints ???궰???? ?꾩룇瑗???類ｋ펲.
    React ??RenderSlot??????띠룆踰→쾮????노젵???낃퐨 ?猷먮쳜????繹??????
    shape: (N, 17, 3) ??[y, x, confidence], normalized 0-1.
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
async def get_expert_poses(exercise: str = "squat"):
    """Return expert 2D keypoints for the given exercise.
    exercise: squat | hammer_curl | lateral_raise | pull_up
    """
    project_root = Path(__file__).resolve().parents[2]
    # Primary: {exercise}_expert_keypoints.json
    candidates = [
        *(project_root / f"{name}_expert_keypoints.json" for name in exercise_file_candidates(exercise)),
        project_root / "squat_expert_keypoints.json",  # fallback
    ]

    for path in candidates:
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                # data may be a list of frames OR {frames: [...]}
                if isinstance(data, list):
                    frames = data
                else:
                    frames = data.get("frames", data)
                return {
                    "status": "ok",
                    "exercise": exercise,
                    "filename": path.name,
                    "total_frames": len(frames),
                    "frames": frames,
                }
            except Exception as exc:
                return {"status": "error", "message": str(exc)}

    return {"status": "error", "message": f"No expert keypoints found for exercise: {exercise}"}


@app.get("/api/expert-pose3d")
async def get_expert_pose3d():
    """Return pre-computed MotionBERT-Lite 3D joint coordinates (COCO-17, meters scale).
    Run run_motionbert.py once to generate squat_expert_keypoints_3d_mb.json.
    Coordinate note: pt=(x,y,z) where y points DOWN ??negate y for Three.js Y-up.
    """
    if getattr(app.state, "expert_pose3d_cache", None) is not None:
        cached = app.state.expert_pose3d_cache
        return {"status": "ok", "total_frames": len(cached), "frames": cached, "source": "motionbert-lite"}

    project_root = Path(__file__).resolve().parents[2]
    mb_path = project_root / "squat_expert_keypoints_3d_mb.json"
    if not mb_path.exists():
        return {"status": "error", "message": "squat_expert_keypoints_3d_mb.json not found ??run run_motionbert.py first"}

    with open(str(mb_path), "r") as f:
        data = json.load(f)

    frames = data["frames"]
    app.state.expert_pose3d_cache = frames
    return {"status": "ok", "total_frames": len(frames), "frames": frames, "source": "motionbert-lite"}


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.client_info: Dict[int, Dict[str, Any]] = {}
        self.latest_pose_message: Optional[Dict[str, Any]] = None
        self.total_keypoint_messages: int = 0
        self.total_broadcast_messages: int = 0
        self.last_keypoint_at: Optional[float] = None
        self.session_control_version: int = 0
        self.session_control: Dict[str, Any] = {
            "user_id": "anonymous",
            "exercise_type": "squat",
            "sets": 1,
            "reps_per_set": 8,
            "expert_started_at_ms": int(time.time() * 1000),
        }

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        client_id = id(websocket)
        self.client_info[client_id] = {
            "client_id": client_id,
            "connected_at": time.time(),
            "client": str(websocket.client) if websocket.client else "",
            "host": websocket.headers.get("host", ""),
            "origin": websocket.headers.get("origin", ""),
            "user_agent": websocket.headers.get("user-agent", ""),
            "last_message_type": "",
            "last_frame_id": "",
            "last_message_at": None,
            "keypoint_messages": 0,
            "config_messages": 0,
        }
        await websocket.send_text(json.dumps({
            "status": "ok",
            "data_type": "session_config",
            "control": self.current_session_control(),
        }))
        if self.latest_pose_message is not None:
            await websocket.send_text(json.dumps(self.latest_pose_message))

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        self.client_info.pop(id(websocket), None)

    async def broadcast_json(self, message: Dict[str, Any]):
        if not self.active_connections:
            return
        payload = json.dumps(message)
        self.total_broadcast_messages += 1
        results = await asyncio.gather(
            *[c.send_text(payload) for c in list(self.active_connections)],
            return_exceptions=True,
        )
        for c, r in zip(list(self.active_connections), results):
            if isinstance(r, Exception):
                self.disconnect(c)

    def record_incoming(self, websocket: WebSocket, data_type: str, frame_id: str) -> None:
        now = time.time()
        info = self.client_info.get(id(websocket))
        if info is not None:
            info["last_message_type"] = data_type
            info["last_frame_id"] = frame_id
            info["last_message_at"] = now
            if data_type == "keypoints":
                info["keypoint_messages"] += 1
            elif data_type == "session_config":
                info["config_messages"] += 1
        if data_type == "keypoints":
            self.total_keypoint_messages += 1
            self.last_keypoint_at = now

    def snapshot(self) -> Dict[str, Any]:
        now = time.time()
        clients = []
        for info in self.client_info.values():
            item = dict(info)
            item["connected_age_sec"] = round(now - item["connected_at"], 2)
            item["last_message_age_sec"] = (
                round(now - item["last_message_at"], 2)
                if item["last_message_at"] is not None else None
            )
            clients.append(item)
        return {
            "active_connections": len(self.active_connections),
            "total_keypoint_messages": self.total_keypoint_messages,
            "total_broadcast_messages": self.total_broadcast_messages,
            "last_keypoint_age_sec": (
                round(now - self.last_keypoint_at, 2)
                if self.last_keypoint_at is not None else None
            ),
            "latest_pose_frame_id": (
                self.latest_pose_message.get("frame_id")
                if self.latest_pose_message else None
            ),
            "session_control": {
                **self.current_session_control(),
            },
            "clients": sorted(clients, key=lambda c: c["connected_at"]),
        }

    def current_session_control(self) -> Dict[str, Any]:
        started_at = int(self.session_control.get("expert_started_at_ms") or int(time.time() * 1000))
        return {
            "version": self.session_control_version,
            **self.session_control,
            "expert_phase_ms": max(0, int(time.time() * 1000) - started_at),
        }

    def exercise_progress(self, rep_count: int) -> Dict[str, int | bool]:
        sets = max(1, int(self.session_control.get("sets", 1) or 1))
        reps_per_set = max(1, int(self.session_control.get("reps_per_set", 8) or 8))
        total_target_reps = sets * reps_per_set
        total_reps = max(0, int(rep_count or 0))
        completed = total_reps >= total_target_reps

        if completed:
            current_set = sets
            rep_in_set = reps_per_set
        else:
            current_set = min(sets, (total_reps // reps_per_set) + 1)
            rep_in_set = total_reps % reps_per_set

        return {
            "current_set": current_set,
            "total_sets": sets,
            "rep_in_set": rep_in_set,
            "reps_per_set": reps_per_set,
            "total_reps": total_reps,
            "total_target_reps": total_target_reps,
            "completed": completed,
        }

    def attach_progress(self, message: Dict[str, Any]) -> Dict[str, Any]:
        feedback = message.get("feedback")
        if isinstance(feedback, dict):
            progress = self.exercise_progress(int(feedback.get("rep_count", 0) or 0))
            feedback.update(progress)
            message["progress"] = progress
        return message

    def start_session_control(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.session_control_version += 1
        exercise_type = normalize_exercise_type(payload.get("exercise_type", "squat"))
        self.session_control = {
            "user_id": payload.get("user_id", "anonymous"),
            "exercise_type": exercise_type,
            "sets": int(payload.get("sets", 1) or 1),
            "reps_per_set": int(payload.get("reps_per_set", 8) or 8),
            "expert_started_at_ms": int(time.time() * 1000),
        }
        return self.current_session_control()


manager = ConnectionManager()


@app.get("/api/debug/ws")
async def debug_ws():
    return {"status": "ok", **manager.snapshot()}


@app.get("/api/session-control")
async def get_session_control():
    return {
        "status": "ok",
        "control": manager.current_session_control(),
    }


@app.websocket("/ws/pose")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    pipeline: FastPosePipeline = websocket.app.state.pose_pipeline
    session_tracker = ExerciseSessionTracker(websocket.app.state.exercise_repository)
    preprocessing_session: Optional[PreprocessingSession] = (
        pipeline.make_preprocessing_session("squat")
        if env_bool("PREPROCESSING_ENABLED", True)
        else None
    )
    loop = asyncio.get_running_loop()
    latest_keypoints_msg: Optional[Dict[str, Any]] = None
    processor_task: Optional[asyncio.Task] = None
    local_session_control_version = -1

    def sync_session_control() -> None:
        nonlocal preprocessing_session, local_session_control_version
        if local_session_control_version == manager.session_control_version:
            return
        control = manager.session_control
        exercise_type = control.get("exercise_type", "squat")
        pipeline.reset_smoothing()
        session_tracker.start(
            user_id=control.get("user_id", "anonymous"),
            exercise_type=exercise_type,
        )
        preprocessing_session = (
            pipeline.make_preprocessing_session(exercise_type)
            if env_bool("PREPROCESSING_ENABLED", True)
            else None
        )
        local_session_control_version = manager.session_control_version

    async def process_latest_keypoints() -> None:
        nonlocal latest_keypoints_msg
        while latest_keypoints_msg is not None:
            current_msg = latest_keypoints_msg
            latest_keypoints_msg = None
            sync_session_control()
            response = await loop.run_in_executor(
                None,
                pipeline.process_keypoints,
                current_msg.get("payload"),
                current_msg.get("frame_id", "unknown"),
                session_tracker,
                preprocessing_session,
            )
            response.setdefault("debug", {})
            response["debug"]["dropped_to_latest"] = True
            manager.attach_progress(response)
            await manager.broadcast_json(response)

    try:
        while True:
            raw_msg = await websocket.receive_text()
            msg = json.loads(raw_msg)
            data_type = msg.get("data_type")
            frame_id = msg.get("frame_id", "unknown")
            manager.record_incoming(websocket, str(data_type), str(frame_id))

            if data_type == "keypoints":
                payload = msg.get("payload")
                if payload:
                    pose_message = {
                        "status": "ok",
                        "data_type": "pose",
                        "frame_id": frame_id,
                        "keypoints_2d": payload,
                        "debug": {
                            "relay_only": True,
                            "client_timestamp_ms": msg.get("client_timestamp_ms"),
                        },
                    }
                    manager.latest_pose_message = pose_message
                    await manager.broadcast_json(pose_message)
                latest_keypoints_msg = msg
                if processor_task is None or processor_task.done():
                    processor_task = asyncio.create_task(process_latest_keypoints())
                continue
                response = await loop.run_in_executor(
                    None,
                    pipeline.process_keypoints,
                    msg.get("payload"),
                    frame_id,
                    session_tracker,
                    preprocessing_session,
                )
                # React ?????ｅ젆?????藥???琉용뼁???熬곣뫗??????broadcast ???
                await manager.broadcast_json(response)
                continue
            elif data_type == "session_start":
                exercise_type = msg.get("exercise_type", "squat")
                control = manager.start_session_control(msg)
                preprocessing_session = (
                    pipeline.make_preprocessing_session(control["exercise_type"])
                    if env_bool("PREPROCESSING_ENABLED", True)
                    else None
                )
                response = pipeline.start_session(
                    session_tracker,
                    user_id=msg.get("user_id", "anonymous"),
                    exercise_type=control["exercise_type"],
                )
                response["control"] = control
            elif data_type == "session_config":
                control = manager.start_session_control(msg)
                response = {
                    "status": "ok",
                    "data_type": "session_config",
                    "control": control,
                }
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
        "final.s02_backend.server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
