import { useEffect, useRef } from 'react';

// Raw 2D keypoints: frames[i] = 17 joints × [x, y, z]
export function useExpertPose2D(exercise: string) {
  const framesRef = useRef<number[][][]>([]);

  useEffect(() => {
    framesRef.current = [];
    fetch(`/api/expert?exercise=${exercise}`)
      .then((r) => r.json())
      .then((data) => {
        if (data.status === 'ok' && Array.isArray(data.frames) && data.frames.length > 0) {
          framesRef.current = data.frames as number[][][];
        }
      })
      .catch(() => {});
  }, [exercise]);

  return framesRef;
}
