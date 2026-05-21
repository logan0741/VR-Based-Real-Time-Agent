from typing import TypedDict

try:
    from typing import NotRequired
except ImportError:
    from typing_extensions import NotRequired

from backend.utils.keypoints import (
    LEFT_ANKLE,
    LEFT_ELBOW,
    LEFT_HIP,
    LEFT_KNEE,
    LEFT_SHOULDER,
    LEFT_WRIST,
    RIGHT_ANKLE,
    RIGHT_ELBOW,
    RIGHT_HIP,
    RIGHT_KNEE,
    RIGHT_SHOULDER,
)


class ClassifyRule(TypedDict):
    """상태 분류 규칙 — axis_compare 또는 gap_compare 타입을 사용한다."""

    type: str
    axis: int
    pos: str
    neg: str
    axis_tolerance: NotRequired[float]
    gap_threshold: NotRequired[float]
    gap_state: NotRequired[str]


class BodyPartCfg(TypedDict):
    """단일 신체 부위의 피드백 분석 설정."""

    joints: tuple[int, ...]
    dtw_slice: tuple[int, int]
    threshold: float
    classify: ClassifyRule


class ExerciseViewCfg(TypedDict):
    """운동·뷰 조합의 전체 피드백 분석 설정."""

    confidence_joints: tuple[int, ...]
    body_parts: dict[str, BodyPartCfg]


EXERCISE_CONFIGS: dict[tuple[str, str], ExerciseViewCfg] = {
    ("squat", "side"): {
        "confidence_joints": (
            LEFT_SHOULDER, RIGHT_SHOULDER,
            LEFT_HIP, RIGHT_HIP,
            LEFT_KNEE, RIGHT_KNEE,
        ),
        "body_parts": {
            "torso": {
                "joints": (LEFT_SHOULDER, RIGHT_SHOULDER),
                "dtw_slice": (0, 2),
                "threshold": 0.10,
                "classify": {
                    "type": "axis_compare",
                    "axis": 1,
                    "axis_tolerance": 0.02,
                    "pos": "too_forward",
                    "neg": "too_upright",
                },
            },
            "hip": {
                "joints": (LEFT_HIP, RIGHT_HIP),
                "dtw_slice": (2, 4),
                "threshold": 0.10,
                "classify": {
                    "type": "axis_compare",
                    "axis": 0,
                    "axis_tolerance": 0.02,
                    "pos": "too_low",
                    "neg": "too_high",
                },
            },
            "knee": {
                "joints": (LEFT_KNEE, RIGHT_KNEE),
                "dtw_slice": (4, 6),
                "threshold": 0.12,
                "classify": {
                    "type": "axis_compare",
                    "axis": 1,
                    "axis_tolerance": 0.02,
                    "pos": "too_forward",
                    "neg": "too_backward",
                },
            },
            "ankle": {
                "joints": (LEFT_ANKLE, RIGHT_ANKLE),
                "dtw_slice": (6, 8),
                "threshold": 0.10,
                "classify": {
                    "type": "axis_compare",
                    "axis": 1,
                    "axis_tolerance": 0.02,
                    "pos": "too_forward",
                    "neg": "limited",
                },
            },
        },
    },
    ("hammer_curl", "side"): {
        "confidence_joints": (LEFT_SHOULDER, LEFT_ELBOW),
        "body_parts": {
            "elbow": {
                "joints": (LEFT_ELBOW,),
                "dtw_slice": (1, 2),
                "threshold": 0.12,
                "classify": {
                    "type": "axis_compare",
                    "axis": 1,
                    "axis_tolerance": 0.02,
                    "pos": "too_forward",
                    "neg": "too_backward",
                },
            },
            "torso": {
                "joints": (LEFT_SHOULDER,),
                "dtw_slice": (0, 1),
                "threshold": 0.10,
                "classify": {
                    "type": "axis_compare",
                    "axis": 1,
                    "axis_tolerance": 0.02,
                    "pos": "too_forward",
                    "neg": "leaning_back",
                },
            },
            "wrist": {
                "joints": (LEFT_WRIST,),
                "dtw_slice": (2, 3),
                "threshold": 0.12,
                "classify": {
                    "type": "axis_compare",
                    "axis": 1,
                    "axis_tolerance": 0.02,
                    "pos": "flexion",
                    "neg": "extension",
                },
            },
        },
    },
    ("pullup", "front"): {
        "confidence_joints": (
            LEFT_SHOULDER, RIGHT_SHOULDER,
            LEFT_ELBOW, RIGHT_ELBOW,
        ),
        "body_parts": {
            "shoulder": {
                "joints": (LEFT_SHOULDER, RIGHT_SHOULDER),
                "dtw_slice": (0, 2),
                "threshold": 0.10,
                "classify": {
                    "type": "gap_compare",
                    "axis": 0,
                    "axis_tolerance": 0.02,
                    "gap_threshold": 0.05,
                    "gap_state": "misaligned",
                    "pos": "too_high",
                    "neg": "too_low",
                },
            },
            "elbow": {
                "joints": (LEFT_ELBOW, RIGHT_ELBOW),
                "dtw_slice": (2, 4),
                "threshold": 0.12,
                "classify": {
                    "type": "gap_compare",
                    "axis": 1,
                    "axis_tolerance": 0.02,
                    "gap_threshold": 0.08,
                    "gap_state": "misaligned",
                    "pos": "too_wide",
                    "neg": "too_narrow",
                },
            },
        },
    },
}
