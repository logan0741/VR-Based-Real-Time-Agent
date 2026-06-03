export type Exercise = {
  id: string;
  label: string;
  icon: string;
};

export type FeedbackItem = {
  status: 'ok' | 'warn';
  message: string;
};

export type SessionResult = {
  exercise: string;
  sets: number;
  score: number;
  grade: string;
  totalReps: number;
  durationMinutes: number;
  accuracy: number;
  feedback: FeedbackItem[];
};
