import type { Exercise, FeedbackItem, SessionResult } from '../types';
import { fetchSessionResult, fetchRealtimeFeedback } from './mockApi';

export async function getSessionResult(exercise: Exercise, sets: number): Promise<SessionResult> {
  // 실제 백엔드 API가 준비되면 이 함수에서 호출을 전환하세요.
  return fetchSessionResult(exercise, sets);
}

export async function getRealtimeFeedback(exercise: Exercise): Promise<FeedbackItem> {
  // 실제 센서/AI 데이터가 나오면 이 함수를 대체하세요.
  return fetchRealtimeFeedback(exercise);
}
