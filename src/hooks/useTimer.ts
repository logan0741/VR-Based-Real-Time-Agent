import { useEffect, useState } from 'react';

export function useTimer(initialSeconds: number) {
  const [timeLeft, setTimeLeft] = useState(initialSeconds);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    if (!running) return;

    const interval = window.setInterval(() => {
      setTimeLeft((value) => {
        if (value <= 1) {
          window.clearInterval(interval);
          setRunning(false);
          return 0;
        }
        return value - 1;
      });
    }, 1000);

    return () => window.clearInterval(interval);
  }, [running]);

  const start = () => {
    if (timeLeft <= 0) {
      setTimeLeft(initialSeconds);
    }
    setRunning(true);
  };

  const stop = () => setRunning(false);
  const reset = () => {
    setRunning(false);
    setTimeLeft(initialSeconds);
  };

  const formattedTime = `${String(Math.floor(timeLeft / 60)).padStart(2, '0')}:${String(
    timeLeft % 60,
  ).padStart(2, '0')}`;

  return {
    timeLeft,
    formattedTime,
    running,
    start,
    stop,
    reset,
  };
}
