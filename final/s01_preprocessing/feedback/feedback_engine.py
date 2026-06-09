"""Generate posture feedback messages from DTW joint distances."""
from __future__ import annotations

from typing import cast

import numpy as np

from .feedback_config import EXERCISE_CONFIGS, ExerciseViewCfg
from .feedback_templates import FEEDBACK_TEMPLATES

MIN_CONFIDENCE: float = 0.25


class FeedbackEngine:
    """Create body-part feedback for an exercise/view configuration."""

    def __init__(self, exercise: str, view: str) -> None:
        key = (exercise, view)
        if key not in EXERCISE_CONFIGS:
            raise ValueError(f"Unsupported exercise/view combination: {key!r}")
        if exercise not in FEEDBACK_TEMPLATES:
            raise ValueError(f"Feedback templates are missing for exercise: {exercise!r}")
        self._exercise = exercise
        self._cfg: ExerciseViewCfg = EXERCISE_CONFIGS[key]

    def analyze(
        self,
        user_raw_keypoints: np.ndarray,
        user_norm_keypoints: np.ndarray,
        expert_norm_keypoints: np.ndarray,
        joint_distances: np.ndarray | None,
    ) -> dict[str, object]:
        if joint_distances is None or joint_distances.size == 0:
            return self._build_result("pending", "warming_up", 0.0)

        if not self._has_min_confidence(user_raw_keypoints):
            return self._build_result("pending", "low_confidence", 0.0)

        scores = self._body_scores(joint_distances)
        body_part = max(scores, key=scores.__getitem__)
        severity = scores[body_part]

        if severity < self._cfg["body_parts"][body_part]["threshold"]:
            return self._build_result("ok", "ok", severity)

        state = self._classify_state(body_part, user_norm_keypoints, expert_norm_keypoints)
        return self._build_result(body_part, state, severity)

    def _build_result(self, body_part: str, state: str, severity: float) -> dict[str, object]:
        if body_part in {"pending", "ok"}:
            message = {
                "warming_up": "측정 중입니다.",
                "low_confidence": "자세를 화면 중앙에 맞춰주세요.",
                "ok": "자세가 안정적입니다.",
            }[state]
        else:
            body_templates = FEEDBACK_TEMPLATES[self._exercise][body_part]
            message = body_templates.get(state, body_templates["generic"])

        return {
            "exercise": self._exercise,
            "body_part": body_part,
            "state": state,
            "severity": float(severity),
            "message": message,
        }

    def _has_min_confidence(self, user_raw_keypoints: np.ndarray) -> bool:
        return all(
            float(user_raw_keypoints[idx, 2]) >= MIN_CONFIDENCE
            for idx in self._cfg["confidence_joints"]
        )

    def _body_scores(self, joint_distances: np.ndarray) -> dict[str, float]:
        scores: dict[str, float] = {}
        for part_name, part_cfg in self._cfg["body_parts"].items():
            start, end = part_cfg["dtw_slice"]
            scores[part_name] = float(np.max(joint_distances[start:end]))
        return scores

    def _classify_state(
        self,
        body_part: str,
        user_norm_keypoints: np.ndarray,
        expert_norm_keypoints: np.ndarray,
    ) -> str:
        part_cfg = self._cfg["body_parts"][body_part]
        rule = part_cfg["classify"]
        joints = list(part_cfg["joints"])
        axis: int = rule["axis"]

        if rule["type"] == "gap_compare":
            user_gap = abs(float(user_norm_keypoints[joints[0], axis] - user_norm_keypoints[joints[1], axis]))
            expert_gap = abs(float(expert_norm_keypoints[joints[0], axis] - expert_norm_keypoints[joints[1], axis]))
            gap_threshold = cast(float, rule.get("gap_threshold", 0.0))
            gap_state = cast(str, rule.get("gap_state", "misaligned"))
            if abs(user_gap - expert_gap) > gap_threshold:
                return gap_state

        user_val = float(np.mean(user_norm_keypoints[joints, axis]))
        expert_val = float(np.mean(expert_norm_keypoints[joints, axis]))
        axis_tolerance = float(rule.get("axis_tolerance", 0.0))
        if abs(user_val - expert_val) < axis_tolerance:
            return "generic"
        return rule["pos"] if user_val > expert_val else rule["neg"]
