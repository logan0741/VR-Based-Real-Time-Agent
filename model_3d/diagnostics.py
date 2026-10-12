"""Automatic QA artifacts for preprocessing, fitting, and model performance."""

from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from model_3d.config import env_bool, package_root
from model_3d.schemas import COCO_SKELETON, FitResult, SquatFeedback


class DiagnosticsRecorder:
    """
    Save per-frame debug images and rolling performance graphs.

    Generated files are intentionally placed under artifacts/ so they stay out
    of source control via .gitignore.
    """

    def __init__(
        self,
        enabled: bool = True,
        output_root: Optional[str] = None,
        save_every_n: int = 1,
        graph_every_n: int = 1,
        graph_window: int = 200,
    ) -> None:
        self.enabled = enabled
        self.save_every_n = max(1, save_every_n)
        self.graph_every_n = max(1, graph_every_n)
        self.graph_window = max(10, graph_window)
        self.frame_index = 0
        self.metrics: List[Dict[str, Any]] = []

        base_dir = Path(output_root) if output_root else package_root() / "artifacts" / "pose_debug"
        session_name = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = base_dir / session_name
        self.frames_dir = self.session_dir / "frames"
        self.graphs_dir = self.session_dir / "graphs"
        self.metrics_path = self.session_dir / "metrics.jsonl"

        if self.enabled:
            self.frames_dir.mkdir(parents=True, exist_ok=True)
            self.graphs_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls) -> "DiagnosticsRecorder":
        return cls(
            enabled=env_bool("DIAGNOSTICS_ENABLED", True),
            output_root=os.getenv("DIAGNOSTICS_OUTPUT_DIR"),
            save_every_n=int(os.getenv("DIAGNOSTICS_SAVE_EVERY_N", "1")),
            graph_every_n=int(os.getenv("DIAGNOSTICS_GRAPH_EVERY_N", "1")),
            graph_window=int(os.getenv("DIAGNOSTICS_GRAPH_WINDOW", "200")),
        )

    def record(
        self,
        result: FitResult,
        feedback: SquatFeedback,
        frame_id: Optional[Any],
        model_latency_ms: float,
        pipeline_latency_ms: float,
    ) -> Dict[str, str]:
        if not self.enabled:
            return {}

        self.frame_index += 1
        frame_slug = self._frame_slug(frame_id)
        artifacts: Dict[str, str] = {}

        metric = {
            "frame_index": self.frame_index,
            "frame_id": frame_id,
            "backend": result.backend,
            "model_latency_ms": _finite(model_latency_ms),
            "pipeline_latency_ms": _finite(pipeline_latency_ms),
            "fps_estimate": _finite(1000.0 / model_latency_ms if model_latency_ms > 0 else 0.0),
            "reprojection_loss": _finite(result.reprojection_loss),
            "knee_angle_deg": _finite(feedback.knee_angle_deg),
            "left_knee_angle_deg": _finite(feedback.left_knee_angle_deg),
            "right_knee_angle_deg": _finite(feedback.right_knee_angle_deg),
            "feedback": feedback.label,
        }
        self._append_metric(metric)
        artifacts["metrics_jsonl"] = str(self.metrics_path)

        should_save_frame = (self.frame_index - 1) % self.save_every_n == 0
        if should_save_frame:
            artifacts["preprocessed_keypoints"] = str(
                self._save_preprocessed_keypoints(result, frame_slug)
            )
            artifacts["reprojection_check"] = str(
                self._save_reprojection_check(result, frame_slug)
            )
            artifacts["joints_3d_check"] = str(self._save_joints_3d(result, frame_slug))
            if result.vertices is not None:
                artifacts["smplx_mesh_preview"] = str(self._save_mesh_preview(result, frame_slug))
            if result.loss_history:
                artifacts["optimization_loss_graph"] = str(
                    self._save_loss_history(result.loss_history, frame_slug)
                )

        if self.frame_index % self.graph_every_n == 0 or should_save_frame:
            artifacts["performance_graph"] = str(self._save_performance_graph())

        return artifacts

    def _append_metric(self, metric: Dict[str, Any]) -> None:
        self.metrics.append(metric)
        if len(self.metrics) > self.graph_window:
            self.metrics = self.metrics[-self.graph_window :]

        with self.metrics_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(metric, ensure_ascii=False, allow_nan=False) + "\n")

    def _frame_slug(self, frame_id: Optional[Any]) -> str:
        if frame_id is None:
            return f"frame_{self.frame_index:06d}"
        safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(frame_id)).strip("_")
        return f"frame_{self.frame_index:06d}_{safe[:40]}"

    def _save_preprocessed_keypoints(self, result: FitResult, frame_slug: str) -> Path:
        path = self.frames_dir / f"{frame_slug}_preprocessed_keypoints.png"
        fig, ax = plt.subplots(figsize=(6.4, 4.8), dpi=120)
        ax.set_title("Preprocessed MoveNet/COCO 2D Keypoints")
        ax.set_facecolor("#101010")
        _plot_2d_skeleton(
            ax,
            result.target_joints_2d,
            result.confidence,
            point_color="#00e5ff",
            line_color="#00bcd4",
            label="target",
        )
        ax.set_xlim(0, 640)
        ax.set_ylim(480, 0)
        ax.set_xlabel("x pixel")
        ax.set_ylabel("y pixel")
        ax.legend(loc="upper right")
        fig.tight_layout()
        fig.savefig(path)
        plt.close(fig)
        return path

    def _save_reprojection_check(self, result: FitResult, frame_slug: str) -> Path:
        path = self.frames_dir / f"{frame_slug}_reprojection_check.png"
        fig, ax = plt.subplots(figsize=(6.4, 4.8), dpi=120)
        ax.set_title(f"Reprojection Check - loss={result.reprojection_loss:.2f}")
        ax.set_facecolor("#101010")
        _plot_2d_skeleton(
            ax,
            result.target_joints_2d,
            result.confidence,
            point_color="#00e5ff",
            line_color="#00bcd4",
            label="target",
        )
        _plot_2d_skeleton(
            ax,
            result.projected_joints_2d,
            np.ones(17, dtype=np.float32),
            point_color="#ff5252",
            line_color="#ff8a80",
            label="projected",
        )
        ax.set_xlim(0, 640)
        ax.set_ylim(480, 0)
        ax.set_xlabel("x pixel")
        ax.set_ylabel("y pixel")
        ax.legend(loc="upper right")
        fig.tight_layout()
        fig.savefig(path)
        plt.close(fig)
        return path

    def _save_joints_3d(self, result: FitResult, frame_slug: str) -> Path:
        path = self.frames_dir / f"{frame_slug}_joints_3d_check.png"
        fig = plt.figure(figsize=(6, 6), dpi=120)
        ax = fig.add_subplot(111, projection="3d")
        ax.set_title("Fitted COCO 17 Joints in 3D")
        joints = result.joints_3d
        ax.scatter(joints[:, 0], joints[:, 1], joints[:, 2], c="#2196f3", s=24)
        for start, end in COCO_SKELETON:
            xs = [joints[start, 0], joints[end, 0]]
            ys = [joints[start, 1], joints[end, 1]]
            zs = [joints[start, 2], joints[end, 2]]
            ax.plot(xs, ys, zs, c="#90caf9", linewidth=1.5)
        ax.set_xlabel("x")
        ax.set_ylabel("y")
        ax.set_zlabel("z")
        _set_equal_3d_axes(ax, joints)
        fig.tight_layout()
        fig.savefig(path)
        plt.close(fig)
        return path

    def _save_mesh_preview(self, result: FitResult, frame_slug: str) -> Path:
        path = self.frames_dir / f"{frame_slug}_smplx_mesh_preview.png"
        vertices = result.vertices
        if vertices is None:
            raise ValueError("SMPL-X mesh preview requested without vertices.")

        step = max(1, vertices.shape[0] // 3000)
        sampled_vertices = vertices[::step]
        fig = plt.figure(figsize=(6, 6), dpi=120)
        ax = fig.add_subplot(111, projection="3d")
        ax.set_title("SMPL-X Mesh Vertex Preview")
        ax.scatter(
            sampled_vertices[:, 0],
            sampled_vertices[:, 1],
            sampled_vertices[:, 2],
            c="#80cbc4",
            s=1,
            alpha=0.35,
        )
        joints = result.joints_3d
        ax.scatter(joints[:, 0], joints[:, 1], joints[:, 2], c="#d32f2f", s=20)
        ax.set_xlabel("x")
        ax.set_ylabel("y")
        ax.set_zlabel("z")
        _set_equal_3d_axes(ax, sampled_vertices)
        fig.tight_layout()
        fig.savefig(path)
        plt.close(fig)
        return path

    def _save_loss_history(self, loss_history: List[float], frame_slug: str) -> Path:
        path = self.frames_dir / f"{frame_slug}_optimization_loss.png"
        fig, ax = plt.subplots(figsize=(6, 3.5), dpi=120)
        ax.set_title("SMPL-X Optimization Loss")
        ax.plot(range(1, len(loss_history) + 1), loss_history, color="#7e57c2")
        ax.set_xlabel("iteration")
        ax.set_ylabel("reprojection loss")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(path)
        plt.close(fig)
        return path

    def _save_performance_graph(self) -> Path:
        path = self.graphs_dir / "performance_graph.png"
        frames = [item["frame_index"] for item in self.metrics]
        latency = [item["model_latency_ms"] for item in self.metrics]
        loss = [item["reprojection_loss"] for item in self.metrics]
        knee_angle = [item["knee_angle_deg"] for item in self.metrics]

        fig, axes = plt.subplots(3, 1, figsize=(8, 7), dpi=120, sharex=True)
        axes[0].set_title("Model Performance and Pose Quality")
        axes[0].plot(frames, latency, color="#ef6c00")
        axes[0].set_ylabel("model ms")
        axes[0].grid(True, alpha=0.3)

        axes[1].plot(frames, loss, color="#2e7d32")
        axes[1].set_ylabel("reproj loss")
        axes[1].grid(True, alpha=0.3)

        axes[2].plot(frames, knee_angle, color="#1565c0")
        axes[2].set_ylabel("knee angle")
        axes[2].set_xlabel("frame")
        axes[2].grid(True, alpha=0.3)

        fig.tight_layout()
        fig.savefig(path)
        plt.close(fig)
        return path


def _plot_2d_skeleton(
    ax: Any,
    points: np.ndarray,
    confidence: np.ndarray,
    point_color: str,
    line_color: str,
    label: str,
) -> None:
    visible = confidence >= 0.1
    for start, end in COCO_SKELETON:
        if visible[start] and visible[end]:
            ax.plot(
                [points[start, 0], points[end, 0]],
                [points[start, 1], points[end, 1]],
                color=line_color,
                linewidth=2,
                alpha=0.9,
            )
    ax.scatter(
        points[visible, 0],
        points[visible, 1],
        c=point_color,
        s=35,
        label=label,
        edgecolors="white",
        linewidths=0.5,
    )


def _set_equal_3d_axes(ax: Any, points: np.ndarray) -> None:
    center = points.mean(axis=0)
    radius = float(np.max(np.linalg.norm(points - center, axis=1)))
    if not np.isfinite(radius) or radius < 1e-6:
        radius = 1.0
    ax.set_xlim(center[0] - radius, center[0] + radius)
    ax.set_ylim(center[1] - radius, center[1] + radius)
    ax.set_zlim(center[2] - radius, center[2] + radius)


def _finite(value: Any) -> float:
    number = float(value)
    if math.isnan(number) or math.isinf(number):
        return 0.0
    return number
