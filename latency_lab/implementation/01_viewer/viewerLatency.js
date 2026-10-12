export function createLatencyPayload(frameId) {
  return {
    frameId,
    viewerCreatedAtMs: performance.now(),
    clientTimestampMs: Date.now(),
  };
}

export function buildKeypointMessage(frameId, payload) {
  const telemetry = createLatencyPayload(frameId);
  return {
    data_type: "keypoints",
    frame_id: frameId,
    client_timestamp_ms: telemetry.clientTimestampMs,
    latency_probe: telemetry,
    payload,
  };
}

export function sendKeypointsWithLatency(ws, frameId, payload) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return false;
  ws.send(JSON.stringify(buildKeypointMessage(frameId, payload)));
  return true;
}
