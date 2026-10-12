import { useEffect, useRef, useState } from 'react';

export type PoseFrame = {
  status: string;
  data_type?: string;
  frame_id?: string;
  fit?: {
    backend: string;
    global_orient: number[];
    body_pose: number[];
  };
};

export function useWebSocketPose(url: string) {
  const [latestPose, setLatestPose] = useState<PoseFrame | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let active = true;

    const connect = () => {
      if (!active) return;
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const data: PoseFrame = JSON.parse(event.data);
          // We only care about pose updates that have 'fit' data (global_orient, body_pose)
          if (data.status === 'ok' && data.fit) {
            setLatestPose(data);
          }
        } catch (e) {
          // ignore parsing errors
        }
      };

      ws.onclose = () => {
        if (!active) return;
        // Reconnect after 2 seconds
        setTimeout(connect, 2000);
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connect();

    return () => {
      active = false;
      wsRef.current?.close();
    };
  }, [url]);

  return latestPose;
}
