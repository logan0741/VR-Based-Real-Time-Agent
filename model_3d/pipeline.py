"""Frame-level 3D pose analysis pipeline shared by the server and CLI runner."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from model_3d.analyzer import analyze_squat
from model_3d.config import resolve_workspace_path
from model_3d.diagnostics import DiagnosticsRecorder
from model_3d.fitter import BasePoseFitter, build_pose_fitter
from model_3d.lifter_model import PoseLifterFitter
from model_3d.schemas import COCO_17_NAMES, FitResult, SquatFeedback


class PosePipeline:
    """Run one full frame through fitting, feedback, and diagnostics."""

    def __init__(
        self,
        fitter: Optional[BasePoseFitter] = None,
        diagnostics: Optional[DiagnosticsRecorder] = None,
    ) -> None:
        self.fitter = fitter or build_pose_fitter()
        self.diagnostics = diagnostics or DiagnosticsRecorder.from_env()

    @property
    def backend(self) -> str:
        return getattr(self.fitter, "backend", "unknown")

    def process_keypoints(self, payload: Any, frame_id: Optional[Any] = None) -> Dict[str, Any]:
        model_start = time.perf_counter()
        result = self.fitter.forward(payload)
        feedback = analyze_squat(result.joints_3d)
        model_latency_ms = (time.perf_counter() - model_start) * 1000.0

        response = fit_result_to_json(result, feedback)
        pipeline_latency_ms = (time.perf_counter() - model_start) * 1000.0
        artifacts = self.diagnostics.record(
            result=result,
            feedback=feedback,
            frame_id=frame_id,
            model_latency_ms=model_latency_ms,
            pipeline_latency_ms=pipeline_latency_ms,
        )
        total_latency_ms = (time.perf_counter() - model_start) * 1000.0

        if frame_id is not None:
            response["frame_id"] = frame_id
        response["processed_at"] = time.time()
        response["performance"] = {
            "model_latency_ms": model_latency_ms,
            "pipeline_latency_ms": total_latency_ms,
            "fps_estimate": 1000.0 / model_latency_ms if model_latency_ms > 0 else 0.0,
        }
        response["diagnostics"] = {
            "enabled": self.diagnostics.enabled,
            "session_dir": str(self.diagnostics.session_dir),
            "artifacts": artifacts,
        }
        return response

    def process_image(self, payload: Any, frame_id: Optional[Any] = None) -> Dict[str, Any]:
        # Phase 2 hook: decode base64 image here, then call a regression fitter
        # such as OSX/PIXIE through the same BasePoseFitter API.
        response = {
            "status": "not_implemented",
            "data_type": "image",
            "message": (
                "Image payload branch is reserved for Phase 2 single-pass "
                "SMPL-X regression backends."
            ),
            "processed_at": time.time(),
        }
        if frame_id is not None:
            response["frame_id"] = frame_id
        return response


def build_pose_pipeline() -> PosePipeline:
    lifter_checkpoint = os.getenv("LIFTER_CHECKPOINT")
    if lifter_checkpoint:
        return PosePipeline(fitter=PoseLifterFitter(resolve_workspace_path(Path(lifter_checkpoint))))
    return PosePipeline()


def fit_result_to_json(result: FitResult, feedback: SquatFeedback) -> Dict[str, Any]:
    payload = {
        "backend": result.backend,
        "reprojection_loss": result.reprojection_loss,
        "joint_names": COCO_17_NAMES,
        "joints_3d": result.joints_3d.tolist(),
        "projected_joints_2d": result.projected_joints_2d.tolist(),
        "target_joints_2d": result.target_joints_2d.tolist(),
        "confidence": result.confidence.tolist(),
        "global_orient": result.global_orient.tolist(),
        "body_pose": result.body_pose.tolist(),
        "loss_history": result.loss_history,
    }
    if result.vertices is not None:
        payload["vertices"] = result.vertices.tolist()

    return {
        "status": "ok",
        "data_type": "keypoints",
        "fit": payload,
        "feedback": {
            "label": feedback.label,
            "knee_angle_deg": feedback.knee_angle_deg,
            "left_knee_angle_deg": feedback.left_knee_angle_deg,
            "right_knee_angle_deg": feedback.right_knee_angle_deg,
        },
    }
