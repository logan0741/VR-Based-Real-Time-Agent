"""SMPL-X fitting backends for Phase 1 optimization and Phase 2 regression."""

from __future__ import annotations

import os
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, List, Optional, Tuple

import numpy as np

from model_3d.camera import CameraIntrinsics
from model_3d.config import env_bool, project_root
from model_3d.joint_mapper import COCOJointMapper
from model_3d.preprocessing import parse_keypoints_payload
from model_3d.schemas import FitResult

try:
    import torch
except ImportError:  # pragma: no cover - startup raises a clear error when fitting.
    torch = None


class BasePoseFitter(ABC):
    """Stable interface for Phase 1 optimization and Phase 2 regression backends."""

    @abstractmethod
    def forward(self, payload: Any) -> FitResult:
        """Fit or regress a 3D body from one client payload."""


class RegressionPoseFitter(BasePoseFitter):
    """
    Phase 2 placeholder.

    Replace this class with OSX, PIXIE, or another single-pass model. The public
    forward(payload) interface should stay unchanged so the WebSocket server and
    exercise analyzer do not need to know which fitting strategy is active.
    """

    backend = "regression"

    def forward(self, payload: Any) -> FitResult:
        raise NotImplementedError(
            "Phase 2 image/regression backend is not wired yet. "
            "Use FITTER_BACKEND=optimization for the SMPL-X optimizer."
        )


