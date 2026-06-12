import { useState } from 'react';
import { requestFinalFeedbackTts } from '../services/ttsApi';
import type { SessionResult } from '../types';

type ResultPanelProps = {
  result: SessionResult;
  onRetry: () => void;
  onHome: () => void;
};

export default function ResultPanel({ result, onRetry, onHome }: ResultPanelProps) {
  const [ttsUrl, setTtsUrl] = useState<string | null>(null);
  const [ttsStatus, setTtsStatus] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle');
  const [ttsMessage, setTtsMessage] = useState('');

  const handleCreateTts = async () => {
    setTtsStatus('loading');
    setTtsMessage('');
    setTtsUrl(null);

    try {
      const response = await requestFinalFeedbackTts(result);
      if (response.status === 'ok' && response.audio_url) {
        setTtsUrl(response.audio_url);
        setTtsStatus('ready');
        setTtsMessage(response.cached ? '저장된 음성을 불러왔습니다.' : '최종 피드백 음성이 생성되었습니다.');
        return;
      }

      setTtsStatus('error');
      setTtsMessage(response.message ?? 'TTS 음성 생성에 실패했습니다.');
    } catch (error) {
      setTtsStatus('error');
      setTtsMessage(error instanceof Error ? error.message : 'TTS 요청 중 오류가 발생했습니다.');
    }
  };

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

      <div className="feedback-box final-report">
        <div className="fb-title">최종 자세 분석</div>
        {result.finalFeedback.map((section) => (
          <div className="final-section" key={section.title}>
            <strong>{section.title}</strong>
            <span>{section.message}</span>
          </div>
        ))}
      </div>

      <div className="feedback-box tts-box">
        <div className="fb-title">최종 피드백 음성</div>
        <button
          className="btn-tts"
          type="button"
          onClick={handleCreateTts}
          disabled={ttsStatus === 'loading'}
        >
          {ttsStatus === 'loading' ? '음성 생성 중' : '음성 생성'}
        </button>
        {ttsMessage ? <p className={`tts-message ${ttsStatus}`}>{ttsMessage}</p> : null}
        {ttsUrl ? (
          <audio className="tts-player" src={ttsUrl} controls preload="metadata">
            최종 피드백 음성을 재생할 수 없습니다.
          </audio>
        ) : null}
      </div>

      <div className="feedback-box">
        <div className="fb-title">운동 중 주요 피드백</div>
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
          처음으로
        </button>
      </div>
    </div>
  );
}
