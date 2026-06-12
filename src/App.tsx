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
import { type ExerciseProgress, useWebSocket } from './hooks/useWebSocket';
import { useExpertPose2D } from './hooks/useExpertPose2D';
import { initialProgress, progressFromTotalReps, REPS_PER_SET } from './utils/workoutProgress';

const TEXT = {
  squat: '\uc2a4\ucffc\ud2b8',
  hammerCurl: '\ud574\uba38 \uceec',
  lateralRaise: '\ub808\ud130\ub7f4 \ub808\uc774\uc988',
  pullup: '\ud480\uc5c5',
  measuring: '\uce21\uc815 \uc911\uc785\ub2c8\ub2e4.',
  start: '\uc6b4\ub3d9 \uc2dc\uc791',
  end: '\uc6b4\ub3d9 \uc885\ub8cc',
  instructor: '\uac15\uc0ac \ubaa8\ub378',
  myPose: '\ub0b4 \uc790\uc138',
};

const exerciseOptions: Exercise[] = [
  { id: 'squat', icon: 'SQ', label: TEXT.squat },
  { id: 'hammer_curl', icon: 'HC', label: TEXT.hammerCurl },
  { id: 'lateral_raise', icon: 'LR', label: TEXT.lateralRaise },
  { id: 'pull_up', icon: 'PU', label: TEXT.pullup },
];

type FeedbackSample = {
  score: number;
  message: string;
  bodyPart: string;
  severity: number;
  muscles: Record<string, string>;
};

const BODY_PART_LABELS: Record<string, string> = {
  knee: '\ubb34\ub98e',
  hip: '\uace8\ubc18',
  torso: '\uc0c1\uccb4',
  ankle: '\ubc1c\ubaa9',
  balance: '\uade0\ud615',
  elbow: '\ud314\uafc8\uce58',
  shoulder: '\uc5b4\uae68',
  wrist: '\uc190\ubaa9',
  ok: '\uc804\uccb4 \uc790\uc138',
};

const MUSCLE_LABELS: Record<string, string> = {
  chest: '\uac00\uc2b4',
  abs: '\ubcf5\uadfc',
  lower_back: '\ud558\ubd80 \ud5c8\ub9ac',
  left_quad: '\uc88c \ub300\ud1f4',
  right_quad: '\uc6b0 \ub300\ud1f4',
  left_hamstring: '\uc88c \ud584\uc2a4\ud2b8\ub9c1',
  right_hamstring: '\uc6b0 \ud584\uc2a4\ud2b8\ub9c1',
  left_glute: '\uc88c \ub454\uadfc',
  right_glute: '\uc6b0 \ub454\uadfc',
};

function labelBodyPart(part: string): string {
  return BODY_PART_LABELS[part] ?? part;
}

function labelMuscle(muscle: string): string {
  return MUSCLE_LABELS[muscle] ?? muscle;
}

