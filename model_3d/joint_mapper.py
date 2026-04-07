"""SMPL-X to COCO 17 joint mapping."""

from __future__ import annotations

from typing import Any

try:
    import torch
except ImportError:  # pragma: no cover - startup raises a clear error when fitting.
    torch = None


class COCOJointMapper(torch.nn.Module if torch is not None else object):
    """
    Map SMPL-X joints to COCO 17 joints.

    Preferred path:
        Pass a COCO-compatible J_regressor through smplx.create as
        J_regressor_extra. SMPL-X appends those extra joints to output.joints,
        so this mapper returns the last 17 joints.

    Fallback path:
        If COCO_J_REGRESSOR_PATH is not provided, use approximate native SMPL-X
        joint indices. Face keypoints are approximated by the head joint; this
        is acceptable for a body-focused squat MVP but should be replaced by a
        real regressor for production fitting.
    """

    def __init__(self, use_extra_regressor: bool) -> None:
        if torch is not None:
            super().__init__()
            fallback_indices = torch.tensor(
                [
                    15,  # nose -> head approximation
                    15,  # left_eye -> head approximation
                    15,  # right_eye -> head approximation
                    15,  # left_ear -> head approximation
                    15,  # right_ear -> head approximation
                    16,  # left_shoulder
                    17,  # right_shoulder
                    18,  # left_elbow
                    19,  # right_elbow
                    20,  # left_wrist
                    21,  # right_wrist
                    1,  # left_hip
                    2,  # right_hip
                    4,  # left_knee
                    5,  # right_knee
                    7,  # left_ankle
                    8,  # right_ankle
                ],
                dtype=torch.long,
            )
            self.register_buffer("fallback_indices", fallback_indices, persistent=False)
        self.use_extra_regressor = use_extra_regressor

    def forward(self, joints: Any, vertices: Any = None, **_: Any) -> Any:
        if self.use_extra_regressor:
            if joints.shape[1] < 17:
                raise ValueError("SMPL-X output has fewer than 17 joints.")
            return joints[:, -17:, :]

        indices = self.fallback_indices.to(device=joints.device)
        if joints.shape[1] <= int(indices.max().item()):
            raise ValueError(
                "SMPL-X output does not contain the fallback native joints. "
                "Provide COCO_J_REGRESSOR_PATH for robust COCO mapping."
            )
        return joints.index_select(1, indices)
