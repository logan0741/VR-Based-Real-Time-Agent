import { useEffect, useState } from 'react';
import { Exercise, FeedbackItem, SessionResult } from './types';
import { getRealtimeFeedback, getSessionResult } from './services/api';
import ExerciseSelector from './components/ExerciseSelector';
import FeedbackChip from './components/FeedbackChip';
import Hud from './components/Hud';
import RenderSlot from './components/RenderSlot';
import ResultPanel from './components/ResultPanel';
import SetControl from './components/SetControl';
import ScreenContainer from './components/ScreenContainer';
import { useTimer } from './hooks/useTimer';

const exerciseOptions: Exercise[] = [
  { id: 'squat', icon: '🏋️', label: '스쿼트' },
  { id: 'lunge', icon: '🤸', label: '런지' },
  { id: 'pushup', icon: '💪', label: '푸시업' },
];

const defaultFeedback: FeedbackItem = {
  status: 'warn',
  message: '무릎이 발끝을 넘어요',
};

function App() {
  const [screen, setScreen] = useState(0);
  const [selectedExercise, setSelectedExercise] = useState<Exercise>(exerciseOptions[0]);
  const [sets, setSets] = useState(3);
  const [sessionResult, setSessionResult] = useState<SessionResult | null>(null);
  const [feedback, setFeedback] = useState<FeedbackItem>(defaultFeedback);
  const [score, setScore] = useState(71);

  const { formattedTime, running, start, stop, reset } = useTimer(213);

  useEffect(() => {
    if (screen !== 1) return;
    getRealtimeFeedback(selectedExercise).then(setFeedback).catch(() => setFeedback(defaultFeedback));
  }, [screen, selectedExercise]);

  const changeSets = (delta: number) => {
    setSets((current) => Math.max(1, Math.min(10, current + delta)));
  };

  const handleSelectExercise = (exercise: Exercise) => {
    setSelectedExercise(exercise);
  };

  const handleStartWorkout = () => {
    reset();
    start();
    setScreen(1);
  };

  const handleEndSession = async () => {
    stop();
    const result = await getSessionResult(selectedExercise, sets);
    setSessionResult(result);
    setScore(result.score);
    setScreen(2);
  };

  const handleRetry = () => {
    reset();
    setSessionResult(null);
    setFeedback(defaultFeedback);
    setScore(71);
    setScreen(0);
  };

  return (
    <div className="app-shell">
      <ScreenContainer active={screen === 0} id="s0">
        <div className="s0-glow" />
        <div className="s0-grid" />
        <div className="s0-inner">
          <span className="eyebrow">VR Personal Trainer</span>
          <h1 className="big-title">
            PS<em>vR</em>
          </h1>
          <p className="subtitle">AI가 자세를 실시간으로 분석하고<br />맞춤형 피드백을 제공합니다</p>

          <ExerciseSelector
            options={exerciseOptions}
            selectedId={selectedExercise.id}
            onSelect={handleSelectExercise}
          />

          <SetControl count={sets} onChange={changeSets} />

          <button className="btn-start" onClick={handleStartWorkout} type="button">
            운동 시작 →
          </button>
        </div>
      </ScreenContainer>

      <ScreenContainer active={screen === 1} id="s1">
        <Hud
          time={formattedTime}
          currentSet={2}
          totalSets={sets}
          reps={8}
          score={score}
        />

        <div className="panels">
          <div className="panel">
            <div className="panel-label">
              <span className="p-dot purple" />강사 모델
            </div>
            <RenderSlot id="slot-instructor" label="3D render" />
            <div style={{ height: '40px' }} />
          </div>

          <div className="panel">
            <div className="panel-label">
              <span className="p-dot mint" />내 자세
            </div>
            <RenderSlot id="slot-user" label="3D render" />
            <FeedbackChip status={feedback.status} message={feedback.message} />
          </div>
        </div>

        <button className="btn-end" onClick={handleEndSession} type="button">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
            <rect x="2" y="2" width="10" height="10" rx="2" fill="currentColor" />
          </svg>
          운동 종료
        </button>
      </ScreenContainer>

      <ScreenContainer active={screen === 2} id="s2">
        <div className="s2-glow" />
        <ResultPanel
          result={sessionResult ?? {
            exercise: selectedExercise.label,
            sets,
            score,
            grade: 'B+',
            totalReps: sets * 8,
            durationMinutes: 12,
            accuracy: 92,
            feedback: [
              { status: 'ok', message: '상체 직립 자세가 전반적으로 안정적으로 유지되었습니다.' },
              { status: 'warn', message: '무릎이 발끝을 넘는 경향이 있어요. 앉을 때 체중을 뒤꿈치에 더 실어보세요.' },
              { status: 'ok', message: '세트가 진행될수록 하강 속도가 빨라졌습니다. 3초 카운트로 천천히 내려가면 효과가 높아집니다.' },
            ],
          }}
          onRetry={handleRetry}
          onHome={handleRetry}
        />
      </ScreenContainer>
    </div>
  );
}

export default App;
