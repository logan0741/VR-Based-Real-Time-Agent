import ScoreRing from './ScoreRing';

type HudProps = {
  time: string;
  currentSet: number;
  totalSets: number;
  reps: number;
  repsPerSet: number;
  totalReps: number;
  totalTargetReps: number;
  score: number;
  wsStatus?: string;
  poseCount?: number;
  lastPoseAgeMs?: number | null;
};

export default function Hud({
  time,
  currentSet,
  totalSets,
  reps,
  repsPerSet,
  totalReps,
  totalTargetReps,
  score,
  wsStatus = 'connecting',
  poseCount = 0,
  lastPoseAgeMs = null,
}: HudProps) {
  const poseState = poseCount > 0
    ? `${Math.round((lastPoseAgeMs ?? 0) / 100) / 10}s`
    : 'waiting';

  return (
    <div className="hud">
      <div className="hud-left">
        <div className="stat">
          <label>Time</label>
          <div className="val">{time}</div>
        </div>
        <div className="hud-sep" />
        <div className="stat">
          <label>Set</label>
          <div className="val">{currentSet}<small>/{totalSets}</small></div>
        </div>
        <div className="hud-sep" />
        <div className="stat">
          <label>Reps</label>
          <div className="val accent">{reps}<small>/{repsPerSet}</small></div>
          <div className="stat-sub">total {totalReps}/{totalTargetReps}</div>
        </div>
        <div className="hud-sep" />
        <div className="stat compact">
          <label>WS</label>
          <div className={`val mini ${wsStatus === 'open' ? 'ok' : 'warn'}`}>{wsStatus}</div>
        </div>
        <div className="hud-sep" />
        <div className="stat compact">
          <label>Pose</label>
          <div className={`val mini ${poseCount > 0 ? 'ok' : 'warn'}`}>{poseState}</div>
        </div>
      </div>
      <div className="score-ring-wrap">
        <div className="stat" style={{ textAlign: 'right' }}>
          <label>Score</label>
          <div className="val accent">{score}<small>/100</small></div>
        </div>
        <ScoreRing score={score} />
      </div>
    </div>
  );
}
