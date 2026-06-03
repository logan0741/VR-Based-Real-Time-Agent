import { useEffect, useRef, useState } from 'react';

export type PoseFrame = {
  status: string;
  data_type?: string;
  keypoints_2d?: number[][];
  frame_id?: string;
  feedback?: {
    score: number;
    message: string;
    rep_count: number;
    rep_scores: number[];
    body_part?: string;
  };
};

function buildWsUrl(): string {
  const host = window.location.host || 'localhost:8000';
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${host}/ws/pose`;
}

export function useWebSocket() {
  const [latestFrame, setLatestFrame] = useState<PoseFrame | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastFrameRef = useRef<PoseFrame | null>(null);
  useEffect(() => {
    let active = true;

    function connect() {
      if (!active) return;
      const ws = new WebSocket(buildWsUrl());
      wsRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const data: PoseFrame = JSON.parse(event.data as string);
          if (data.status === 'ok' && data.keypoints_2d) {
            const merged =
              data.data_type === 'pose'
                ? { ...lastFrameRef.current, ...data, feedback: lastFrameRef.current?.feedback }
                : { ...lastFrameRef.current, ...data };
            lastFrameRef.current = merged;
            setLatestFrame(merged);
          }
        } catch {
          // ignore parse errors
        }
      };

      ws.onclose = () => {
        if (!active) return;
        retryRef.current = setTimeout(connect, 3000);
      };

      ws.onerror = () => ws.close();
    }

    connect();

    return () => {
      active = false;
      if (retryRef.current) clearTimeout(retryRef.current);
      wsRef.current?.close();
    };
  }, []);

  const sendJson = (payload: unknown) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return false;
    ws.send(JSON.stringify(payload));
    return true;
  };

  const startSession = (options: { userId?: string; exerciseType: string; sets: number; repsPerSet: number }) =>
    sendJson({
      data_type: 'session_start',
      user_id: options.userId ?? 'quest_app',
      exercise_type: options.exerciseType,
      sets: options.sets,
      reps_per_set: options.repsPerSet,
    });

  const endSession = () => sendJson({ data_type: 'session_end' });

  return { latestFrame, startSession, endSession };
}
