# Apply Latency Pipeline To Main

## 1. Backend

Patch `final/s02_backend/server.py`.

In the immediate relay path, include:

```python
server_received_ms = int(time.time() * 1000)
debug = {
    "relay_only": True,
    "client_timestamp_ms": msg.get("client_timestamp_ms"),
    "server_received_ms": server_received_ms,
    "server_relay_sent_ms": int(time.time() * 1000),
}
```

In the processed feedback path, include:

```python
response.setdefault("debug", {})
response["debug"]["client_timestamp_ms"] = current_msg.get("client_timestamp_ms")
response["debug"]["server_processed_at_ms"] = int(time.time() * 1000)
```

## 2. Viewer

Patch `viewer_2d/viewer.js`.

Before sending a keypoint frame:

```javascript
const telemetry = createLatencyPayload(frameId);
ws.send(JSON.stringify({
  data_type: "keypoints",
  frame_id: frameId,
  client_timestamp_ms: telemetry.clientTimestampMs,
  latency_probe: telemetry,
  payload
}));
```

The viewer can also draw local skeleton immediately. That local draw is not part
of server relay latency.

## 3. App

Patch `src/hooks/useWebSocket.ts` or wrap it with `useLatencyMetrics.ts`.

On every incoming message:

```typescript
latencyTracker.recordIncoming(data);
```

Use `latencyTracker.toJson()` when saving a report.

## 4. Report

Use `04_report/latencyReportWriter.ts` to download a JSON report from the app UI
or to send it to the backend later.

## 5. Verify

Run:

```powershell
python -m py_compile final\s02_backend\server.py
npm run build
python latency_lab\run_latency_suite.py --frames 90 --fps 30 --exercise squat
```
