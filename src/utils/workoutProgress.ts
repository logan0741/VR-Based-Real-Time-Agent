import type { ExerciseProgress } from '../hooks/useWebSocket';

export const REPS_PER_SET = 8;

export function initialProgress(sets: number): ExerciseProgress {
  return {
    current_set: 1,
    total_sets: sets,
    rep_in_set: 0,
    reps_per_set: REPS_PER_SET,
    total_reps: 0,
    total_target_reps: sets * REPS_PER_SET,
    completed: false,
  };
}

export function progressFromTotalReps(totalReps: number, sets: number): ExerciseProgress {
  const safeSets = Math.max(1, sets);
  const totalTargetReps = safeSets * REPS_PER_SET;
  const safeTotalReps = Math.max(0, totalReps);
  const completed = safeTotalReps >= totalTargetReps;

  if (completed) {
    return {
      current_set: safeSets,
      total_sets: safeSets,
      rep_in_set: REPS_PER_SET,
      reps_per_set: REPS_PER_SET,
      total_reps: safeTotalReps,
      total_target_reps: totalTargetReps,
      completed,
    };
  }

  if (safeTotalReps > 0 && safeTotalReps % REPS_PER_SET === 0) {
    return {
      current_set: Math.min(safeSets, safeTotalReps / REPS_PER_SET),
      total_sets: safeSets,
      rep_in_set: REPS_PER_SET,
      reps_per_set: REPS_PER_SET,
      total_reps: safeTotalReps,
      total_target_reps: totalTargetReps,
      completed,
    };
  }

  return {
    current_set: Math.min(safeSets, Math.floor(safeTotalReps / REPS_PER_SET) + 1),
    total_sets: safeSets,
    rep_in_set: safeTotalReps % REPS_PER_SET,
    reps_per_set: REPS_PER_SET,
    total_reps: safeTotalReps,
    total_target_reps: totalTargetReps,
    completed,
  };
}
