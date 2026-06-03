import { useEffect, useRef, useState } from 'react';

const EXPERT_FPS = 24;

export function useExpertPose() {
  const [currentFrame, setCurrentFrame] = useState<number[][] | null>(null);
  const framesRef = useRef<number[][][]>([]);

  useEffect(() => {
    fetch('/api/expert-keypoints')
      .then((r) => r.json())
      .then((data) => {
        if (data.status === 'ok' && Array.isArray(data.frames)) {
          framesRef.current = data.frames as number[][][];
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    const id = setInterval(() => {
      if (framesRef.current.length === 0) return;
      // 시각 기반 인덱스 — viewer/app 모두 같은 프레임을 동시에 표시
      const idx = Math.floor(Date.now() / (1000 / EXPERT_FPS)) % framesRef.current.length;
      setCurrentFrame(framesRef.current[idx]);
    }, 1000 / EXPERT_FPS);
    return () => clearInterval(id);
  }, []);

  return currentFrame;
}
