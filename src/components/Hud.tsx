import ScoreRing from './ScoreRing';

type HudProps = {
  time: string;
  currentSet: number;
  totalSets: number;
  reps: number;
  score: number;
};

export default function Hud({ time, currentSet, totalSets, reps, score }: HudProps) {
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
          <div className="val accent">{reps}</div>
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
