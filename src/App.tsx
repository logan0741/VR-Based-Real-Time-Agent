import { useEffect, useRef, useState } from 'react';
import { Exercise, FeedbackItem, SessionResult } from './types';
import ExerciseSelector from './components/ExerciseSelector';
import FeedbackChip from './components/FeedbackChip';
import Hud from './components/Hud';
import ResultPanel from './components/ResultPanel';
import SetControl from './components/SetControl';
import ScreenContainer from './components/ScreenContainer';
import SkeletonCanvas2D from './components/SkeletonCanvas2D';
import { useTimer } from './hooks/useTimer';
import { useWebSocket } from './hooks/useWebSocket';
import { useExpertPose2D } from './hooks/useExpertPose2D';

const exerciseOptions: Exercise[] = [
  { id: 'squat',         icon: 'SQ', label: '스쿼트' },
  { id: 'hammer_curl',   icon: 'HC', label: '해머 컬' },
  { id: 'lateral_raise', icon: 'LR', label: '레터럴 레이즈' },
  { id: 'pull_up',       icon: 'PU', label: '풀업' },
];

const REPS_PER_SET = 8;

function deriveGrade(score: number): string {
  if (score >= 90) return 'A';
  if (score >= 80) return 'B+';
  if (score >= 70) return 'B';
  if (score >= 60) return 'C+';
  return 'C';
}

function App() {
  const [screen, setScreen] = useState(0);
  const [selectedExercise, setSelectedExercise] = useState<Exercise>(exerciseOptions[0]);
  const [sets, setSets] = useState(3);
  const [sessionResult, setSessionResult] = useState<SessionResult | null>(null);
  const [feedback, setFeedback] = useState<FeedbackItem>({ status: 'ok', message: '측정 중입니다.' });
  const [score, setScore] = useState(0);
  const [reps, setReps] = useState(0);

  const { elapsed, formattedTime, start, stop, reset } = useTimer();
  const {
    latestFrame: liveFrame,
    status: wsStatus,
    poseCount,
    lastPoseAt,
    selectExercise,
    startSession,
    endSession,
  } = useWebSocket();
  const expertFramesRef = useExpertPose2D(selectedExercise.id);

  // Sync exercise selection to viewer via localStorage
  useEffect(() => {
    localStorage.setItem('expertExercise', selectedExercise.id);
    selectExercise({ exerciseType: selectedExercise.id, sets, repsPerSet: REPS_PER_SET });
  }, [selectedExercise.id, selectExercise, sets]);

  const scoresRef = useRef<number[]>([]);
  const feedbackLogRef = useRef<FeedbackItem[]>([]);
  const seenMessagesRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (!liveFrame?.feedback) return;
    const { score: s, message, rep_count, body_part } = liveFrame.feedback;

    if (typeof s === 'number' && s > 0) {
      setScore(Math.round(s));
      scoresRef.current.push(s);
    }
    if (typeof rep_count === 'number') setReps(rep_count);

    if (message && body_part !== 'pending') {
      const fbStatus: 'ok' | 'warn' = body_part === 'ok' ? 'ok' : 'warn';
      setFeedback({ status: fbStatus, message });

      if (!seenMessagesRef.current.has(message)) {
        seenMessagesRef.current.add(message);
        feedbackLogRef.current.push({ status: fbStatus, message });
      }
    }
  }, [liveFrame]);

  const changeSets = (delta: number) => {
    setSets((c) => Math.max(1, Math.min(10, c + delta)));
  };

  const handleStartWorkout = () => {
    scoresRef.current = [];
    feedbackLogRef.current = [];
    seenMessagesRef.current = new Set();
    setScore(0);
    setReps(0);
    setFeedback({ status: 'ok', message: '측정 중입니다.' });
    startSession({ exerciseType: selectedExercise.id, sets, repsPerSet: REPS_PER_SET });
    reset();
    start();
    setScreen(1);
  };

  const handleEndSession = () => {
    endSession();
    stop();

    const avgScore =
      scoresRef.current.length > 0
        ? Math.round(scoresRef.current.reduce((a, b) => a + b, 0) / scoresRef.current.length)
        : score;

    const feedbackList: FeedbackItem[] =
      feedbackLogRef.current.length > 0
        ? feedbackLogRef.current.slice(-4)
        : [
            {
              status: avgScore >= 70 ? 'ok' : 'warn',
              message:
                avgScore >= 70
                  ? '전반적으로 안정적인 자세를 유지했습니다.'
                  : '자세 교정이 더 필요합니다. 다시 시도해보세요.',
            },
          ];

    const computed: SessionResult = {
      exercise: selectedExercise.label,
      sets,
      score: avgScore,
      grade: deriveGrade(avgScore),
      totalReps: reps,
      durationMinutes: Math.round(elapsed / 6) / 10,
      accuracy: avgScore,
      feedback: feedbackList,
    };

    setSessionResult(computed);
    setScore(avgScore);
    setScreen(2);
  };

  const handleRetry = () => {
    reset();
    setSessionResult(null);
    setFeedback({ status: 'ok', message: '측정 중입니다.' });
    setScore(0);
    setReps(0);
    setScreen(0);
  };

  const currentSet = Math.min(sets, Math.floor(reps / REPS_PER_SET) + 1);

  return (
    <div className="app-shell">
      {/* Screen 0: Exercise selection */}
      <ScreenContainer active={screen === 0} id="s0">
        <div className="s0-glow" />
        <div className="s0-grid" />
        <div className="s0-inner">
          <span className="eyebrow">VR Personal Trainer</span>
          <h1 className="big-title">
            PS<em>vR</em>
          </h1>
          <p className="subtitle">
            AI가 자세를 실시간으로 분석하고
            <br />
            맞춤형 피드백을 제공합니다.
          </p>

          <ExerciseSelector
            options={exerciseOptions}
            selectedId={selectedExercise.id}
            onSelect={setSelectedExercise}
          />

          <SetControl count={sets} onChange={changeSets} />

          <button className="btn-start" onClick={handleStartWorkout} type="button">
            운동 시작
          </button>
        </div>
      </ScreenContainer>

      {/* Screen 1: Workout */}
      <ScreenContainer active={screen === 1} id="s1">
        <Hud
          time={formattedTime}
          currentSet={currentSet}
          totalSets={sets}
          reps={reps}
          score={score}
          wsStatus={wsStatus}
          poseCount={poseCount}
          lastPoseAgeMs={lastPoseAt ? Date.now() - lastPoseAt : null}
        />

        <div className="panels">
          <div className="panel">
            <div className="panel-label">
              <span className="p-dot purple" />
              강사 모델 — {selectedExercise.label}
            </div>
            <div className="render-slot">
              <SkeletonCanvas2D framesRef={expertFramesRef} fps={15} color="#a78bfa" />
            </div>
            <div style={{ height: '40px' }} />
          </div>

          <div className="panel">
            <div className="panel-label">
              <span className="p-dot mint" />
              내 자세
            </div>
            <div className="render-slot">
              <SkeletonCanvas2D keypoints={liveFrame?.keypoints_2d ?? null} />
            </div>
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

      {/* Screen 2: Results */}
      <ScreenContainer active={screen === 2} id="s2">
        <div className="s2-glow" />
        {sessionResult && (
          <ResultPanel
            result={sessionResult}
            onRetry={handleRetry}
            onHome={handleRetry}
          />
        )}
      </ScreenContainer>
    </div>
  );
}

export default App;
