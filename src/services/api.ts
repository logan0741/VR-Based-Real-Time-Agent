import type { Exercise, FeedbackItem, SessionResult } from '../types';
import { fetchRealtimeFeedback, fetchSessionResult } from './mockApi';

export async function getSessionResult(exercise: Exercise, sets: number): Promise<SessionResult> {
  // Replace this with the FastAPI result endpoint when the web UI is wired to live sessions.
  return fetchSessionResult(exercise, sets);
}

export async function getRealtimeFeedback(exercise: Exercise): Promise<FeedbackItem> {
  // Replace this with live WebSocket or polling data from FastAPI when needed.
  return fetchRealtimeFeedback(exercise);
}
