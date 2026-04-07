"""Fit SMPL-X directly to 3D joint coordinates."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from model_3d.fitter import (
    OptimizationPoseFitter,
    prefer_npz_model_path,
    resolve_smplx_model_path,
    weighted_reprojection_loss,
)
from model_3d.pose3d_dataset import pose3d_keypoints_to_pixels
from model_3d.schemas import FitResult

try:
    import torch
except ImportError:  # pragma: no cover - init raises a clear error.
    torch = None


class SMPLXCoordinateFitter(OptimizationPoseFitter):
    """
    Optimize SMPL-X parameters against target 3D joints.

    This is the important feasibility path: input coordinates -> SMPL-X body
    parameters -> fitted 3D body/joints. It does not use the lifter model.
    """

    backend = "smplx_coordinate_fit"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.backend = "smplx_coordinate_fit"
        self.num_iters = int(os.getenv("SMPLX_3D_OPT_ITERS", str(self.num_iters)))
        self.learning_rate = float(os.getenv("SMPLX_3D_OPT_LR", str(self.learning_rate)))
        self.joint_loss_weight = float(os.getenv("SMPLX_3D_JOINT_LOSS_WEIGHT", "1.0"))
        self.reprojection_loss_weight = float(os.getenv("SMPLX_3D_REPROJ_LOSS_WEIGHT", "0.01"))
        self._thread_lock = threading.Lock()

    def forward(self, payload: Any) -> FitResult:
        if torch is None:
            raise RuntimeError("torch is required for SMPL-X coordinate fitting.")
        if not isinstance(payload, dict):
            raise ValueError("SMPLXCoordinateFitter expects a pose_3d_v3 dict payload.")

        target_3d_np = np.asarray(payload["joints_3d"], dtype=np.float32)
        if target_3d_np.shape != (17, 3):
            raise ValueError(f"joints_3d must have shape (17, 3). Received {target_3d_np.shape}.")

        keypoints_2d = np.asarray(payload.get("keypoints_2d", target_3d_np), dtype=np.float32)
        target_2d_np, confidence_np = pose3d_keypoints_to_pixels(keypoints_2d)

        with self._thread_lock:
            target_3d = torch.as_tensor(target_3d_np, dtype=torch.float32, device=self.device)
            target_2d = torch.as_tensor(target_2d_np, dtype=torch.float32, device=self.device)
            confidence = torch.as_tensor(confidence_np, dtype=torch.float32, device=self.device)

            global_orient = self._last_global_orient.detach().clone().requires_grad_(True)
            body_pose = self._last_body_pose.detach().clone().requires_grad_(True)
            transl = target_3d.mean(dim=0, keepdim=True).detach().clone().requires_grad_(True)
            log_scale = torch.zeros((1, 1, 1), dtype=torch.float32, device=self.device, requires_grad=True)

            optimizer = torch.optim.Adam(
                [global_orient, body_pose, transl, log_scale],
                lr=self.learning_rate,
            )
            fixed_inputs = {key: value for key, value in self._fixed_inputs.items() if key != "transl"}
            loss_history: List[float] = []

            for _ in range(self.num_iters):
                optimizer.zero_grad(set_to_none=True)
                output = self.model(
                    global_orient=global_orient,
                    body_pose=body_pose,
                    return_verts=False,
                    **fixed_inputs,
                )
                fitted_joints = output.joints[:, :17, :] * log_scale.exp() + transl[:, None, :]
                joint_loss = ((fitted_joints[0] - target_3d) ** 2).sum(dim=-1).mean()
                projected_2d = self.camera.project(fitted_joints)[0]
                reproj_loss = weighted_reprojection_loss(projected_2d, target_2d, confidence)
                pose_prior = self.pose_prior_weight * body_pose.pow(2).mean()
                loss = (
                    self.joint_loss_weight * joint_loss
                    + self.reprojection_loss_weight * reproj_loss
                    + pose_prior
                )
                loss.backward()
                optimizer.step()

                if self.capture_loss_history:
                    loss_history.append(float(joint_loss.detach().cpu().item()))

            with torch.no_grad():
                final_output = self.model(
                    global_orient=global_orient,
                    body_pose=body_pose,
                    return_verts=self.return_vertices,
                    **fixed_inputs,
                )
                final_joints = final_output.joints[:, :17, :] * log_scale.exp() + transl[:, None, :]
                final_projected_2d = self.camera.project(final_joints)[0]
                final_joint_loss = ((final_joints[0] - target_3d) ** 2).sum(dim=-1).mean()

                vertices_np = None
                if self.return_vertices and hasattr(final_output, "vertices"):
                    vertices_np = (
                        final_output.vertices[0] * log_scale.exp()[0] + transl[0]
                    ).detach().cpu().numpy().copy()

                self._last_global_orient = global_orient.detach().clone()
                self._last_body_pose = body_pose.detach().clone()

                return FitResult(
                    backend=self.backend,
                    joints_3d=final_joints[0].detach().cpu().numpy().copy(),
                    projected_joints_2d=final_projected_2d.detach().cpu().numpy().copy(),
                    target_joints_2d=target_2d_np,
                    confidence=confidence_np,
                    reprojection_loss=float(final_joint_loss.detach().cpu().item()),
                    global_orient=global_orient.detach().cpu().numpy()[0].copy(),
                    body_pose=body_pose.detach().cpu().numpy()[0].copy(),
                    loss_history=loss_history,
                    vertices=vertices_np,
                )


def smplx_coordinate_fit_available() -> Dict[str, Any]:
    """Return availability details without constructing the heavy SMPL-X model."""
    try:
        import smplx  # noqa: F401
    except ImportError:
        return {
            "available": False,
            "reason": "Python package 'smplx' is not installed in this interpreter.",
        }

    model_path = Path(os.getenv("SMPLX_MODEL_PATH", resolve_smplx_model_path()))
    if not model_path.is_absolute():
        model_path = Path(__file__).resolve().parents[1] / model_path
    model_path = prefer_npz_model_path(model_path.resolve())
    if not model_path.exists():
        return {
            "available": False,
            "reason": f"SMPL-X model file not found: {model_path}",
        }
    return {"available": True, "model_path": str(model_path)}