class OptimizationPoseFitter(BasePoseFitter):
    """Phase 1 SMPL-X optimizer using 2D reprojection loss."""

    backend = "optimization"

    def __init__(
        self,
        model_path: Optional[str] = None,
        coco_j_regressor_path: Optional[str] = None,
        camera: Optional[CameraIntrinsics] = None,
        num_iters: Optional[int] = None,
        learning_rate: Optional[float] = None,
        num_betas: int = 10,
        camera_depth: Optional[float] = None,
        return_vertices: Optional[bool] = None,
    ) -> None:
        if torch is None:
            raise RuntimeError(
                "torch is required for SMPL-X optimization. Install a CPU or CUDA "
                "build of torch before running this server."
            )

        try:
            import smplx
        except ImportError as exc:
            raise RuntimeError(
                "smplx is required for Phase 1 fitting. Install it with `pip install smplx`."
            ) from exc

        self.camera = camera or CameraIntrinsics(
            width=int(os.getenv("CAMERA_WIDTH", "640")),
            height=int(os.getenv("CAMERA_HEIGHT", "480")),
            fx=float(os.getenv("CAMERA_FX", "500")),
            fy=float(os.getenv("CAMERA_FY", "500")),
            cx=float(os.getenv("CAMERA_CX", "320")),
            cy=float(os.getenv("CAMERA_CY", "240")),
            flip_y=env_bool("CAMERA_FLIP_Y", True),
        )
        self.num_iters = num_iters or int(os.getenv("SMPLX_OPT_ITERS", "15"))
        self.learning_rate = learning_rate or float(os.getenv("SMPLX_OPT_LR", "0.03"))
        self.pose_prior_weight = float(os.getenv("SMPLX_POSE_PRIOR_WEIGHT", "0.001"))
        self.capture_loss_history = env_bool("SMPLX_CAPTURE_LOSS_HISTORY", True)
        self.num_betas = num_betas
        self.camera_depth = camera_depth or float(os.getenv("SMPLX_CAMERA_DEPTH", "2.5"))
        self.return_vertices = (
            env_bool("RETURN_VERTICES", False) if return_vertices is None else return_vertices
        )

        use_cuda = env_bool("USE_CUDA", True) and torch.cuda.is_available()
        self.device = torch.device("cuda" if use_cuda else "cpu")
        self._thread_lock = threading.Lock()

        resolved_model_path = Path(model_path or resolve_smplx_model_path()).resolve()
        if not resolved_model_path.exists():
            raise FileNotFoundError(
                f"SMPL-X model asset not found: {resolved_model_path}. "
                "Set SMPLX_MODEL_PATH to SMPLX_NEUTRAL.pkl or your SMPL-X model file."
            )

        j_regressor_extra, use_extra_regressor = self._load_coco_regressor(
            coco_j_regressor_path or os.getenv("COCO_J_REGRESSOR_PATH")
        )
        joint_mapper = COCOJointMapper(use_extra_regressor=use_extra_regressor)

        model_kwargs = dict(
            model_path=str(resolved_model_path),
            model_type="smplx",
            gender="neutral",
            num_betas=self.num_betas,
            use_pca=False,
            batch_size=1,
            joint_mapper=joint_mapper,
            J_regressor_extra=j_regressor_extra,
            create_global_orient=False,
            create_body_pose=False,
            create_betas=False,
            create_left_hand_pose=False,
            create_right_hand_pose=False,
            create_expression=False,
            create_jaw_pose=False,
            create_leye_pose=False,
            create_reye_pose=False,
            create_transl=False,
        )

        try:
            self.model = smplx.create(**model_kwargs)
        except Exception:
            # smplx.create can infer the model type from a file name. Generic
            # files such as smplx_locked_head/neutral/model.pkl may fail that
            # inference, so fall back to the direct SMPLX constructor.
            if resolved_model_path.is_file() and resolved_model_path.name.lower() == "model.pkl":
                model_kwargs.pop("model_path")
                model_kwargs.pop("model_type")
                self.model = smplx.SMPLX(str(resolved_model_path), **model_kwargs)
            else:
                raise

        self.model = self.model.to(self.device)
        self.model.eval()
        for parameter in self.model.parameters():
            parameter.requires_grad_(False)

        # Warm-start each frame from the previous solution. Detach before every
        # optimization loop to avoid retaining the old computation graph.
        self._last_global_orient = torch.zeros((1, 3), dtype=torch.float32, device=self.device)
        self._last_body_pose = torch.zeros((1, 63), dtype=torch.float32, device=self.device)

        self._fixed_inputs = {
            "betas": torch.zeros((1, self.num_betas), dtype=torch.float32, device=self.device),
            "left_hand_pose": torch.zeros((1, 45), dtype=torch.float32, device=self.device),
            "right_hand_pose": torch.zeros((1, 45), dtype=torch.float32, device=self.device),
            "jaw_pose": torch.zeros((1, 3), dtype=torch.float32, device=self.device),
            "leye_pose": torch.zeros((1, 3), dtype=torch.float32, device=self.device),
            "reye_pose": torch.zeros((1, 3), dtype=torch.float32, device=self.device),
            "expression": torch.zeros((1, 10), dtype=torch.float32, device=self.device),
            "transl": torch.tensor(
                [[0.0, 0.0, self.camera_depth]], dtype=torch.float32, device=self.device
            ),
        }

        print(
            f"[PoseFitter] backend=optimization device={self.device} "
            f"model={resolved_model_path} coco_regressor={use_extra_regressor}"
        )

    def _load_coco_regressor(self, path: Optional[str]) -> Tuple[Any, bool]:
        if not path:
            print(
                "[PoseFitter] COCO_J_REGRESSOR_PATH not set. "
                "Using approximate native SMPL-X -> COCO mapping."
            )
            return None, False

        regressor_path = Path(path).resolve()
        if not regressor_path.exists():
            raise FileNotFoundError(f"COCO J_regressor not found: {regressor_path}")

        regressor = np.load(regressor_path).astype(np.float32)
        if regressor.ndim != 2 or regressor.shape[0] != 17:
            raise ValueError(
                "COCO J_regressor must have shape [17, num_vertices]. "
                f"Received {regressor.shape} from {regressor_path}."
            )
        return torch.as_tensor(regressor, dtype=torch.float32), True

    def forward(self, payload: Any) -> FitResult:
        target_2d_np, confidence_np = parse_keypoints_payload(payload, self.camera)

        # The SMPL-X module is stateful and we warm-start from previous frames,
        # so guard forward() when asyncio runs it in a worker thread.
        with self._thread_lock:
            target_2d = torch.as_tensor(target_2d_np, dtype=torch.float32, device=self.device)
            confidence = torch.as_tensor(confidence_np, dtype=torch.float32, device=self.device)

            global_orient = self._last_global_orient.detach().clone().requires_grad_(True)
            body_pose = self._last_body_pose.detach().clone().requires_grad_(True)
            optimizer = torch.optim.Adam([global_orient, body_pose], lr=self.learning_rate)
            loss_history: List[float] = []

            for _ in range(self.num_iters):
                optimizer.zero_grad(set_to_none=True)
                output = self.model(
                    global_orient=global_orient,
                    body_pose=body_pose,
                    return_verts=False,
                    **self._fixed_inputs,
                )
                joints_3d = output.joints[:, :17, :]
                projected_2d = self.camera.project(joints_3d)[0]
                reprojection_loss = weighted_reprojection_loss(
                    projected_2d, target_2d, confidence
                )
                pose_prior = self.pose_prior_weight * body_pose.pow(2).mean()
                loss = reprojection_loss + pose_prior
                loss.backward()
                optimizer.step()

                if self.capture_loss_history:
                    loss_history.append(float(reprojection_loss.detach().cpu().item()))

            with torch.no_grad():
                final_output = self.model(
                    global_orient=global_orient,
                    body_pose=body_pose,
                    return_verts=self.return_vertices,
                    **self._fixed_inputs,
                )
                final_joints_3d = final_output.joints[:, :17, :]
                final_projected_2d = self.camera.project(final_joints_3d)[0]
                final_loss = weighted_reprojection_loss(
                    final_projected_2d, target_2d, confidence
                )

                # Critical memory boundary: everything returned from this
                # method is detached, moved to CPU, and converted to numpy.
                joints_np = final_joints_3d[0].detach().cpu().numpy().copy()
                projected_np = final_projected_2d.detach().cpu().numpy().copy()
                global_orient_np = global_orient.detach().cpu().numpy()[0].copy()
                body_pose_np = body_pose.detach().cpu().numpy()[0].copy()
                vertices_np = None
                if self.return_vertices and hasattr(final_output, "vertices"):
                    vertices_np = final_output.vertices[0].detach().cpu().numpy().copy()

                self._last_global_orient = global_orient.detach().clone()
                self._last_body_pose = body_pose.detach().clone()

                return FitResult(
                    backend=self.backend,
                    joints_3d=joints_np,
                    projected_joints_2d=projected_np,
                    target_joints_2d=target_2d_np,
                    confidence=confidence_np,
                    reprojection_loss=float(final_loss.detach().cpu().item()),
                    global_orient=global_orient_np,
                    body_pose=body_pose_np,
                    loss_history=loss_history,
                    vertices=vertices_np,
                )


