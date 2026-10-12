import { useEffect, useRef } from 'react';

export type ExpertSmplxFrame = {
  global_orient: number[];
  body_pose: number[];
};

// Returns a ref (not state) so callers read it inside useFrame without triggering re-renders.
export function useExpertPose(exercise: string = 'squat') {
  const framesRef = useRef<ExpertSmplxFrame[]>([]);
  const fpsRef = useRef<number>(24);

  useEffect(() => {
    fetch(`/api/expert-smplx?exercise=${exercise}`)
      .then((r) => r.json())
      .then((data) => {
        if (data.status === 'ok' && Array.isArray(data.frames)) {
          framesRef.current = data.frames as ExpertSmplxFrame[];
        }
      })
      .catch(() => {});
  }, [exercise]);

  return { framesRef, fpsRef };
}
