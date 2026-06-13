import type { SessionResult } from '../types';

export type FinalFeedbackTtsResponse = {
  status: 'ok' | 'error';
  engine?: string;
  cached?: boolean;
  text?: string;
  audio_url?: string;
  message?: string;
  code?: string;
};

export async function requestFinalFeedbackTts(result: SessionResult): Promise<FinalFeedbackTtsResponse> {
  const response = await fetch('/api/tts/final-feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(result),
  });

  if (!response.ok) {
    return {
      status: 'error',
      message: `TTS 요청 실패 (${response.status})`,
      code: 'http_error',
    };
  }

  return response.json();
}
