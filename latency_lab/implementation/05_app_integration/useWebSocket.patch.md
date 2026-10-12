# `src/hooks/useWebSocket.ts` Integration

Add the hook:

```typescript
import { useLatencyMetrics } from '../../latency_lab/implementation/03_app/useLatencyMetrics';
```

Inside `useWebSocket()`:

```typescript
const latencyMetrics = useLatencyMetrics();
```

Inside `ws.onmessage`, immediately after parsing JSON:

```typescript
latencyMetrics.recordIncoming(data);
```

Return it:

```typescript
return {
  latestFrame,
  status,
  poseCount,
  lastPoseAt,
  sessionControl,
  latencyMetrics,
  selectExercise,
  startSession,
  endSession,
};
```

This lets the app show or download relay and processed feedback latency without
changing the existing pose rendering flow.
