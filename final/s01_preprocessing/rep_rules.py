"""Exercise-specific repetition counting thresholds."""
from __future__ import annotations

from typing import Any


SUPPORTED_DETECTOR_TYPES: frozenset[str] = frozenset({"squat", "hammer_curl", "pullup", "lateral_raise"})
SUPPORTED_NORMALIZER_TYPES: frozenset[str] = frozenset({"front", "side_left", "side_right"})


ANGLE_REP_RULES: dict[str, dict[str, Any]] = {
    # direction=decrease: extended/high angle -> flexed/low angle -> extended/high angle.
    "squat": {
        "direction": "decrease",
        "ready": 155.0,
        "target": 125.0,
        "return": 150.0,
        "min_range": 25.0,
    },
    "hammer_curl": {
        "direction": "decrease",
        "ready": 145.0,
        "target": 75.0,
        "return": 135.0,
        "min_range": 55.0,
    },
    "pullup": {
        "direction": "decrease",
        "ready": 140.0,
        "target": 95.0,
        "return": 130.0,
        "min_range": 35.0,
    },
    # direction=increase: arm down/low angle -> raised/high angle -> arm down/low angle.
    "lateral_raise": {
        "direction": "increase",
        "ready": 30.0,
        "target": 70.0,
        "return": 40.0,
        "min_range": 35.0,
    },
}
