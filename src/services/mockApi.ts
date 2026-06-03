import type { Exercise, FeedbackItem, SessionResult } from '../types';

const sampleFeedback: Record<string, FeedbackItem> = {
  squat: { status: 'warn', message: '무릎이 발끝보다 앞으로 나가지 않게 중심을 뒤로 유지하세요.' },
  lunge: { status: 'warn', message: '앞무릎이 과도하게 벌어지지 않도록 골반을 정렬하세요.' },
  pushup: { status: 'ok', message: '상체 라인이 안정적으로 유지되고 있습니다.' },
};

export async function fetchSessionResult(exercise: Exercise, sets: number): Promise<SessionResult> {
  await new Promise((resolve) => setTimeout(resolve, 250));

  return {
    exercise: exercise.label,
    sets,
    score: 78,
    grade: 'B+',
    totalReps: sets * 8,
    durationMinutes: 12,
    accuracy: 92,
    feedback: [
      { status: 'ok', message: '상체 정렬이 전반적으로 안정적입니다.' },
      { status: 'warn', message: '무릎이 안쪽으로 모이지 않게 발끝 방향을 유지하세요.' },
      { status: 'ok', message: '세트가 진행될수록 하강 속도가 안정되고 있습니다.' },
    ],
  };
}

export async function fetchRealtimeFeedback(exercise: Exercise): Promise<FeedbackItem> {
  await new Promise((resolve) => setTimeout(resolve, 150));
  return sampleFeedback[exercise.id] ?? { status: 'ok', message: '자세가 안정적입니다.' };
}
