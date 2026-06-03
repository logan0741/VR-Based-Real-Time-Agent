import type { SessionResult } from '../types';

type ResultPanelProps = {
  result: SessionResult;
  onRetry: () => void;
  onHome: () => void;
};

export default function ResultPanel({ result, onRetry, onHome }: ResultPanelProps) {
  return (
    <div className="s2-inner">
      <p className="result-tag">
        운동 완료 · {result.exercise} {result.sets}세트
      </p>
      <div className="result-score">{result.score}</div>
      <p className="result-grade">
        평균 점수 · 등급 <strong>{result.grade}</strong>
      </p>

      <div className="stat-cards">
        <div className="stat-card">
          <div className="sv">{result.totalReps}</div>
          <div className="sl">총 횟수</div>
        </div>
        <div className="stat-card">
          <div className="sv">
            {result.durationMinutes}
            <span style={{ fontSize: 18, color: 'var(--muted)' }}>분</span>
          </div>
          <div className="sl">운동 시간</div>
        </div>
        <div className="stat-card">
          <div className="sv" style={{ color: 'var(--accent2)' }}>
            {result.accuracy}%
          </div>
          <div className="sl">자세 정확도</div>
        </div>
      </div>

      <div className="feedback-box">
        <div className="fb-title">AI 피드백</div>
        {result.feedback.map((item, index) => (
          <div className="fb-item" key={`${item.status}-${index}`}>
            <span className="fb-ico">{item.status === 'ok' ? 'OK' : '!'}</span>
            <span>{item.message}</span>
          </div>
        ))}
      </div>

      <div className="result-btns">
        <button className="btn-retry" type="button" onClick={onRetry}>
          다시 시작
        </button>
        <button className="btn-home" type="button" onClick={onHome}>
          홈으로
        </button>
      </div>
    </div>
  );
}
