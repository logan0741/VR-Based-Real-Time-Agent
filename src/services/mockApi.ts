import type { Exercise, FeedbackItem, SessionResult } from '../types';

const sampleFeedback: Record<string, FeedbackItem> = {
  squat: { status: 'warn', message: '무릎이 발끝을 넘어요' },
  lunge: { status: 'warn', message: '앞무릎이 과도하게 밀려요' },
  pushup: { status: 'ok', message: '상체가 정렬되어 안정적입니다' },
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
      { status: 'ok', message: '상체 직립 자세가 전반적으로 안정적으로 유지되었습니다.' },
      { status: 'warn', message: '무릎이 발끝을 넘는 경향이 있어요. 앉을 때 체중을 뒤꿈치에 더 실어보세요.' },
      { status: 'ok', message: '세트가 진행될수록 하강 속도가 빨라졌습니다. 3초 카운트로 천천히 내려가면 효과가 높아집니다.' },
    ],
  };
}

export async function fetchRealtimeFeedback(exercise: Exercise): Promise<FeedbackItem> {
  await new Promise((resolve) => setTimeout(resolve, 150));
  return sampleFeedback[exercise.id] ?? { status: 'ok', message: '자세가 안정적입니다.' };
}
