import { useEffect, useRef, useState } from 'react';

export function useExpertPose2D(exercise: string) {
  const framesRef = useRef<number[][][]>([]);
  const [version, setVersion] = useState(0);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;

    framesRef.current = [];
    setLoading(true);
    setVersion((current) => current + 1);

    fetch(`/api/expert?exercise=${exercise}`)
      .then((response) => response.json())
      .then((data) => {
        if (cancelled) return;
        if (data.status === 'ok' && Array.isArray(data.frames) && data.frames.length > 0) {
          framesRef.current = data.frames as number[][][];
        }
      })
      .catch(() => {
        if (!cancelled) framesRef.current = [];
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
          setVersion((current) => current + 1);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [exercise]);

  return { framesRef, version, loading };
}