def resolve_smplx_model_path() -> str:
    """Resolve a practical default while still allowing explicit production paths."""
    env_path = os.getenv("SMPLX_MODEL_PATH")
    if env_path:
        return env_path

    root = project_root()
    candidates = [
        root / "SMPLX_NEUTRAL.pkl",
        root / "models" / "SMPLX_NEUTRAL.pkl",
        root / "models" / "smplx" / "SMPLX_NEUTRAL.pkl",
        root / "smplx_locked_head" / "neutral" / "model.pkl",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    # Return the preferred file name so the FileNotFoundError is actionable.
    return str(root / "SMPLX_NEUTRAL.pkl")


def weighted_reprojection_loss(predicted_2d: Any, target_2d: Any, confidence: Any) -> Any:
    """Confidence-weighted L2 reprojection loss in pixel space."""
    weights = confidence.clamp(min=0.0, max=1.0)
    weight_sum = weights.sum()
    weights = torch.where(weight_sum < 1e-6, torch.ones_like(weights), weights)
    squared_error = (predicted_2d - target_2d).pow(2).sum(dim=-1)
    return (squared_error * weights).sum() / weights.sum().clamp(min=1e-6)


def build_pose_fitter() -> BasePoseFitter:
    backend = os.getenv("FITTER_BACKEND", "optimization").strip().lower()
    if backend in {"optimization", "smplx", "smplx_optimization"}:
        return OptimizationPoseFitter()
    if backend in {"regression", "osx", "pixie"}:
        return RegressionPoseFitter()
    raise ValueError(f"Unsupported FITTER_BACKEND={backend}")
