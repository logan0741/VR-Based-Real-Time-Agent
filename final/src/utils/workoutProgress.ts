import type { ExerciseProgress } from '../hooks/useWebSocket';

export const DEFAULT_REPS_PER_SET = 8;

export function initialProgress(sets: number, repsPerSet = DEFAULT_REPS_PER_SET): ExerciseProgress {
  const safeRepsPerSet = Math.max(1, repsPerSet);
  return {
    current_set: 1,
    total_sets: sets,
    rep_in_set: 0,
    reps_per_set: safeRepsPerSet,
    total_reps: 0,
    total_target_reps: sets * safeRepsPerSet,
    completed: false,
  };
}

export function progressFromTotalReps(
  totalReps: number,
  sets: number,
  repsPerSet = DEFAULT_REPS_PER_SET,
): ExerciseProgress {
  const safeSets = Math.max(1, sets);
  const safeRepsPerSet = Math.max(1, repsPerSet);
  const totalTargetReps = safeSets * safeRepsPerSet;
  const safeTotalReps = Math.max(0, totalReps);
  const completed = safeTotalReps >= totalTargetReps;

  if (completed) {
    return {
      current_set: safeSets,
      total_sets: safeSets,
      rep_in_set: safeRepsPerSet,
      reps_per_set: safeRepsPerSet,
      total_reps: safeTotalReps,
      total_target_reps: totalTargetReps,
      completed,
    };
  }

  if (safeTotalReps > 0 && safeTotalReps % safeRepsPerSet === 0) {
    return {
      current_set: Math.min(safeSets, safeTotalReps / safeRepsPerSet),
      total_sets: safeSets,
      rep_in_set: safeRepsPerSet,
      reps_per_set: safeRepsPerSet,
      total_reps: safeTotalReps,
      total_target_reps: totalTargetReps,
      completed,
    };
  }

  return {
    current_set: Math.min(safeSets, Math.floor(safeTotalReps / safeRepsPerSet) + 1),
    total_sets: safeSets,
    rep_in_set: safeTotalReps % safeRepsPerSet,
    reps_per_set: safeRepsPerSet,
    total_reps: safeTotalReps,
    total_target_reps: totalTargetReps,
    completed,
  };
}
