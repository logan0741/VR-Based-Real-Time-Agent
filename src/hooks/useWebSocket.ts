import { useCallback, useEffect, useRef, useState } from 'react';

export type PoseFrame = {
  status: string;
  data_type?: string;
  keypoints_2d?: number[][];
  frame_id?: string;
  progress?: ExerciseProgress;
  feedback?: {
    score: number;
    message: string;
    rep_count: number;
    rep_scores: number[];
    current_set?: number;
    total_sets?: number;
    rep_in_set?: number;
    reps_per_set?: number;
    total_reps?: number;
    total_target_reps?: number;
    completed?: boolean;
    bad_joints?: number[];
    body_part?: string;
    state?: string;
    severity?: number;
    countable?: boolean;
    muscle_fatigue?: Record<string, string>;
  };
};

export type ExerciseProgress = {
  current_set: number;
  total_sets: number;
  rep_in_set: number;
  reps_per_set: number;
  total_reps: number;
  total_target_reps: number;
  completed: boolean;
};

export type SessionControl = {
  version: number;
  user_id?: string;
  exercise_type: string;
  sets: number;
  reps_per_set: number;
  expert_started_at_ms?: number;
  expert_phase_ms?: number;
};

type WebSocketStatus = 'connecting' | 'open' | 'closed' | 'error';

function buildWsUrl(): string {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  if (window.location.protocol === 'http:' && window.location.port && window.location.port !== '8000') {
    return `${proto}://${window.location.hostname}:8000/ws/pose`;
  }
  const host = window.location.host || 'localhost:8000';
  return `${proto}://${host}/ws/pose`;
}

export function useWebSocket() {
  const [latestFrame, setLatestFrame] = useState<PoseFrame | null>(null);
  const [status, setStatus] = useState<WebSocketStatus>('connecting');
  const [poseCount, setPoseCount] = useState(0);
  const [lastPoseAt, setLastPoseAt] = useState<number | null>(null);
  const [sessionControl, setSessionControl] = useState<SessionControl | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastFrameRef = useRef<PoseFrame | null>(null);
  const pendingConfigRef = useRef<unknown>(null);
  useEffect(() => {
    let active = true;

    function connect() {
      if (!active) return;
      setStatus('connecting');
      const ws = new WebSocket(buildWsUrl());
      wsRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const data: PoseFrame = JSON.parse(event.data as string);
          const control = (data as PoseFrame & { control?: SessionControl }).control;
          if (control?.exercise_type) {
            setSessionControl(control);
          }
          if (data.status === 'ok' && data.keypoints_2d) {
            const prev = lastFrameRef.current;
            const merged =
              data.data_type === 'pose'
                ? {
                    ...prev,
                    status: data.status,
                    data_type: data.data_type,
                    frame_id: data.frame_id,
                    keypoints_2d: data.keypoints_2d,
                    feedback: prev?.feedback,
                  }
                : { ...prev, ...data };
            lastFrameRef.current = merged;
            setLatestFrame(merged);
            if (data.data_type === 'pose') {
              setPoseCount((count) => count + 1);
              setLastPoseAt(Date.now());
            }
          }
        } catch {
          // ignore parse errors
        }
      };

      ws.onopen = () => {
        setStatus('open');
        if (pendingConfigRef.current) {
          ws.send(JSON.stringify(pendingConfigRef.current));
        }
      };

      ws.onclose = () => {
        setStatus('closed');
        if (!active) return;
        retryRef.current = setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        setStatus('error');
        ws.close();
      };
    }

    connect();

    return () => {
      active = false;
      if (retryRef.current) clearTimeout(retryRef.current);
      wsRef.current?.close();
    };
  }, []);

  const sendJson = useCallback((payload: unknown) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return false;
    ws.send(JSON.stringify(payload));
    return true;
  }, []);

  const sendOrQueueConfig = useCallback((payload: unknown) => {
    pendingConfigRef.current = payload;
    return sendJson(payload);
  }, [sendJson]);

  const selectExercise = useCallback((options: { userId?: string; exerciseType: string; sets: number; repsPerSet: number }) =>
    sendOrQueueConfig({
      data_type: 'session_config',
      user_id: options.userId ?? 'quest_app',
      exercise_type: options.exerciseType,
      sets: options.sets,
      reps_per_set: options.repsPerSet,
    }), [sendOrQueueConfig]);

  const startSession = useCallback((options: { userId?: string; exerciseType: string; sets: number; repsPerSet: number }) =>
    sendJson({
      data_type: 'session_start',
      user_id: options.userId ?? 'quest_app',
      exercise_type: options.exerciseType,
      sets: options.sets,
      reps_per_set: options.repsPerSet,
    }), [sendJson]);

  const endSession = useCallback(() => sendJson({ data_type: 'session_end' }), [sendJson]);

  return { latestFrame, status, poseCount, lastPoseAt, sessionControl, selectExercise, startSession, endSession };
}