function buildFinalFeedback(samples: FeedbackSample[], avgScore: number, reps: number) {
  if (samples.length === 0) {
    return [{
      title: '\ubd84\uc11d \ub370\uc774\ud130 \ubd80\uc871',
      message: '\uc6b4\ub3d9 \uc911 \uc218\uc9d1\ub41c \uc790\uc138 \ud53c\ub4dc\ubc31\uc774 \ubd80\uc871\ud569\ub2c8\ub2e4. \uce74\uba54\ub77c\uac00 \uc804\uc2e0\uc744 \uc548\uc815\uc801\uc73c\ub85c \uc7a1\ub3c4\ub85d \ub9de\ucd98 \ub4a4 \ub2e4\uc2dc \uce21\uc815\ud558\uc138\uc694.',
    }];
  }

  const validScores = samples.map((sample) => sample.score).filter((score) => Number.isFinite(score) && score > 0);
  const minScore = validScores.length ? Math.min(...validScores) : avgScore;
  const maxScore = validScores.length ? Math.max(...validScores) : avgScore;
  const problemSamples = samples.filter((sample) => sample.bodyPart && sample.bodyPart !== 'ok' && sample.bodyPart !== 'pending');

  const bodyCounts = new Map<string, number>();
  const messageCounts = new Map<string, number>();
  const muscleCounts = new Map<string, number>();

  for (const sample of problemSamples) {
    bodyCounts.set(sample.bodyPart, (bodyCounts.get(sample.bodyPart) ?? 0) + 1);
    if (sample.message) messageCounts.set(sample.message, (messageCounts.get(sample.message) ?? 0) + 1);
  }

  for (const sample of samples) {
    for (const [muscle, level] of Object.entries(sample.muscles)) {
      if (level === 'high' || level === 'med' || level === 'mid') {
        muscleCounts.set(muscle, (muscleCounts.get(muscle) ?? 0) + (level === 'high' ? 2 : 1));
      }
    }
  }

  const topBody = [...bodyCounts.entries()].sort((a, b) => b[1] - a[1])[0];
  const topMessages = [...messageCounts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 2);
  const topMuscles = [...muscleCounts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 3);

  const sections = [{
    title: '\uc804\uccb4 \ud3c9\uac00',
    message: `\ud3c9\uade0 \uc810\uc218\ub294 ${avgScore}\uc810\uc785\ub2c8\ub2e4. \uc138\uc158 \uc911 \ucd5c\uc800 ${Math.round(minScore)}\uc810, \ucd5c\uace0 ${Math.round(maxScore)}\uc810\uc73c\ub85c \uce21\uc815\ub410\uace0 \ucd1d ${reps}\ud68c\ub97c \uc218\ud589\ud588\uc2b5\ub2c8\ub2e4.`,
  }];

  if (topBody) {
    sections.push({
      title: '\uac00\uc7a5 \uc790\uc8fc \ud754\ub4e4\ub9b0 \ubd80\uc704',
      message: `${labelBodyPart(topBody[0])} \uad00\ub828 \uacbd\uace0\uac00 ${topBody[1]}\ud68c \uac10\uc9c0\ub410\uc2b5\ub2c8\ub2e4. \ub2e4\uc74c \uc138\ud2b8\uc5d0\uc11c\ub294 \uc774 \ubd80\uc704\ub97c \uba3c\uc800 \uc758\uc2dd\ud558\uba74\uc11c \ucc9c\ucc9c\ud788 \ubc18\ubcf5\ud558\uc138\uc694.`,
    });
  } else {
    sections.push({
      title: '\uc790\uc138 \uc548\uc815\uc131',
      message: '\ubc18\ubcf5\uc801\uc73c\ub85c \ub204\uc801\ub41c \ud070 \uc790\uc138 \uc624\ub958\ub294 \uc801\uc5c8\uc2b5\ub2c8\ub2e4. \ud604\uc7ac \uc18d\ub3c4\uc640 \uac00\ub3d9 \ubc94\uc704\ub97c \uc720\uc9c0\ud558\uc138\uc694.',
    });
  }

  if (topMessages.length > 0) {
    sections.push({
      title: '\ubc18\ubcf5\ub41c \uad50\uc815 \ud3ec\uc778\ud2b8',
      message: topMessages.map(([message, count]) => `${message} (${count}\ud68c)`).join(' / '),
    });
  }

  if (topMuscles.length > 0) {
    sections.push({
      title: '\ud53c\ub85c \ub204\uc801 \ubd80\uc704',
      message: `${topMuscles.map(([muscle]) => labelMuscle(muscle)).join(', ')} \ucabd \ud53c\ub85c \uc2e0\ud638\uac00 \ubc18\ubcf5\ub410\uc2b5\ub2c8\ub2e4. \uc790\uc138\uac00 \ubb34\ub108\uc9c0\uae30 \uc804\uc5d0 \ud734\uc2dd \uc2dc\uac04\uc744 \uc870\uae08 \ub298\ub9ac\uc138\uc694.`,
    });
  }

  sections.push({
    title: '\ub2e4\uc74c \uc138\ud2b8 \uae30\uc900',
    message: avgScore >= 75
      ? '\ud604\uc7ac \ub9ac\ub4ec\uc740 \uc720\uc9c0\ud558\ub418, \ubc18\ubcf5 \ud6c4\ubc18\uc5d0\ub3c4 \uac19\uc740 \uada4\uc801\uc744 \uc720\uc9c0\ud558\ub294\uc9c0 \ud655\uc778\ud558\uc138\uc694.'
      : '\uc18d\ub3c4\ub97c \ub0ae\ucd94\uace0 \ud55c \ubc18\ubcf5\ub9c8\ub2e4 \uc2dc\uc791 \uc790\uc138\ub97c \ub2e4\uc2dc \ub9de\ucd98 \ub4a4 \uc9c4\ud589\ud558\uc138\uc694. \uc810\uc218\ubcf4\ub2e4 \uac19\uc740 \uc790\uc138\ub97c \ubc18\ubcf5\ud558\ub294 \uac83\uc774 \uc6b0\uc120\uc785\ub2c8\ub2e4.',
  });

  return sections;
}

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
  const [userMirror, setUserMirror] = useState(false);
  const [feedback, setFeedback] = useState<FeedbackItem>({ status: 'ok', message: TEXT.measuring });
  const [score, setScore] = useState(0);
  const [reps, setReps] = useState(0);
  const [progress, setProgress] = useState<ExerciseProgress>(() => initialProgress(3));

  const { elapsed, formattedTime, start, stop, reset } = useTimer();
  const {
    latestFrame: liveFrame,
    status: wsStatus,
    poseCount,
    lastPoseAt,
    sessionControl,
    selectExercise,
    startSession,
    endSession,
  } = useWebSocket();
  const expertPose = useExpertPose2D(selectedExercise.id);

  useEffect(() => {
    localStorage.setItem('expertExercise', selectedExercise.id);
    selectExercise({ exerciseType: selectedExercise.id, sets, repsPerSet: REPS_PER_SET });
  }, [selectedExercise.id, selectExercise, sets]);

  const scoresRef = useRef<number[]>([]);
  const feedbackLogRef = useRef<FeedbackItem[]>([]);
  const seenMessagesRef = useRef<Set<string>>(new Set());
  const feedbackSamplesRef = useRef<FeedbackSample[]>([]);

  useEffect(() => {
    if (!liveFrame?.feedback) return;
    const { score: frameScore, message, rep_count, body_part, severity, muscle_fatigue, countable, feedback_event } = liveFrame.feedback;
    const isCountable = countable !== false;
    const isFeedbackEvent = feedback_event === true;

    if (isCountable && typeof frameScore === 'number' && frameScore > 0) {
      setScore(Math.round(frameScore));
      scoresRef.current.push(frameScore);
    }
    const fallbackProgress = isCountable && typeof liveFrame.feedback.total_reps === 'number'
      ? progressFromTotalReps(liveFrame.feedback.total_reps, sets)
      : null;
    const nextProgress: ExerciseProgress | null = liveFrame.progress ?? (
      fallbackProgress
        ? {
            current_set: liveFrame.feedback.current_set ?? fallbackProgress.current_set,
            total_sets: liveFrame.feedback.total_sets ?? fallbackProgress.total_sets,
            rep_in_set: liveFrame.feedback.rep_in_set ?? fallbackProgress.rep_in_set,
            reps_per_set: liveFrame.feedback.reps_per_set ?? fallbackProgress.reps_per_set,
            total_reps: fallbackProgress.total_reps,
            total_target_reps: liveFrame.feedback.total_target_reps ?? fallbackProgress.total_target_reps,
            completed: liveFrame.feedback.completed ?? fallbackProgress.completed,
          }
        : null
    );

    if (isCountable && nextProgress) {
      setProgress(nextProgress);
      setReps(nextProgress.total_reps);
    } else if (isCountable && typeof rep_count === 'number') {
      setReps(rep_count);
      setProgress(progressFromTotalReps(rep_count, sets));
    }

    if (isCountable && isFeedbackEvent) {
      feedbackSamplesRef.current.push({
        score: typeof frameScore === 'number' ? frameScore : 0,
        message: message || '',
        bodyPart: body_part || '',
        severity: typeof severity === 'number' ? severity : 0,
        muscles: muscle_fatigue ?? {},
      });
    }

    if (message && body_part !== 'pending') {
      const nextStatus: 'ok' | 'warn' = body_part === 'ok' ? 'ok' : 'warn';
      setFeedback({ status: nextStatus, message });

      if (isCountable && isFeedbackEvent && !seenMessagesRef.current.has(message)) {
        seenMessagesRef.current.add(message);
        feedbackLogRef.current.push({ status: nextStatus, message });
      }
    }
  }, [liveFrame]);

  const changeSets = (delta: number) => {
    setSets((current) => Math.max(1, Math.min(10, current + delta)));
  };

  useEffect(() => {
    setProgress((current) => ({
      ...current,
      current_set: Math.min(sets, current.current_set),
      total_sets: sets,
      total_target_reps: sets * current.reps_per_set,
      completed: current.total_reps >= sets * current.reps_per_set,
    }));
  }, [sets]);

  const handleStartWorkout = () => {
    scoresRef.current = [];
    feedbackLogRef.current = [];
    feedbackSamplesRef.current = [];
    seenMessagesRef.current = new Set();
    setScore(0);
    setReps(0);
    setProgress(initialProgress(sets));
    setFeedback({ status: 'ok', message: TEXT.measuring });
    startSession({ exerciseType: selectedExercise.id, sets, repsPerSet: REPS_PER_SET });
    reset();
    start();
    setScreen(1);
  };

  const handleEndSession = () => {
    endSession();
    stop();

    const avgScore = scoresRef.current.length > 0
      ? Math.round(scoresRef.current.reduce((sum, item) => sum + item, 0) / scoresRef.current.length)
      : score;

    const feedbackList: FeedbackItem[] = feedbackLogRef.current.length > 0
      ? feedbackLogRef.current.slice(-4)
      : [{
          status: avgScore >= 70 ? 'ok' : 'warn',
          message: avgScore >= 70
            ? '\uc804\ubc18\uc801\uc73c\ub85c \uc548\uc815\uc801\uc778 \uc790\uc138\ub97c \uc720\uc9c0\ud588\uc2b5\ub2c8\ub2e4.'
            : '\uc790\uc138 \uad50\uc815\uc774 \ub354 \ud544\uc694\ud569\ub2c8\ub2e4. \ub2e4\uc2dc \uc2dc\ub3c4\ud574\ubcf4\uc138\uc694.',
        }];

    const computed: SessionResult = {
      exercise: selectedExercise.label,
      sets,
      score: avgScore,
      grade: deriveGrade(avgScore),
      totalReps: reps,
      durationMinutes: Math.round(elapsed / 6) / 10,
      accuracy: avgScore,
      feedback: feedbackList,
      finalFeedback: buildFinalFeedback(feedbackSamplesRef.current, avgScore, reps),
    };

    setSessionResult(computed);
    setScore(avgScore);
    setScreen(2);
  };

  const handleRetry = () => {
    reset();
    setSessionResult(null);
    setFeedback({ status: 'ok', message: TEXT.measuring });
    setScore(0);
    setReps(0);
    setProgress(initialProgress(sets));
    setScreen(0);
  };

  const currentSet = progress.current_set;
  const repsInSet = progress.rep_in_set;
  const repsPerSet = progress.reps_per_set;

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
          <p className="subtitle">
            {'AI\uac00 \uc790\uc138\ub97c \uc2e4\uc2dc\uac04\uc73c\ub85c \ubd84\uc11d\ud558\uace0'}
            <br />
            {'\ub9de\ucda4\ud615 \ud53c\ub4dc\ubc31\uc744 \uc81c\uacf5\ud569\ub2c8\ub2e4.'}
          </p>

          <ExerciseSelector
            options={exerciseOptions}
            selectedId={selectedExercise.id}
            onSelect={setSelectedExercise}
          />

          <SetControl count={sets} onChange={changeSets} />

          <button className="btn-start" onClick={handleStartWorkout} type="button">
            {TEXT.start}
          </button>
        </div>
      </ScreenContainer>

      <ScreenContainer active={screen === 1} id="s1">
        <Hud
          time={formattedTime}
          currentSet={currentSet}
          totalSets={progress.total_sets}
          reps={repsInSet}
          repsPerSet={repsPerSet}
          totalReps={reps}
          totalTargetReps={progress.total_target_reps}
          score={score}
          wsStatus={wsStatus}
          poseCount={poseCount}
          lastPoseAgeMs={lastPoseAt ? Date.now() - lastPoseAt : null}
        />

        <div className="panels">
          <div className="panel">
            <div className="panel-label">
              <span className="p-dot purple" />
              {TEXT.instructor} - {selectedExercise.label}
            </div>
            <div className="render-slot">
              <SkeletonCanvas2D
                framesRef={expertPose.framesRef}
                framesVersion={expertPose.version}
                playbackVersion={sessionControl?.version ?? 0}
                playbackPhaseMs={sessionControl?.expert_phase_ms ?? 0}
                loading={expertPose.loading}
                fps={24}
                color="#a78bfa"
              />
            </div>
            <div style={{ height: '40px' }} />
          </div>

          <div className="panel">
            <div className="panel-label">
              <span className="p-dot mint" />
              {TEXT.myPose}
              <button
                className={`mirror-toggle ${userMirror ? 'on' : ''}`}
                type="button"
                onClick={() => setUserMirror((current) => !current)}
              >
                좌우 반전
              </button>
            </div>
            <div className="render-slot">
              <SkeletonCanvas2D
                keypoints={liveFrame?.keypoints_2d ?? null}
                badJoints={liveFrame?.feedback?.bad_joints ?? []}
                mirror={userMirror}
              />
            </div>
            <FeedbackChip status={feedback.status} message={feedback.message} />
          </div>
        </div>

        <button className="btn-end" onClick={handleEndSession} type="button">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
            <rect x="2" y="2" width="10" height="10" rx="2" fill="currentColor" />
          </svg>
          {TEXT.end}
        </button>
      </ScreenContainer>

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
