# 02 Step By Step Code Map

## Step 1. App 운동 선택

파일:

- `src/App.tsx`
- `src/hooks/useWebSocket.ts`

핵심 흐름:

```ts
selectExercise({ exerciseType, sets, repsPerSet })
startSession({ exerciseType, sets, repsPerSet })
```

수정 포인트:

- 운동 목록: `exerciseOptions`
- 세트 기본값: `useState(3)`
- 세트당 횟수: `REPS_PER_SET`
- 서버 progress 표시: `progress`, `currentSet`, `repsInSet`

## Step 2. Viewer 카메라와 keypoint 전송

파일:

- `final/s05_frontend/viewer.js`

핵심 흐름:

```js
const payload = poses[0].keypoints.map(kp => [kp.y / vh, kp.x / vw, kp.score ?? 0.9]);
ws.send(JSON.stringify({ data_type: "keypoints", frame_id, payload }));
```

수정 포인트:

- 카메라 시작: `startCamera`
- MoveNet 로딩: detector/model loading 부분
- 서버 전송 FPS/상태: `cameraDebug`, send loop
- viewer skeleton 좌우 반전: `drawSkeleton`, `normalizeToCanvas`

## Step 3. 서버 WebSocket entry

파일:

- `final/s02_backend/server.py`

핵심 함수:

- `websocket_endpoint`
- `ConnectionManager.broadcast_json`
- `FastPosePipeline.process_keypoints`

중요 분기:

```py
if data_type == "keypoints":
    pose_message = { "data_type": "pose", "keypoints_2d": payload }
    await manager.broadcast_json(pose_message)
    latest_keypoints_msg = msg
```

수정 포인트:

- app/viewer 공통 메시지 형식
- session control 변경
- preprocessing session reset
- progress attach 위치

## Step 4. Preprocessing session

파일:

- `final/s02_backend/server.py`
- `final/s01_preprocessing/config.py`
- `final/s01_preprocessing/pose_normalizer.py`
- `final/s01_preprocessing/rep_detector.py`
- `final/s01_preprocessing/feedback/feedback_engine.py`

핵심 흐름:

```py
prep = preprocessing_session.process(kpts_np)
feedback_block = {
    "rep_count": prep["rep_count"],
    "message": prep["message"],
    "score": prep["score"],
}
```

수정 포인트:

- 운동별 threshold: `rep_rules.py`
- 각도 계산: `joint_angles.py`
- 운동별 신호 추출: `rep_signals.py`
- 상태 머신: `rep_detector.py`
- 운동별 사용 관절: `config.py`
- 피드백 문장: `feedback_templates.py`
- 피드백 정책: `feedback_policy.py`

## Step 5. Set/Reps progress

파일:

- `final/s02_backend/server.py`
- `src/App.tsx`
- `src/components/Hud.tsx`

서버 기준:

```py
progress = exercise_progress(session_control, rep_count)
attach_progress(message, session_control)
```

app 기준:

```tsx
setProgress(nextProgress)
setReps(nextProgress.total_reps)
```

수정 포인트:

- 세트 경계 표시: `final/s02_backend/session_progress.py`
- app fallback 계산: `src/utils/workoutProgress.ts`
- HUD 표시: `Hud.tsx`

## Step 6. Expert pose sync

파일:

- `final/s02_backend/server.py`
- `src/components/SkeletonCanvas2D.tsx`
- `src/hooks/useExpertPose2D.ts`
- `final/s05_frontend/viewer.js`

핵심 값:

- `expert_started_at_ms`
- `expert_phase_ms`
- `session_control.version`

수정 포인트:

- 운동 변경 시 phase reset
- viewer/app expert frame index 계산
- expert FPS 통일

## Step 7. Final feedback

파일:

- `src/App.tsx`
- `src/components/ResultPanel.tsx`

핵심 함수:

```ts
buildFinalFeedback(feedbackSamples, avgScore, reps)
```

현재 방식:

- LLM/prompt 기반이 아니다.
- 누적된 실시간 feedback sample을 deterministic하게 집계한다.

수정 포인트:

- 최종 분석 문장
- 반복 문제 부위 집계
- 피로 누적 부위 집계
- 나중에 LLM을 붙일 경우 이 단계에만 붙인다.
