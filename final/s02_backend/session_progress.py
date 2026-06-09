"""Helpers for deriving set/rep progress from server session control."""
from __future__ import annotations

from typing import Any, Dict


def exercise_progress(session_control: Dict[str, Any], rep_count: int) -> Dict[str, Any]:
    sets = max(1, int(session_control.get("sets", 1) or 1))
    reps_per_set = max(1, int(session_control.get("reps_per_set", 8) or 8))
    total_target_reps = sets * reps_per_set
    total_reps = max(0, int(rep_count or 0))
    completed = total_reps >= total_target_reps

    if completed:
        current_set = sets
        rep_in_set = reps_per_set
    elif total_reps > 0 and total_reps % reps_per_set == 0:
        current_set = min(sets, total_reps // reps_per_set)
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


def attach_progress(message: Dict[str, Any], session_control: Dict[str, Any]) -> Dict[str, Any]:
    feedback = message.get("feedback")
    if isinstance(feedback, dict):
        progress = exercise_progress(session_control, int(feedback.get("rep_count", 0) or 0))
        feedback.update(progress)
        message["progress"] = progress
    return message
