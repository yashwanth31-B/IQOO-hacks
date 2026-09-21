import { useState, useEffect } from 'react';
import { calculateElapsedSeconds, formatElapsedTimer } from '../utils/date.utils';

/**
 * Custom hook to maintain an accurate live elapsed timer based on backend startedAt timestamp
 * @param {string|null} startedAt - ISO timestamp from backend
 * @returns {{ elapsedSeconds: number, formattedTimer: string }}
 */
export const useSessionTimer = (startedAt) => {
  const [elapsedSeconds, setElapsedSeconds] = useState(() =>
    startedAt ? calculateElapsedSeconds(startedAt) : 0
  );

  useEffect(() => {
    if (!startedAt) {
      setElapsedSeconds(0);
      return;
    }

    // Immediately compute current elapsed
    setElapsedSeconds(calculateElapsedSeconds(startedAt));

    const intervalId = setInterval(() => {
      setElapsedSeconds(calculateElapsedSeconds(startedAt));
    }, 1000);

    return () => clearInterval(intervalId);
  }, [startedAt]);

  return {
    elapsedSeconds,
    formattedTimer: formatElapsedTimer(elapsedSeconds)
  };
};

export default useSessionTimer;
