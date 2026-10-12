type ScoreRingProps = {
  score: number;
};

export default function ScoreRing({ score }: ScoreRingProps) {
  const offset = 138 - (138 * Math.max(0, Math.min(100, score))) / 100;

  return (
    <svg className="ring-svg" width="48" height="48" viewBox="0 0 48 48" aria-hidden="true">
      <circle className="ring-track" cx="24" cy="24" r="22" />
      <circle className="ring-prog" cx="24" cy="24" r="22" style={{ strokeDashoffset: offset }} />
    </svg>
  );
}
